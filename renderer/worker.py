import asyncio
import json
from pathlib import Path
import sys
from app.videos.render_contract import DirectRenderRequest,DirectHtmlRuntimeError
from app.videos.checked_render import validate_direct,render_direct

async def run(operation,folder):
    from .resources import limit_cpu_affinity
    limit_cpu_affinity()
    folder=Path(folder)
    request=DirectRenderRequest.model_validate_json((folder/'request.json').read_bytes())
    if operation=='validate-html':metadata=await validate_direct(request)
    elif operation=='render-html':metadata=await render_direct(request,folder/'output.mp4')
    else:raise ValueError('Unsupported operation')
    (folder/'metadata.json').write_text(json.dumps(metadata),encoding='utf-8')

if __name__=='__main__':
    try:asyncio.run(run(sys.argv[1],sys.argv[2]))
    except DirectHtmlRuntimeError as error:
        (Path(sys.argv[2])/'error.json').write_text(json.dumps({'code':'direct_runtime','message':str(error)[:500]}),encoding='utf-8')
        raise SystemExit(2)
