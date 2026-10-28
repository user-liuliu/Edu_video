"""Backend client of the renderer's studio endpoints (/studio/inspect, /studio/render)."""
from __future__ import annotations

import asyncio
import base64
import binascii
import json
import time
from typing import Literal

import httpx
from pydantic import ValidationError

from app.studio.render_contract import InspectRequest, InspectResult, Issue, RenderRequest
from app.videos.render_contract import MAX_OUTPUT_BYTES

RENDER_TIMEOUT = 960  # same as the old pipeline's client
INSPECT_TIMEOUT = 120
MAX_RENDER_BYTES = int(MAX_OUTPUT_BYTES * 1.4) + 4096  # base64 of the mp4 plus the JSON envelope
MAX_INSPECT_BYTES = 64 * 1024 * 1024
MAX_ERROR_BYTES = 1024 * 1024  # 422 bodies are tiny JSON; anything longer is cut off
# The renderer runs one job at a time and a render holds it for minutes, so a busy (429)
# answer is queued for: retried until this much wall time has passed since the first try,
# like the old pipeline's QUEUE_TIMEOUT. Applies to inspect and render alike.
QUEUE_BUDGET = 1800
DEFAULT_RETRY_AFTER = 2
MIN_RETRY_AFTER = 0.5  # a Retry-After of 0 must not turn the queue budget into a busy loop
MAX_RETRY_AFTER = 30

UNCONFIGURED = '视频渲染服务尚未配置，请联系管理员'
BUSY = '渲染服务忙，请稍后重试'
VERSION_MISMATCH = '渲染服务版本不一致，请重新部署渲染服务'
UNAVAILABLE = '渲染服务暂时不可用'
TIMEOUT = '渲染超时，请缩短片段或简化画面'
TOO_LARGE = '渲染内容过大，请缩短片段'

Reason = Literal['timeout', 'too_large', 'network', 'bad_response', 'http_error']
_MESSAGES = {'timeout': TIMEOUT, 'too_large': TOO_LARGE}


class StudioUnavailable(ValueError):
    """The renderer could not deliver a usable answer. ``reason`` tells why: ``timeout`` (504 or the client
    gave up: the segment is too heavy), ``too_large`` (413 or the response exceeded the cap), ``network``
    (renderer unreachable), ``bad_response`` (200 with an unusable body), ``http_error`` (any other status)."""

    def __init__(self, reason: Reason, status: int | None = None):
        self.reason = reason
        self.status = status
        super().__init__(_MESSAGES.get(reason, UNAVAILABLE))


class StudioRenderError(ValueError):
    """The renderer answered 422: the request is invalid (``studio_input``), or the film it carries
    reports runtime problems and cannot be exported (``studio_runtime``, with ``issues``)."""

    def __init__(self, detail, *, code: str | None = None, issues: list[Issue] | None = None):
        self.detail = detail
        self.code = code
        self.issues = issues or []
        super().__init__(self._message(detail, self.issues))

    @staticmethod
    def _message(detail, issues: list[Issue]) -> str:
        if isinstance(detail, dict) and detail.get('code') == 'studio_runtime':
            first = issues[0].message if issues else str(detail.get('message', ''))
            return f'动画运行出错，不能导出：{first}'[:500]
        if isinstance(detail, dict):
            return str(detail.get('message') or '渲染服务拒绝了请求')[:500]
        return '渲染服务拒绝了请求，请检查整片内容'

    @classmethod
    def from_detail(cls, detail) -> StudioRenderError:
        code = detail.get('code') if isinstance(detail, dict) else None
        issues: list[Issue] = []
        if code == 'studio_runtime':
            for raw in detail.get('issues') or []:
                try:
                    issues.append(Issue.model_validate(raw))
                except ValidationError:
                    continue
        return cls(detail, code=code, issues=issues)


def retry_after(response: httpx.Response) -> float:
    try:
        seconds = float(response.headers.get('Retry-After', DEFAULT_RETRY_AFTER))
    except ValueError:
        return DEFAULT_RETRY_AFTER
    if not 0 <= seconds < float('inf'):
        return DEFAULT_RETRY_AFTER
    return min(max(seconds, MIN_RETRY_AFTER), MAX_RETRY_AFTER)


class StudioRenderer:
    def __init__(self, settings, http: httpx.AsyncClient, *, sleep=asyncio.sleep, clock=time.monotonic):
        self.url = (settings.renderer_url or '').strip().rstrip('/')
        self.http = http
        self.sleep = sleep
        self.clock = clock

    async def inspect(self, req: InspectRequest) -> InspectResult:
        body = await self._post('/studio/inspect', req.model_dump(mode='json'), INSPECT_TIMEOUT, MAX_INSPECT_BYTES)
        try:
            return InspectResult.model_validate_json(body)
        except ValidationError:
            raise StudioUnavailable('bad_response') from None

    async def render(self, req: RenderRequest) -> dict:
        body = await self._post('/studio/render', req.model_dump(mode='json'), RENDER_TIMEOUT, MAX_RENDER_BYTES)
        try:
            result = json.loads(body)
            if not isinstance(result.get('metadata'), dict) or not isinstance(result.get('mp4_base64'), str):
                raise ValueError
            if not base64.b64decode(result['mp4_base64'], validate=True):
                raise ValueError
        except (ValueError, AttributeError, binascii.Error):
            raise StudioUnavailable('bad_response') from None
        return result

    async def _post(self, path: str, payload: dict, timeout: float, limit: int) -> bytes:
        if not self.url:
            raise ValueError(UNCONFIGURED)
        deadline = self.clock() + QUEUE_BUDGET
        while True:
            body, wait = await self._once(path, payload, timeout, limit)
            if body is not None:
                return body
            remaining = deadline - self.clock()
            if remaining <= 0:
                raise ValueError(BUSY)
            await self.sleep(min(wait, remaining))

    async def _once(self, path: str, payload: dict, timeout: float, limit: int) -> tuple[bytes | None, float]:
        """One request: ``(body, 0)``, or ``(None, seconds_to_wait)`` while the renderer is busy."""
        try:
            async with self.http.stream('POST', self.url + path, json=payload, timeout=timeout,
                                        follow_redirects=False) as response:
                if response.status_code == 429:
                    return None, retry_after(response)
                if response.status_code == 409:
                    raise ValueError(VERSION_MISMATCH)
                if response.status_code == 422:
                    try:
                        detail = json.loads(await self._read(response, MAX_ERROR_BYTES, strict=False)).get('detail')
                    except (ValueError, AttributeError):
                        detail = None
                    raise StudioRenderError.from_detail(detail)
                if response.status_code == 504:
                    raise StudioUnavailable('timeout', 504)
                if response.status_code == 413:
                    raise StudioUnavailable('too_large', 413)
                if not response.is_success:
                    raise StudioUnavailable('http_error', response.status_code)
                return await self._read(response, limit), 0
        except httpx.TimeoutException:
            raise StudioUnavailable('timeout') from None
        except httpx.HTTPError:
            raise StudioUnavailable('network') from None

    @staticmethod
    async def _read(response: httpx.Response, limit: int, *, strict: bool = True) -> bytes:
        """The body, read in blocks. Over ``limit`` it is a ``too_large`` failure, or cut off when not strict."""
        body = bytearray()
        async for block in response.aiter_bytes():
            body.extend(block)
            if len(body) > limit:
                if strict:
                    raise StudioUnavailable('too_large', response.status_code)
                return bytes(body[:limit])
        return bytes(body)
