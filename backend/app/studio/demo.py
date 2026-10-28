"""End-to-end demo film of the studio pipeline: real Edge narration, inspect, render.

    python -m app.studio.demo --voice edge:zh-CN-YunxiNeural --out <folder>

The three segments are hand-written fixtures in ``tests/fixtures/studio/demo``: ``film.json``
holds each segment's narration, hand-written word timings (for offline checks), highlights,
start/end states and the seams; ``seg_*.js`` the segment code; ``characters.js`` the
characters. ``build_demo`` voices every narration first and uses the real word timings and the
real audio length instead of the fixture's, so the picture lines up with the voice.

``app.studio.speech`` (edge_tts) is imported only when the real voice is used: the renderer
image loads this module for its checks without edge_tts.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import time
from pathlib import Path

from app.studio.contract import Seam, Segment
from app.studio.film import FilmError, assemble_audio, build_film_html, film_duration
from app.studio.render_client import StudioRenderError
from app.studio.render_contract import InspectRequest, RenderRequest
from app.studio.runtime.assets import runtime_digest
from app.studio.words import Word, align_words, cue

FIXTURES = Path(__file__).resolve().parents[2] / 'tests' / 'fixtures' / 'studio' / 'demo'
CHECKS = ['determinism', 'bounds', 'overlap', 'highlights', 'geometry', 'states']
STYLE = '.edu-stage{background:#fdfaf3}'
DEFAULT_VOICE = 'edge:zh-CN-YunxiNeural'


def fixture_words(narration: str, words: list) -> list[Word]:
    """``[text, start, end]`` triples (seconds) placed on the narration's characters."""
    events = [{'offset': round(start * 1e7), 'duration': round((end - start) * 1e7), 'text': text}
              for text, start, end in words]
    return align_words(narration, events)


def load_film(folder: Path = FIXTURES) -> tuple[list[Segment], list[Seam], str]:
    """The demo's segments (with the fixture's hand-written timings), seams and characters code."""
    folder = Path(folder)
    data = json.loads((folder / 'film.json').read_text(encoding='utf-8'))
    segments = [Segment(id=s['id'], code=(folder / s['code']).read_text(encoding='utf-8'),
                        duration=s['duration'], words=fixture_words(s['narration'], s['words']),
                        narration=s['narration'], highlights=s['highlights'],
                        start_state=s['start_state'], end_state=s['end_state'])
                for s in data['segments']]
    seams = [Seam.model_validate(s) for s in data['seams']]
    return segments, seams, (folder / 'characters.js').read_text(encoding='utf-8')


def demo_html(segments: list[Segment], seams: list[Seam], characters: str) -> str:
    return build_film_html(segments, seams, characters_code=characters, style_css=STYLE)


def _issue_lines(issues) -> str:
    def when(t):
        return '' if t is None else f'{t:.2f} 秒'
    return '\n'.join(f'- 第 {i.segment or "-"} 段 {when(i.t)} [{i.code}] {i.element or "-"}：{i.message}'
                     for i in issues)


async def build_demo(voice: str, out: Path, *, synthesize=None, renderer) -> Path:
    """Voice, assemble, inspect (all checks) and render the demo film into ``out``.

    Writes ``demo.html`` (always), ``demo.mp4`` and ``demo.json`` (timings and highlight cues).
    Any inspect issue, or runtime issues the renderer reports, raise ``FilmError`` listing them."""
    if synthesize is None:
        from app.studio.speech import synthesize_words as synthesize
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    fixture, seams, characters = load_film()

    started = time.monotonic()
    segments: list[Segment] = []
    clips: list[bytes] = []
    for segment in fixture:
        spoken = await synthesize(segment.narration, speaker=voice)
        segments.append(Segment.model_validate({**segment.model_dump(), 'duration': spoken.duration,
                                                'words': spoken.words}))
        clips.append(spoken.audio)
    voice_seconds = time.monotonic() - started

    html = demo_html(segments, seams, characters)
    (out / 'demo.html').write_text(html, encoding='utf-8')
    audio = assemble_audio(clips, segments, seams)
    duration = film_duration(segments, seams)

    started = time.monotonic()
    result = await renderer.inspect(InspectRequest(runtime_digest=runtime_digest(), html=html, duration=duration,
                                                   frame_times=[], checks=CHECKS))
    inspect_seconds = time.monotonic() - started
    if result.issues:
        raise FilmError(f'演示片检查发现 {len(result.issues)} 个问题：\n{_issue_lines(result.issues)}')

    started = time.monotonic()
    try:
        rendered = await renderer.render(RenderRequest(runtime_digest=runtime_digest(), html=html,
                                                       audio_base64=base64.b64encode(audio).decode(),
                                                       duration=duration))
    except StudioRenderError as error:
        if error.issues:
            raise FilmError(f'演示片导出失败，{len(error.issues)} 个问题：\n{_issue_lines(error.issues)}') from None
        raise
    render_seconds = time.monotonic() - started

    path = out / 'demo.mp4'
    path.write_bytes(base64.b64decode(rendered['mp4_base64']))
    starts, cursor = {}, 0.0
    for index, segment in enumerate(segments):
        starts[segment.id] = cursor
        cursor += segment.duration + (seams[index].duration if index < len(seams) else 0)
    report = {
        'duration': duration,
        'metadata': rendered.get('metadata'),
        'seconds': {'voice': round(voice_seconds, 2), 'inspect': round(inspect_seconds, 2),
                    'render': round(render_seconds, 2)},
        'segments': [{'id': s.id, 'start': round(starts[s.id], 3), 'duration': s.duration,
                      'highlights': [{'phrase': h.phrase, 'target': h.target,
                                      'film_time': round(starts[s.id] + cue(s.words, s.narration, h.phrase,
                                                                            h.occurrence)[0], 3)}
                                     for h in s.highlights]}
                     for s in segments],
    }
    (out / 'demo.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
    return path


async def _main(voice: str, out: Path) -> None:
    import httpx
    from app.config import get_settings
    from app.studio.render_client import StudioRenderer

    async with httpx.AsyncClient() as http:
        path = await build_demo(voice, out, renderer=StudioRenderer(get_settings(), http))
    report = json.loads((out / 'demo.json').read_text(encoding='utf-8'))
    print(f'demo: {path}')
    print(f'duration: {report["duration"]:.3f} s; seconds: {report["seconds"]}')
    for segment in report['segments']:
        for h in segment['highlights']:
            print(f'highlight {segment["id"]} "{h["phrase"]}" -> {h["target"]} at {h["film_time"]:.3f} s')


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description='生成 studio 端到端演示片')
    parser.add_argument('--voice', default=DEFAULT_VOICE)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    asyncio.run(_main(args.voice, args.out))


if __name__ == '__main__':
    main()
