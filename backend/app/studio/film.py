"""Whole-film assembly: timeline, HTML page, audio track and captions.

Pure stdlib/pydantic plus ``app.studio.words``; the renderer image imports this module
without edge_tts, so nothing here may import ``app.studio.speech``.
"""
from __future__ import annotations

import io
import json
import re
import wave
from dataclasses import asdict

from app.studio.contract import Seam, Segment, state_diff
from app.studio.lint import lint_segment
from app.studio.runtime.assets import runtime_url
from app.studio.words import sentence_captions

CSP = ("default-src 'none'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
       "font-src 'self'; img-src data:; connect-src 'none'")
VENDOR_STYLES = ('katex.min.css', 'fonts.css')
# GSAP core must load before its plugins.
RUNTIME_SCRIPTS = ('gsap.min.js', 'DrawSVGPlugin.min.js', 'MorphSVGPlugin.min.js',
                   'MotionPathPlugin.min.js', 'SplitText.min.js', 'katex.min.js', 'three.iife.js',
                   'rough.js', 'edu_motion.js', 'film_runtime.js')
AUDIO_TOLERANCE = 1 / 30
_SCRIPT_BREAKOUT = re.compile(r'</script|<!--', re.IGNORECASE)
_STYLE_BREAKOUT = re.compile(r'</style|<!--', re.IGNORECASE)


class FilmError(ValueError):
    pass


def _check_counts(segments: list[Segment], seams: list[Seam]) -> None:
    if not segments:
        raise FilmError('整片至少需要一段')
    if len(seams) != len(segments) - 1:
        raise FilmError(f'{len(segments)} 段需要 {len(segments) - 1} 个接缝，实际有 {len(seams)} 个')


def timeline(segments: list[Segment], seams: list[Seam]) -> list[dict]:
    """Segments and the seam gaps between them, in time order."""
    _check_counts(segments, seams)
    items: list[dict] = []
    cursor = 0.0
    for index, segment in enumerate(segments):
        end = cursor + segment.duration
        items.append({'id': segment.id, 'start': round(cursor, 6), 'end': round(end, 6)})
        cursor = end
        if index < len(seams):
            seam = seams[index]
            end = cursor + seam.duration
            items.append({'seam': index, 'start': round(cursor, 6), 'end': round(end, 6),
                          'kind': seam.kind, 'transition': seam.transition})
            cursor = end
    return items


def film_duration(segments: list[Segment], seams: list[Seam]) -> float:
    return timeline(segments, seams)[-1]['end']


def film_captions(segments: list[Segment], seams: list[Seam]) -> list[dict]:
    """Sentence captions with absolute film times."""
    starts = {item['id']: item['start'] for item in timeline(segments, seams) if 'id' in item}
    captions: list[dict] = []
    for segment in segments:
        offset = starts[segment.id]
        for caption in sentence_captions(segment.narration, segment.words):
            captions.append({'text': caption['text'], 'start': caption['start'] + offset,
                             'end': caption['end'] + offset})
    return captions


def _validate(segments: list[Segment], seams: list[Seam]) -> None:
    _check_counts(segments, seams)
    seen: set[str] = set()
    for segment in segments:
        if segment.id in seen:
            raise FilmError(f'段 id 重复：{segment.id}')
        seen.add(segment.id)
    for segment in segments:
        issues = lint_segment(segment.code)
        if _SCRIPT_BREAKOUT.search(segment.code):
            issues.append('</script 或 <!-- 不允许使用')
        if issues:
            raise FilmError(f'第 {segment.id} 段：' + '；'.join(issues))
    for index, seam in enumerate(seams):
        before, after = segments[index], segments[index + 1]
        if seam.duration > min(before.duration, after.duration) / 2 + 1e-9:
            raise FilmError(f'接缝 {index} 比相邻片段还长')
        if seam.kind == 'continue':
            diffs = state_diff(before.end_state, after.start_state)
            if diffs:
                raise FilmError(f'接缝 {index}（{before.id} 到 {after.id}）画面状态不连续：' + '；'.join(diffs))


def _json_block(data: dict) -> str:
    # `<` is escaped so narration text can never close the script element.
    return json.dumps(data, ensure_ascii=False).replace('<', '\\u003c')


def build_film_html(segments: list[Segment], seams: list[Seam], *, characters_code: str = '',
                    style_css: str = '', width: int = 1280, height: int = 720) -> str:
    _validate(segments, seams)
    if _SCRIPT_BREAKOUT.search(characters_code):
        raise FilmError('角色代码里不允许出现 </script 或 <!--')
    if _STYLE_BREAKOUT.search(style_css):
        raise FilmError('样式里不允许出现 </style 或 <!--')
    if not (isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0):
        raise FilmError('画布宽高必须是正整数')

    items = timeline(segments, seams)
    film = {
        'timeline': items,
        'duration': items[-1]['end'],
        'width': width,
        'height': height,
        'segments': [{
            'id': s.id,
            'duration': s.duration,
            'words': [asdict(w) for w in s.words],
            'narration': s.narration,
            'highlights': [h.model_dump(mode='json') for h in s.highlights],
            'start_state': s.start_state.model_dump(mode='json'),
            'end_state': s.end_state.model_dump(mode='json'),
        } for s in segments],
        'seams': [s.model_dump(mode='json') for s in seams],
        'captions': film_captions(segments, seams),
    }

    parts = [
        '<!DOCTYPE html>',
        '<html><head>',
        '<meta charset="utf-8">',
        f'<meta http-equiv="Content-Security-Policy" content="{CSP}">',
        *(f'<link rel="stylesheet" href="{runtime_url(name)}">' for name in VENDOR_STYLES),
        f'<style>html,body{{margin:0;padding:0;width:{width}px;height:{height}px;overflow:hidden}}</style>',
        f'<style>{style_css}</style>',
        '</head><body>',
        *(f'<script src="{runtime_url(name)}"></script>' for name in RUNTIME_SCRIPTS),
        f'<script>{characters_code}</script>',
        *(f'<script>EduStudio.defineSegment({json.dumps(s.id)}, function(ctx){{\n{s.code}\n}});</script>'
          for s in segments),
        f'<script type="application/json" id="edu-studio-film">{_json_block(film)}</script>',
        '<script>EduFilm.boot()</script>',  # last line; closing body/html tags are optional
    ]
    return '\n'.join(parts)


def _read_wav(data: bytes, segment: Segment) -> tuple[tuple[int, int, int], bytes, float]:
    try:
        with wave.open(io.BytesIO(data), 'rb') as source:
            params = (source.getnchannels(), source.getsampwidth(), source.getframerate())
            frames = source.readframes(source.getnframes())
            seconds = source.getnframes() / source.getframerate()
    except (wave.Error, EOFError, ZeroDivisionError):
        raise FilmError(f'第 {segment.id} 段配音不是有效的 WAV 音频') from None
    return params, frames, seconds


def assemble_audio(clips: list[bytes], segments: list[Segment], seams: list[Seam]) -> bytes:
    """Concatenate per-segment WAV clips, inserting silence as long as each seam."""
    _check_counts(segments, seams)
    if len(clips) != len(segments):
        raise FilmError(f'{len(segments)} 段需要 {len(segments)} 段配音，实际有 {len(clips)} 段')
    parsed: list[bytes] = []
    params: tuple[int, int, int] | None = None
    for clip, segment in zip(clips, segments):
        clip_params, frames, seconds = _read_wav(clip, segment)
        if abs(seconds - segment.duration) > AUDIO_TOLERANCE:
            raise FilmError(f'第 {segment.id} 段配音时长与动画不一致')
        if params is None:
            params = clip_params
        elif clip_params != params:
            raise FilmError(f'第 {segment.id} 段配音格式与前面的段不一致')
        parsed.append(frames)
    channels, width, rate = params
    out = io.BytesIO()
    with wave.open(out, 'wb') as target:
        target.setnchannels(channels)
        target.setsampwidth(width)
        target.setframerate(rate)
        for index, frames in enumerate(parsed):
            target.writeframes(frames)
            if index < len(seams) and seams[index].duration > 0:
                target.writeframes(bytes(1) * (round(seams[index].duration * rate) * channels * width))
    return out.getvalue()
