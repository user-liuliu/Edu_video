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
# 走 OpenAI 兼容接口的用途：地址通常以 /v1 结尾
_OPENAI_PURPOSES = _CHAT_PURPOSES | {Purpose.embedding, Purpose.image_gen}
_V1_HINT = "。接口地址可能不完整：OpenAI 兼容接口通常以 /v1 结尾"


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


def _missing_v1(base_url: str) -> bool:
    """地址路径里没有 /v1 这一段（例如只填了域名 https://example.com）。"""
    return "v1" not in urlsplit(base_url).path.split("/")


def _http_error(resp: httpx.Response, purpose: Purpose, cfg: ResolvedConfig) -> ProbeResult:
    preview = _preview(resp.text, cfg.api_key)
    message = f"HTTP {resp.status_code}：{preview}" if preview else f"HTTP {resp.status_code}"
    # 只提示，不自动补 /v1：有的服务地址本来就不带 /v1
    if purpose in _OPENAI_PURPOSES and resp.status_code in (404, 405) and _missing_v1(cfg.base_url):
        message += _V1_HINT
    return ProbeResult(False, message)


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
        method, path, headers = "POST", "chat/completions", bearer
        body = {"model": cfg.model, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1}
    elif purpose == Purpose.embedding:
        method, path, headers = "POST", "embeddings", bearer
        body = {"model": cfg.model, "input": "ping"}
    elif purpose == Purpose.image_gen:
        # 只查模型列表，不真的生成图片（生成要花钱）
        method, path, headers, body = "GET", "models", bearer, None
    elif purpose == Purpose.tts:
        voice = _first_voice(cfg.extra)
        if voice is None:
            return ProbeResult(False, "请先配置至少一个音色")
        method, path, headers = "POST", "api/v3/tts/create", {"X-Api-Key": cfg.api_key}
        body = {"model": cfg.model, "text_prompt": "测试", "speaker": voice.speaker_id}
    else:
        raise ProbeUnsupported(purpose.value)

    url = join_url(cfg.base_url, path)
    # 构造请求也放进 try：地址或请求头不合法时 build_request 本身就会抛错
    try:
        request = http.build_request(method, url, headers=headers, json=body)
        resp = await http.send(request)
    except httpx.TimeoutException:
        return ProbeResult(False, "连接超时")
    except httpx.TransportError:
        return ProbeResult(False, f"无法连接到 {urlsplit(url).hostname or url}")
    except httpx.InvalidURL:
        return ProbeResult(False, "接口地址格式不正确")
    except (httpx.HTTPError, ValueError) as e:
        # 其他请求错误（例如响应解码失败）：只给异常类名，异常内容可能带 key
        return ProbeResult(False, f"请求失败：{type(e).__name__}")

    if not resp.is_success:
        return _http_error(resp, purpose, cfg)
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
