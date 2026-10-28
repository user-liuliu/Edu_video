"""Edge TTS narration with word-level timing for the studio pipeline."""
import asyncio
import io
import logging
import wave
from dataclasses import dataclass, replace

import aiohttp
import edge_tts
from edge_tts.exceptions import EdgeTTSException

from app.studio.words import Word, align_words, cue, sentence_captions
from app.videos.edge_speech import ATTEMPTS, MAX_STREAM_SECONDS, _decode, available
from app.videos.speech import MAX_AUDIO_BYTES

__all__ = ['VOICES', 'Word', 'WordNarration', 'align_words', 'cue', 'sentence_captions', 'synthesize_words']

VOICES = (
    {'speaker_id': 'edge:zh-CN-YunxiNeural', 'label': '云希·男声'},
    {'speaker_id': 'edge:zh-CN-XiaoxiaoNeural', 'label': '晓晓·女声'},
    {'speaker_id': 'edge:zh-CN-YunjianNeural', 'label': '云健·男声'},
    {'speaker_id': 'edge:zh-CN-XiaoyiNeural', 'label': '晓伊·女声'},
    {'speaker_id': 'edge:zh-CN-YunyangNeural', 'label': '云扬·男声'},
)
MAX_TEXT = 2000
MAX_EVENTS = 4000


@dataclass(frozen=True)
class WordNarration:
    audio: bytes
    duration: float
    words: list[Word]


async def _stream_words(text, voice, rate):
    audio, events = bytearray(), []
    async with asyncio.timeout(MAX_STREAM_SECONDS):
        communicate = edge_tts.Communicate(text, voice=voice, rate=rate,
            boundary='WordBoundary', connect_timeout=10, receive_timeout=30)
        async for item in communicate.stream():
            if item['type'] == 'audio':
                audio.extend(item['data'])
                if len(audio) > MAX_AUDIO_BYTES:
                    raise ValueError('系统配音音频过大')
            elif item['type'] == 'WordBoundary':
                events.append(item)
                if len(events) > MAX_EVENTS:
                    raise ValueError('系统配音逐词时间过多')
    if not audio:
        raise ValueError('系统配音未返回音频')
    return bytes(audio), events


async def synthesize_words(text, *, speaker, rate='-5%'):
    if not text.strip() or len(text) > MAX_TEXT:
        raise ValueError('单段旁白长度不符合要求')
    if speaker not in {v['speaker_id'] for v in VOICES}:
        raise ValueError('所选配音音色不可用，请重新选择')
    if not available():
        raise ValueError('系统配音组件不可用，请联系管理员')
    voice = speaker.removeprefix('edge:')
    for attempt in range(ATTEMPTS):
        try:
            data, events = await _stream_words(text, voice, rate)
            break
        except (aiohttp.ClientError, TimeoutError, EdgeTTSException):
            logging.getLogger(__name__).warning('studio_speech_request_failed attempt=%s', attempt + 1)
            if attempt == ATTEMPTS - 1:
                raise ValueError('配音服务暂时不可用，请稍后重试；已保留生成进度') from None
            await asyncio.sleep(1 + attempt)
    audio = await asyncio.to_thread(_decode, data)
    with wave.open(io.BytesIO(audio), 'rb') as source:
        duration = source.getnframes() / 48000
    # Edge can overshoot the audio end by a few milliseconds; keep times inside it.
    words = [replace(w, start=min(w.start, duration), end=min(w.end, duration))
             for w in align_words(text, events)]
    if not words:
        raise ValueError('配音未返回逐词时间，请重试')
    return WordNarration(audio, duration, words)
