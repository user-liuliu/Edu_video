"""Request/response contract of the renderer's studio endpoints (/studio/inspect, /studio/render).

Pure pydantic/stdlib: imported both by the backend client and inside the renderer image.
"""
from __future__ import annotations

import base64
import binascii
import io
import json
import re
import wave
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.studio.contract import StageState

MAX_HTML = 4_000_000
MAX_FRAMES = 40
MAX_AUDIO_BASE64 = 196 * 1024 * 1024
MAX_AUDIO_BYTES = 140 * 1024 * 1024
MAX_DURATION = 7200.0
REVIEW_SIZE = (640, 360)  # inspect frames are downscaled to this for the vision review
DURATION_TOLERANCE = 1 / 30

Check = Literal['determinism', 'bounds', 'overlap', 'highlights', 'geometry', 'states']
Seconds = Annotated[float, Field(allow_inf_nan=False)]
_FILM_BLOCK = re.compile(r'<script type="application/json" id="edu-studio-film">(.*?)</script>', re.S)


class StudioInputError(ValueError):
    """The request does not describe the film it carries (duration, size, missing block)."""


class _Model(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class InspectRequest(_Model):
    runtime_digest: str = Field(pattern=r'^[0-9a-f]{64}$')
    html: str = Field(max_length=MAX_HTML)
    duration: Seconds = Field(gt=0, le=MAX_DURATION)
    frame_times: list[Seconds] = Field(max_length=MAX_FRAMES)
    checks: list[Check]

    @model_validator(mode='after')
    def _frames_inside_film(self):
        for t in self.frame_times:
            if not 0 <= t <= self.duration:
                raise ValueError(f'截帧时间 {t:g} 秒不在 0 到 {self.duration:g} 秒之间')
        return self


class Issue(_Model):
    code: str
    segment: str | None
    t: float | None
    element: str | None
    message: str


class Frame(_Model):
    t: float
    png_base64: str


class SegmentStates(_Model):
    start: StageState
    end: StageState


class InspectResult(_Model):
    issues: list[Issue]
    frames: list[Frame]
    states: dict[str, SegmentStates]


def decode_audio(value: str) -> bytes:
    try:
        data = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error):
        raise ValueError('音轨数据不是有效的 base64') from None
    if not data or len(data) > MAX_AUDIO_BYTES:
        raise ValueError('音轨大小超出范围')
    return data


class RenderRequest(_Model):
    runtime_digest: str = Field(pattern=r'^[0-9a-f]{64}$')
    html: str = Field(max_length=MAX_HTML)
    audio_base64: str = Field(max_length=MAX_AUDIO_BASE64)
    duration: Seconds = Field(gt=0, le=MAX_DURATION)
    width: int = Field(default=1280, ge=240, le=1920)
    height: int = Field(default=720, ge=240, le=1920)
    fps: int = Field(default=30, ge=1, le=30)

    @model_validator(mode='after')
    def _valid_media(self):
        if self.width % 2 or self.height % 2:
            raise ValueError('视频尺寸必须为偶数')
        data = decode_audio(self.audio_base64)
        try:
            with wave.open(io.BytesIO(data), 'rb') as audio:
                seconds = audio.getnframes() / audio.getframerate()
                compressed = audio.getcomptype() != 'NONE'
        except (wave.Error, EOFError, ZeroDivisionError):
            raise ValueError('音轨不是有效的 WAV 音频') from None
        if compressed or abs(seconds - self.duration) > DURATION_TOLERANCE:
            raise ValueError(f'音轨时长 {seconds:.3f} 秒与整片时长 {self.duration:g} 秒不一致')
        return self


def film_data(html: str) -> dict:
    """The ``#edu-studio-film`` JSON block that ``build_film_html`` wrote into the page."""
    match = _FILM_BLOCK.search(html)
    if not match:
        raise StudioInputError('页面里没有 #edu-studio-film 数据块，请用 build_film_html 生成整片')
    try:
        data = json.loads(match.group(1))
        for key in ('timeline', 'segments', 'seams', 'duration', 'width', 'height'):
            data[key]
    except (ValueError, KeyError, TypeError):
        raise StudioInputError('#edu-studio-film 数据块无效') from None
    return data


def check_film(data: dict, duration: float, size: tuple[int, int] | None = None) -> None:
    """The request's duration (and frame size) must be the film's own."""
    if abs(float(data['duration']) - duration) > 1e-3:
        raise StudioInputError(f'请求里的时长 {duration:g} 秒与整片时长 {data["duration"]:g} 秒不一致')
    if size is not None and (data['width'], data['height']) != size:
        raise StudioInputError(f'请求的画面尺寸 {size[0]}×{size[1]} 与整片尺寸 '
                               f'{data["width"]}×{data["height"]} 不一致')
