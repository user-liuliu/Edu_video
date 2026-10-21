"""Expression streaming at the real HTTP boundary; no provider calls."""
import copy
import json
from types import SimpleNamespace

import httpx
import pytest

from app.outline.model_client import ModelCallError
from app.purposes import Purpose
from app.videos.expression import build_expression
from test_film_expression import source, targets, response

CONFIG=SimpleNamespace(base_url='https://test.invalid/v1',model='writer',api_key='private-test-key',purpose=Purpose.outline_llm)


@pytest.fixture(autouse=True)
def no_wait(monkeypatch):
    monkeypatch.setattr('app.outline.model_client._retry_delay',lambda *args:0)


class Chunks(httpx.AsyncByteStream):
    def __init__(self,data):self.data=data
    async def __aiter__(self):
        for index in range(0,len(self.data),7):yield self.data[index:index+7]


def streamed(value, *, complete=True, finish='stop'):
    text=json.dumps(value,ensure_ascii=False)
    body=': heartbeat\n\n'
    for index in range(0,len(text),13):
        body+='data: '+json.dumps({'choices':[{'index':0,'delta':{'content':text[index:index+13]},'finish_reason':None}]},ensure_ascii=False)+'\r\n\r\n'
    if complete:
        body+='data: '+json.dumps({'choices':[{'index':0,'delta':{},'finish_reason':finish}]})+'\n\ndata: [DONE]'
    return httpx.Response(200,headers={'Content-Type':'text/event-stream'},stream=Chunks(body.encode()))


async def test_expression_stream_assembles_complete_json_before_validation():
    requests=[]
    def handle(req):requests.append(json.loads(req.content));return streamed(response())
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        result=await build_expression(CONFIG,source(),targets(),http)
    assert result['segments'][0]['outline_segment_id']=='section-1'
    assert result['segments'][0]['narration']==response()['segments'][0]['narration']
    assert len(requests)==1 and requests[0]['stream'] is True
    assert requests[0]['response_format']['type']=='json_schema'


@pytest.mark.parametrize('fault',[524,502,429,'timeout','disconnect','incomplete'])
async def test_expression_transient_faults_can_recover_on_third_retry(fault):
    requests=[]
    def handle(req):
        requests.append(req.content)
        if len(requests)==4:return streamed(response())
        if fault=='timeout':raise httpx.ReadTimeout('private-test-key',request=req)
        if fault=='disconnect':raise httpx.RemoteProtocolError('private-test-key',request=req)
        if fault=='incomplete':return streamed(response(),complete=False)
        return httpx.Response(fault)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        result=await build_expression(CONFIG,source(),targets(),http)
    assert result['segments'][0]['id']=='seg-1'
    assert len(requests)==4 and len(set(requests))==1


async def test_expression_524_exhaustion_is_bounded_and_does_not_start_format_correction(caplog):
    requests=[]
    def handle(req):requests.append(req.content);return httpx.Response(524,text='private-test-key')
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        with pytest.raises(ModelCallError) as caught:await build_expression(CONFIG,source(),targets(),http)
    assert caught.value.category=='timeout' and caught.value.status_code==524
    assert len(requests)==4 and len(set(requests))==1
    assert 'private-test-key' not in str(caught.value)+caplog.text


@pytest.mark.parametrize('status',[400,401,403])
async def test_expression_stream_does_not_retry_permanent_provider_errors(status):
    requests=[]
    def handle(req):requests.append(req.content);return httpx.Response(status)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        with pytest.raises(ModelCallError) as caught:await build_expression(CONFIG,source(),targets(),http)
    assert caught.value.status_code==status and len(requests)==1


async def test_expression_schema_fallback_keeps_streaming():
    requests=[]
    def handle(req):
        requests.append(json.loads(req.content))
        if len(requests)==1:return httpx.Response(400,json={'error':{'message':'response_format json_schema is not supported'}})
        return streamed(response())
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        await build_expression(CONFIG,source(),targets(),http)
    assert [r['response_format']['type'] for r in requests]==['json_schema','json_object']
    assert all(r['stream'] is True for r in requests)


@pytest.mark.parametrize('change',['formula','mapping'])
async def test_expression_stream_still_rejects_changed_facts_and_segment_mapping(change):
    bad=copy.deepcopy(response())
    if change=='mapping':bad['segments'][0]['id']='wrong-id'
    else:
        bad['visual_prompt']='坐标轴'
        bad['segments'][0].update(narration='观察直线。',visual_prompt='直线')
    requests=[]
    def handle(req):requests.append(req.content);return streamed(bad)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        with pytest.raises(ValueError,match='结构|公式'):await build_expression(CONFIG,source(),targets(),http)
    assert len(requests)==2


async def test_expression_transport_budget_does_not_reset_after_invalid_json():
    requests=[]
    def handle(req):
        requests.append(req.content)
        if len(requests)==2:
            return httpx.Response(200,json={'choices':[{'message':{'content':'invalid json'}}]})
        return httpx.Response(524)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        with pytest.raises(ModelCallError):await build_expression(CONFIG,source(),targets(),http)
    assert len(requests)==5
@pytest.mark.parametrize('finish,category',[('length','output_limit'),('content_filter','invalid_request')])
async def test_expression_stream_finish_errors_stop_without_retry(finish,category):
    requests=[]
    def handle(req):requests.append(req.content);return streamed(response(),finish=finish)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        with pytest.raises(ModelCallError) as caught:await build_expression(CONFIG,source(),targets(),http)
    assert caught.value.category==category and len(requests)==1
    assert '讲稿' in str(caught.value) and 'HTML' not in str(caught.value)


async def test_expression_persistently_incomplete_stream_never_returns_partial_script():
    requests=[]
    def handle(req):requests.append(req.content);return streamed(response(),complete=False)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        with pytest.raises(ModelCallError) as caught:await build_expression(CONFIG,source(),targets(),http)
    assert caught.value.category=='connection' and len(requests)==4


async def test_expression_stream_compatible_json_response_still_gets_format_correction():
    requests=[]
    def handle(req):
        requests.append(json.loads(req.content))
        content='invalid' if len(requests)==1 else json.dumps(response())
        return httpx.Response(200,json={'choices':[{'message':{'content':content}}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        result=await build_expression(CONFIG,source(),targets(),http)
    assert result['segments'][0]['outline_segment_id']=='section-1'
    assert len(requests)==2 and all(r['stream'] is True for r in requests)
    assert len(requests[1]['messages'])==len(requests[0]['messages'])+1
