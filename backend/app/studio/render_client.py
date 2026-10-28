"""Backend client of the renderer's studio endpoints (/studio/inspect, /studio/render)."""
from __future__ import annotations

import asyncio
import json

import httpx
from pydantic import ValidationError

from app.studio.render_contract import InspectRequest, InspectResult, Issue, RenderRequest
from app.videos.render_contract import MAX_OUTPUT_BYTES

RENDER_TIMEOUT = 960  # same as the old pipeline's client
INSPECT_TIMEOUT = 120
MAX_RENDER_BYTES = int(MAX_OUTPUT_BYTES * 1.4) + 4096  # base64 of the mp4 plus the JSON envelope
MAX_INSPECT_BYTES = 64 * 1024 * 1024
MAX_RETRIES = 10
DEFAULT_RETRY_AFTER = 2
MAX_RETRY_AFTER = 30

UNCONFIGURED = '视频渲染服务尚未配置，请联系管理员'
BUSY = '渲染服务忙，请稍后重试'
VERSION_MISMATCH = '渲染服务版本不一致，请重新部署渲染服务'
UNAVAILABLE = '渲染服务暂时不可用'


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
    return min(seconds, MAX_RETRY_AFTER)


class StudioRenderer:
    def __init__(self, settings, http: httpx.AsyncClient, *, sleep=asyncio.sleep):
        self.url = (settings.renderer_url or '').strip().rstrip('/')
        self.http = http
        self.sleep = sleep

    async def inspect(self, req: InspectRequest) -> InspectResult:
        body = await self._post('/studio/inspect', req.model_dump(mode='json'), INSPECT_TIMEOUT, MAX_INSPECT_BYTES)
        try:
            return InspectResult.model_validate_json(body)
        except ValidationError:
            raise ValueError(UNAVAILABLE) from None

    async def render(self, req: RenderRequest) -> dict:
        body = await self._post('/studio/render', req.model_dump(mode='json'), RENDER_TIMEOUT, MAX_RENDER_BYTES)
        try:
            result = json.loads(body)
            if not isinstance(result.get('mp4_base64'), str) or not isinstance(result.get('metadata'), dict):
                raise ValueError
        except (ValueError, AttributeError):
            raise ValueError(UNAVAILABLE) from None
        return result

    async def _post(self, path: str, payload: dict, timeout: float, limit: int) -> bytes:
        if not self.url:
            raise ValueError(UNCONFIGURED)
        for attempt in range(MAX_RETRIES + 1):
            body, wait = await self._once(path, payload, timeout, limit)
            if body is not None:
                return body
            if attempt < MAX_RETRIES:
                await self.sleep(wait)
        raise ValueError(BUSY)

    async def _once(self, path: str, payload: dict, timeout: float, limit: int) -> tuple[bytes | None, float]:
        """One request: ``(body, 0)``, or ``(None, seconds_to_wait)`` while the renderer is busy."""
        try:
            async with self.http.stream('POST', self.url + path, json=payload, timeout=timeout,
                                        follow_redirects=False) as response:
                if response.status_code == 429:
                    await response.aread()
                    return None, retry_after(response)
                if response.status_code == 409:
                    raise ValueError(VERSION_MISMATCH)
                if response.status_code == 422:
                    await response.aread()
                    try:
                        detail = response.json().get('detail')
                    except (ValueError, AttributeError):
                        detail = None
                    raise StudioRenderError.from_detail(detail)
                if not response.is_success:
                    raise ValueError(UNAVAILABLE)
                body = bytearray()
                async for block in response.aiter_bytes():
                    body.extend(block)
                    if len(body) > limit:
                        raise ValueError(UNAVAILABLE)
                return bytes(body), 0
        except httpx.HTTPError:
            raise ValueError(UNAVAILABLE) from None
