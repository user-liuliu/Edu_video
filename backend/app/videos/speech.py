import base64
import asyncio
import logging
import binascii
import json
import math
import unicodedata
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

MAX_AUDIO_BYTES = 20 * 1024 * 1024
NARRATION_PROTOCOL_VERSION = 2
NARRATION_INSTRUCTION = ('请使用参考音色，以自然、清晰、连贯的普通话朗读下面的正文。'
    '只生成一位讲述者的干声旁白，不要背景音乐、环境声、音效、笑声或其他额外声音，'
    '不要演唱，不要读出这些说明，不增删正文。正文：')


@dataclass(frozen=True)
class Narration:
    audio: bytes
    captions: list[dict]


def verified_captions(subtitle, text: str) -> list[dict]:
    if not isinstance(subtitle, dict) or not isinstance(subtitle.get('sentences'), list) or not subtitle['sentences']:
        raise ValueError('配音服务未返回有效字幕时间戳，不能自动安排动画')
    entries = []
    previous_end = 0.0
    for sentence in subtitle['sentences']:
        try:
            start, end = float(sentence['start_time']) / 1000, float(sentence['end_time']) / 1000
            content = sentence['text']
            if not isinstance(content, str) or not content.strip() or not all(map(math.isfinite, (start, end))) or not previous_end <= start < end <= 120:
                raise ValueError
        except (KeyError, TypeError, ValueError):
            raise ValueError('配音字幕时间戳无效或相互重叠') from None
        entries.append({'start': start, 'end': end, 'text': content})
        previous_end = end
    def spoken(value):
        return ''.join(c for c in value if not c.isspace() and not unicodedata.category(c).startswith('P'))
    if spoken(''.join(item['text'] for item in entries)) != spoken(text):
        raise ValueError('配音字幕与已确认讲稿不一致，请重新生成配音')
    return entries


async def synthesize_speech(config, text: str, http: httpx.AsyncClient, *, speaker: str | None = None) -> bytes:
    if config.base_url=='system://offline':
        from .system_speech import synthesize
        return (await synthesize(text,speaker=speaker)).audio
    if not text.strip() or len(text) > 2000:
        raise ValueError('单次配音讲稿长度不符合要求')
    audio, _ = await _synthesize(config, text, http, speaker=speaker)
    return audio


async def synthesize_narration(config, text: str, http: httpx.AsyncClient, *, speaker: str | None = None, instruction: str = '') -> Narration:
    if config.base_url=='system://offline':
        from .system_speech import synthesize
        return await synthesize(text,speaker=speaker,instruction=instruction)
    if not text.strip() or len(text) > 2000:
        raise ValueError('单次配音讲稿长度不符合要求')
    guidance = ('朗读表现参考（仅调整语气节奏，绝不朗读或改写正文）：'+instruction[:2000]+'。') if instruction else ''
    audio, subtitle = await _synthesize(config, guidance + NARRATION_INSTRUCTION + text, http, speaker=speaker,
        audio_config={'format': 'wav', 'sample_rate': 48000, 'enable_subtitle': True})
    return Narration(audio, verified_captions(subtitle, text))


async def _synthesize(config, text, http, *, speaker=None, audio_config=None):
    from app.outline.model_client import ModelCallError, _retry_delay
    for attempt in range(3):
        try:
            return await _synthesize_once(config,text,http,speaker=speaker,audio_config=audio_config)
        except ModelCallError as error:
            retry=error.category in ('timeout','connection','rate_limit','unavailable') and attempt<2
            logging.getLogger(__name__).warning('speech_request_failed status=%s category=%s retry=%s retry_count=%s',
                                               error.status_code,error.category,retry,attempt)
            if not retry:raise
            await asyncio.sleep(getattr(error,'retry_delay',None) or _retry_delay(None,attempt))


async def _synthesize_once(config, text, http, *, speaker=None, audio_config=None):
    from app.outline.model_client import ModelCallError, _http_failure, _retry_delay
    voices = [v.get('speaker_id') for v in config.extra.get('voices', []) if isinstance(v, dict)]
    speaker = speaker or (voices[0] if voices else None)
    if not speaker or speaker not in voices:
        raise ValueError('所选配音音色已不可用，请重新选择')
    if not text.strip() or len(text) > 3000:
        raise ValueError('单次配音讲稿长度不符合要求')
    base = config.base_url.rstrip('/')
    path = '/api/v3/tts/create'
    url = base if urlsplit(base).path.endswith(path) else base + path
    payload = {
            'model': config.model, 'text_prompt': text, 'references': [{'speaker': speaker}],
    }
    if audio_config is not None:
        payload['audio_config'] = audio_config
    subtitle = None
    try:
        async with http.stream('POST', url, headers={'X-Api-Key': config.api_key}, json=payload, timeout=150, follow_redirects=False) as response:
            if not response.is_success:
                await response.aread()
                error=_http_failure(response)
                error.retry_delay=_retry_delay(response,0) if response.headers.get('Retry-After') else None
                raise error
            chunks = bytearray()
            async for chunk in response.aiter_bytes():
                chunks.extend(chunk)
                if len(chunks) > MAX_AUDIO_BYTES * 2:
                    raise ValueError('配音返回音频过大')
            content_type = response.headers.get('content-type', '').split(';')[0]
            if content_type.startswith('audio/') or content_type == 'application/octet-stream':
                audio = bytes(chunks)
            else:
                body = json.loads(chunks)
                if not isinstance(body, dict) or body.get('code') not in (None, 0, 20000000):
                    raise ValueError('配音服务未成功生成音频，请检查配音权限与参数')
                data = body.get('data', {})
                subtitle = data.get('subtitle', body.get('subtitle')) if isinstance(data, dict) else body.get('subtitle')
                encoded = data.get('audio') if isinstance(data, dict) else data
                encoded = encoded or body.get('audio')
                if not isinstance(encoded, str):
                    raise ValueError('配音服务未返回可用音频')
                audio = base64.b64decode(encoded, validate=True)
    except httpx.TimeoutException:
        raise ModelCallError('配音服务请求超时，请稍后重试',category='timeout') from None
    except httpx.HTTPError:
        raise ModelCallError('配音服务连接失败，请稍后重试',category='connection') from None
    except (binascii.Error, KeyError, TypeError, json.JSONDecodeError):
        raise ValueError('配音服务返回音频无效或连接失败') from None
    if not audio or len(audio) > MAX_AUDIO_BYTES:
        raise ValueError('配音服务返回音频为空或过大')
    return audio, subtitle
