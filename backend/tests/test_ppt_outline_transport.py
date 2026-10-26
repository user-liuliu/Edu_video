"""PPT outline HTTP boundary tests; no external model calls."""
import json
from unittest.mock import AsyncMock
import httpx
import pytest
from app.model_configs.schemas import ResolvedConfig
from app.purposes import Purpose
from app.presentations import generation
from app.outline.model_client import chat_json

CONFIG=ResolvedConfig(Purpose.outline_llm,'https://model.example/v1','private-key','outline-model',{})
OUTLINE={'slides':[{'layout':'title','title':'函数复习','content':'复习函数概念'}]}

class Chunks(httpx.AsyncByteStream):
    def __init__(self,data):self.data=data
    async def __aiter__(self):
        for offset in range(0,len(self.data),11):yield self.data[offset:offset+11]

def streamed(value,complete=True):
    newline=chr(10)
    body='data: '+json.dumps({'choices':[{'index':0,'delta':{'content':json.dumps(value,ensure_ascii=False)},'finish_reason':None}]},ensure_ascii=False)+newline*2
    if complete:body+='data: '+json.dumps({'choices':[{'index':0,'delta':{},'finish_reason':'stop'}]})+newline*2+'data: [DONE]'+newline*2
    return httpx.Response(200,headers={'Content-Type':'text/event-stream'},stream=Chunks(body.encode()))

@pytest.fixture
def no_wait(monkeypatch):
    monkeypatch.setattr('app.outline.model_client.asyncio.sleep',AsyncMock())

async def invoke(monkeypatch,client,payload):
    async def request(config,messages,**kwargs):return await chat_json(config,messages,client=client,**kwargs)
    monkeypatch.setattr(generation,'chat_json',request)
    return await generation.call(CONFIG,payload)

@pytest.mark.asyncio
@pytest.mark.parametrize('operation',['outline','rewrite'])
async def test_outline_streaming_avoids_buffered_gateway_timeout(monkeypatch,no_wait,operation):
    requests=[]
    def handle(request):
        payload=json.loads(request.content);requests.append(payload)
        return streamed(OUTLINE) if payload.get('stream') else httpx.Response(524)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        result=await invoke(monkeypatch,client,{'operation':operation,'requirement':'函数复习'})
    assert result==OUTLINE
    assert len(requests)==1
    assert requests[0]['stream'] is True

@pytest.mark.asyncio
@pytest.mark.parametrize('status,expected',[(524,'超时'),(401,'认证失败'),(429,'限额')])
async def test_outline_reports_safe_provider_reason_with_bounded_retry(monkeypatch,no_wait,caplog,status,expected):
    requests=[]
    def handle(request):
        requests.append(request)
        return httpx.Response(status,json={'error':{'message':'private-key private-material https://secret.example'}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(generation.GenerationError) as caught:
            await invoke(monkeypatch,client,{'operation':'outline','requirement':'private-material'})
    assert expected in str(caught.value)
    assert str(status) in str(caught.value)
    assert len(requests)==(1 if status==401 else 2)
    for secret in ['private-key','private-material','secret.example']:
        assert secret not in str(caught.value)+caplog.text

@pytest.mark.asyncio
async def test_outline_discards_incomplete_stream_and_retries_original_request(monkeypatch,no_wait):
    requests=[]
    def handle(request):
        requests.append(request.content)
        return streamed(OUTLINE,complete=len(requests)>1)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        assert await invoke(monkeypatch,client,{'operation':'outline'})==OUTLINE
    assert len(requests)==2 and requests[0]==requests[1]

@pytest.mark.asyncio
async def test_outline_persistent_incomplete_stream_returns_no_partial_outline(monkeypatch,no_wait):
    requests=[]
    def handle(request):
        requests.append(request)
        return streamed(OUTLINE,complete=False)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(generation.GenerationError,match='课件大纲.*中断'):
            await invoke(monkeypatch,client,{'operation':'outline'})
    assert len(requests)==2
