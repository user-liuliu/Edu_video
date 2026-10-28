"""Whole-film mp4 export of a studio film: renderFrame + PNG screenshot per frame, piped to
ffmpeg with the same encoder settings as ``app.videos.direct_render.render_direct``.

Fails closed: any ``studioDiagnostics`` entry or page error (a segment that failed to build
or paint draws nothing), or a page that stops answering, raises ``StudioRuntimeError``
instead of exporting a film with blank stretches.
"""
from __future__ import annotations

import asyncio
import contextlib
import math
from pathlib import Path
import subprocess
import tempfile

from app.studio.render_contract import (RenderRequest, StudioRuntimeError, check_film, decode_audio,
                                        film_data)

ENCODE_TIMEOUT = 60  # s, after the last frame

# Draw one frame; return the diagnostics that appeared while drawing it.
_FRAME = '''(t) => {
  const before = window.studioDiagnostics.length;
  window.renderFrame(t);
  return window.studioDiagnostics.slice(before).map((d) => d.message);
}'''


def encoder_command(ffmpeg: str, fps: int, audio: Path, duration: float, output: Path) -> list[str]:
    # Same parameters as render_direct (without its sprite credit metadata).
    return [ffmpeg, '-y', '-hide_banner', '-loglevel', 'error', '-f', 'image2pipe', '-vcodec', 'png',
            '-r', str(fps), '-i', '-', '-i', str(audio), '-map', '0:v:0', '-map', '1:a:0',
            '-t', str(duration), '-c:v', 'libx264', '-preset', 'fast', '-crf', '21',
            '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-movflags', '+faststart', str(output)]


def frame_count(duration: float, fps: int) -> int:
    return math.ceil(duration * fps - 1e-6)


async def _frames(req: RenderRequest, process) -> None:
    from app.studio.inspect import diagnostic_issues, from_timeout
    from app.studio.page import StudioTimeout, bounded, film_needs_webgl, studio_page

    first_seen: dict[str, float] = {}
    t = None
    try:
        async with studio_page(req.html, width=req.width, height=req.height,
                               webgl=film_needs_webgl(req.html)) as (page, errors):
            async def refuse():
                diagnostics = await bounded(page, page.evaluate('window.studioDiagnostics'))
                if diagnostics or errors:
                    raise StudioRuntimeError(diagnostic_issues(diagnostics, list(errors), first_seen))
            await refuse()
            for frame in range(frame_count(req.duration, req.fps)):
                t = frame / req.fps
                fresh = await bounded(page, page.evaluate(_FRAME, t))
                if fresh or errors:
                    for message in fresh:
                        first_seen.setdefault(message, t)
                    await refuse()
                png = await bounded(page, page.screenshot(type='png'))
                await asyncio.to_thread(process.stdin.write, png)
    except StudioTimeout as error:
        error.t = t
        raise StudioRuntimeError(from_timeout(error)) from None


async def render_film(req: RenderRequest, output: Path, *, work_dir: Path | None = None) -> dict:
    """Encode the film to ``output``; returns ``videos.export.probe`` metadata.

    ``audio.wav`` and ``encoder.log`` go to ``work_dir`` when given (the renderer worker passes
    its request folder, which the service removes even when it kills the worker), otherwise
    to a temporary folder removed on return.
    """
    from app.videos.export import decode_check, executable, probe

    data = film_data(req.html)
    check_film(data, req.duration, (req.width, req.height))
    output = Path(output)
    scratch = (contextlib.nullcontext(str(work_dir)) if work_dir is not None
               else tempfile.TemporaryDirectory(prefix='ev-studio-'))
    with scratch as folder:
        audio = Path(folder) / 'audio.wav'
        audio.write_bytes(decode_audio(req.audio_base64))
        command = encoder_command(executable('ffmpeg'), req.fps, audio, req.duration, output)
        with open(Path(folder) / 'encoder.log', 'wb') as log:
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log)
            try:
                await _frames(req, process)
                process.stdin.close()
                if await asyncio.to_thread(process.wait, ENCODE_TIMEOUT):
                    raise ValueError('整片视频编码失败')
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                if process.stdin and not process.stdin.closed:
                    process.stdin.close()
    await asyncio.to_thread(decode_check, output)
    return await asyncio.to_thread(probe, output, (req.width, req.height))
