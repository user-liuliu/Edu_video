"""Whole-film mp4 export of a studio film: renderFrame + PNG screenshot per frame, piped to
ffmpeg with the same encoder settings as ``app.videos.direct_render.render_direct``."""
from __future__ import annotations

import asyncio
import math
from pathlib import Path
import subprocess
import tempfile

from app.studio.render_contract import RenderRequest, check_film, decode_audio, film_data

ENCODE_TIMEOUT = 60  # s, after the last frame


def encoder_command(ffmpeg: str, fps: int, audio: Path, duration: float, output: Path) -> list[str]:
    # Same parameters as render_direct (without its sprite credit metadata).
    return [ffmpeg, '-y', '-hide_banner', '-loglevel', 'error', '-f', 'image2pipe', '-vcodec', 'png',
            '-r', str(fps), '-i', '-', '-i', str(audio), '-map', '0:v:0', '-map', '1:a:0',
            '-t', str(duration), '-c:v', 'libx264', '-preset', 'fast', '-crf', '21',
            '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-movflags', '+faststart', str(output)]


def frame_count(duration: float, fps: int) -> int:
    return math.ceil(duration * fps - 1e-6)


async def render_film(req: RenderRequest, output: Path) -> dict:
    """Encode the film to ``output``; returns ``videos.export.probe`` metadata, plus
    ``diagnostics`` (the runtime's list) when the film reported any while rendering."""
    from app.studio.page import studio_page
    from app.videos.export import decode_check, executable, probe

    data = film_data(req.html)
    check_film(data, req.duration, (req.width, req.height))
    output = Path(output)
    with tempfile.TemporaryDirectory(prefix='ev-studio-') as folder:
        audio = Path(folder) / 'audio.wav'
        audio.write_bytes(decode_audio(req.audio_base64))
        command = encoder_command(executable('ffmpeg'), req.fps, audio, req.duration, output)
        with open(Path(folder) / 'encoder.log', 'wb') as log:
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log)
            try:
                async with studio_page(req.html, width=req.width, height=req.height) as (page, errors):
                    for frame in range(frame_count(req.duration, req.fps)):
                        await page.evaluate('t => window.renderFrame(t)', frame / req.fps)
                        png = await page.screenshot(type='png')
                        await asyncio.to_thread(process.stdin.write, png)
                    diagnostics = await page.evaluate('window.studioDiagnostics')
                    diagnostics += [{'segment': None, 'message': f'页面脚本出错：{e[:500]}'}
                                    for e in dict.fromkeys(errors)]
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
    metadata = await asyncio.to_thread(probe, output, (req.width, req.height))
    if diagnostics:
        metadata['diagnostics'] = diagnostics
    return metadata
