"""Subprocess for the studio endpoints: ``python -m renderer.studio_worker inspect|render <folder>``.

Reads ``request.json`` and writes ``result.json`` (inspect) or ``output.mp4`` +
``metadata.json`` (render). A request that does not match its own film writes
``error.json`` with code ``studio_input`` and exits 2.
"""
import asyncio
import json
from pathlib import Path
import sys

from app.studio.render_contract import InspectRequest, RenderRequest, StudioInputError


async def run(operation, folder):
    from .resources import limit_cpu_affinity
    limit_cpu_affinity()
    folder = Path(folder)
    data = (folder / 'request.json').read_bytes()
    if operation == 'inspect':
        from app.studio.inspect import inspect_film
        result = await inspect_film(InspectRequest.model_validate_json(data))
        (folder / 'result.json').write_text(result.model_dump_json(), encoding='utf-8')
    elif operation == 'render':
        from app.studio.export import render_film
        metadata = await render_film(RenderRequest.model_validate_json(data), folder / 'output.mp4')
        (folder / 'metadata.json').write_text(json.dumps(metadata, ensure_ascii=False), encoding='utf-8')
    else:
        raise ValueError('Unsupported operation')


if __name__ == '__main__':
    try:
        asyncio.run(run(sys.argv[1], sys.argv[2]))
    except StudioInputError as error:
        (Path(sys.argv[2]) / 'error.json').write_text(
            json.dumps({'code': 'studio_input', 'message': str(error)[:500]}, ensure_ascii=False), encoding='utf-8')
        raise SystemExit(2)
