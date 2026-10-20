import base64
import io
import wave
from pathlib import Path
import httpx
import pytest
from test_direct_html import HTML
from app.videos.direct_html import direct_digest

def payload():
    wav=io.BytesIO()
    with wave.open(wav,'wb') as w:
        w.setparams((1,2,48000,0,'NONE','not compressed'));w.writeframes(bytes(96000))
    return {'compiler_digest':direct_digest(),'html':HTML,'audio_base64':base64.b64encode(wav.getvalue()).decode(),
            'manifest':{'duration':1.,'source_duration':1.,'clock':[{'t':0.,'source':0.},{'t':1.,'source':1.}],'captions':[]}}

def test_export_probe_requires_both_codecs_and_dimensions():
    from app.videos.export import validate_probe
    valid={'streams':[{'codec_type':'video','codec_name':'h264','width':1280,'height':720},{'codec_type':'audio','codec_name':'aac'}],'format':{'duration':'1.0'}}
    assert validate_probe(valid,(1280,720))['duration']==1.
    for value,size in [(dict(valid,streams=valid['streams'][:1]),(1280,720)),(valid,(720,1280)),(dict(valid,format={'duration':'NaN'}),(1280,720))]:
        with pytest.raises(ValueError):validate_probe(value,size)

@pytest.mark.parametrize('mode',['size','missing','runtime','mismatch'])
async def test_direct_client_rejects_invalid_output(mode):
    from app.videos.render_client import RendererClient
    from app.videos.render_contract import DirectHtmlRuntimeError
    body={'mp4_base64':base64.b64encode(b'film').decode(),'metadata':{'width':720,'height':1280,'duration':1}}
    response=httpx.Response(200,json=body if mode=='size' else {})
    if mode=='runtime':response=httpx.Response(422,json={'detail':{'code':'direct_runtime','message':'无法倒退定位'}})
    if mode=='mismatch':response=httpx.Response(409,json={'detail':'版本不一致'})
    p=payload()
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req:response)) as http:
        with pytest.raises(DirectHtmlRuntimeError if mode=='runtime' else ValueError):
            await RendererClient(type('S',(),{'renderer_url':'http://renderer'})(),http).direct(p['html'],p['manifest'],base64.b64decode(p['audio_base64']),(1280,720))

async def test_busy_renderer_waits_with_bounded_deadline(monkeypatch):
    from app.videos.render_client import RendererClient
    p=payload();responses=iter([httpx.Response(429),httpx.Response(200,json={'validated':True})])
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req:next(responses))) as http:
        assert await RendererClient(type('S',(),{'renderer_url':'http://renderer'})(),http).direct(p['html'],p['manifest'],base64.b64decode(p['audio_base64']),(1280,720),validate=True)=={'validated':True}
    monkeypatch.setattr('app.videos.render_client.QUEUE_TIMEOUT',0)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req:httpx.Response(429))) as http:
        with pytest.raises(ValueError,match='等待超时'):
            await RendererClient(type('S',(),{'renderer_url':'http://renderer'})(),http).direct(p['html'],p['manifest'],base64.b64decode(p['audio_base64']),(1280,720),validate=True)

async def test_renderer_removes_old_endpoints_and_rejects_digest_before_launch(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2]))
    from renderer import app as service
    async def forbidden(*args,**kwargs):raise AssertionError('No worker should start')
    monkeypatch.setattr(service.asyncio,'create_subprocess_exec',forbidden)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=service.app),base_url='http://renderer') as http:
        for operation in ('render','validate','assemble'):
            assert (await http.post('/'+operation,json={})).status_code==404
        for operation in ('render-html','validate-html'):
            assert (await http.post('/'+operation,json={**payload(),'compiler_digest':'0'*64})).status_code==409

async def test_renderer_timeout_stops_worker_before_task_cleanup(monkeypatch):
    import asyncio
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2]))
    from renderer import app as service
    folders=[]
    class Process:
        returncode=None
        async def wait(self):await asyncio.Event().wait()
    process=Process()
    async def launch(*args,**kwargs):folders.append(Path(args[-1]));return process
    async def stop(child):
        assert child is process and folders[0].exists();child.returncode=-9
    monkeypatch.setattr(service,'RENDER_TIMEOUT',.01)
    monkeypatch.setattr(service.asyncio,'create_subprocess_exec',launch)
    monkeypatch.setattr(service,'terminate_process',stop)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=service.app),base_url='http://renderer') as http:
        assert (await http.post('/render-html',json=payload())).status_code==504
    assert not folders[0].exists() and not service.busy

async def test_validate_endpoint_returns_only_checks(monkeypatch):
    import json
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2]))
    from renderer import app as service
    operations=[]
    class Process:
        returncode=0
        async def wait(self):return 0
    async def launch(*args,**kwargs):
        operations.append(args[-2]);folder=Path(args[-1]);(folder/'metadata.json').write_text(json.dumps({'validated':True}));return Process()
    async def stop(*args):pass
    monkeypatch.setattr(service.asyncio,'create_subprocess_exec',launch);monkeypatch.setattr(service,'terminate_process',stop)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=service.app),base_url='http://renderer') as http:
        r=await http.post('/validate-html',json=payload())
    assert r.status_code==200 and r.json()=={'validated':True} and operations==['validate-html'] and not service.busy
