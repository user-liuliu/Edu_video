"""模型配置的"测试连接"：按用途向接口发一个最小的请求，看能不能用。

返回的提示会保存到库里并显示给管理员，所以失败提示都要先用 redact 去掉 API key。
"""

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.purposes import Purpose

from .schemas import ResolvedConfig, Voice

OK_MESSAGE = "连接正常"
BODY_PREVIEW_LENGTH = 200

# 火山引擎 v3 接口成功时 code 常为 20000000
_TTS_OK_CODES = (0, 20000000)

_CHAT_PURPOSES = frozenset({Purpose.outline_llm, Purpose.review_llm, Purpose.vision_llm})


@dataclass
class ProbeResult:
    ok: bool
    message: str


class ProbeUnsupported(Exception):
    """这种用途暂时不支持测试连接。"""


def join_url(base: str, path: str) -> str:
    return base.rstrip("/") + "/" + path.lstrip("/")


def redact(text: str, secret: str) -> str:
    """把 text 里出现的 secret 换成 ****。"""
    if not secret:
        return text
    return text.replace(secret, "****")


def _first_voice(extra: dict[str, Any]) -> Voice | None:
    raw = extra.get("voices")
    if not isinstance(raw, list):
        return None
    for item in raw:
        try:
            return Voice.model_validate(item)
        except ValueError:
            continue
    return None


def _json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except ValueError:
        return None


def _check_image_models(resp: httpx.Response, model: str) -> ProbeResult:
    body = _json(resp)
    data = body.get("data") if isinstance(body, dict) else None
    if isinstance(data, list) and any(
        isinstance(m, dict) and m.get("id") == model for m in data
    ):
        return ProbeResult(True, OK_MESSAGE)
    return ProbeResult(False, f"接口可用，但没有找到模型 {model}")


def _preview(text: str, secret: str) -> str:
    """先去掉 key 再截断，免得 key 正好跨在截断处、只剩半截而没被替换。"""
    return redact(text, secret)[:BODY_PREVIEW_LENGTH]


def _check_tts(resp: httpx.Response, secret: str) -> ProbeResult:
    body = _json(resp)
    if not isinstance(body, dict):
        # 不是 JSON（例如直接返回音频）也算成功
        return ProbeResult(True, OK_MESSAGE)
    code = body.get("code")
    if code is None or code in _TTS_OK_CODES:
        return ProbeResult(True, OK_MESSAGE)
    detail = _preview(str(body.get("message") or ""), secret)
    return ProbeResult(False, f"接口返回错误：{code} {detail}")


async def _probe(http: httpx.AsyncClient, cfg: ResolvedConfig) -> ProbeResult:
    purpose = Purpose(cfg.purpose)
    bearer = {"Authorization": f"Bearer {cfg.api_key}"}

    if purpose in _CHAT_PURPOSES:
        url = join_url(cfg.base_url, "chat/completions")
        body = {"model": cfg.model, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1}
        request = http.build_request("POST", url, headers=bearer, json=body)
    elif purpose == Purpose.embedding:
        url = join_url(cfg.base_url, "embeddings")
        request = http.build_request(
            "POST", url, headers=bearer, json={"model": cfg.model, "input": "ping"}
        )
    elif purpose == Purpose.image_gen:
        # 只查模型列表，不真的生成图片（生成要花钱）
        url = join_url(cfg.base_url, "models")
        request = http.build_request("GET", url, headers=bearer)
    elif purpose == Purpose.tts:
        voice = _first_voice(cfg.extra)
        if voice is None:
            return ProbeResult(False, "请先配置至少一个音色")
        url = join_url(cfg.base_url, "api/v3/tts/create")
        body = {"model": cfg.model, "text_prompt": "测试", "speaker": voice.speaker_id}
        request = http.build_request("POST", url, headers={"X-Api-Key": cfg.api_key}, json=body)
    else:
        raise ProbeUnsupported(purpose.value)

    try:
        resp = await http.send(request)
    except httpx.TimeoutException:
        return ProbeResult(False, "连接超时")
    except httpx.TransportError:
        return ProbeResult(False, f"无法连接到 {urlsplit(url).hostname or url}")

    if not resp.is_success:
        return ProbeResult(False, f"HTTP {resp.status_code}：{_preview(resp.text, cfg.api_key)}")
    if purpose == Purpose.image_gen:
        return _check_image_models(resp, cfg.model)
    if purpose == Purpose.tts:
        return _check_tts(resp, cfg.api_key)
    return ProbeResult(True, OK_MESSAGE)


async def run_probe(http: httpx.AsyncClient, cfg: ResolvedConfig) -> ProbeResult:
    """测试一项配置。web_search 抛 ProbeUnsupported；其余情况都返回 ProbeResult，不抛异常。"""
    try:
        result = await _probe(http, cfg)
    except httpx.InvalidURL:
        result = ProbeResult(False, "接口地址格式不正确")
    return ProbeResult(result.ok, redact(result.message, cfg.api_key))
