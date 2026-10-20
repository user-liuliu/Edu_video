import json
import logging
import httpx
import pytest
from app.outline.model_client import ModelCallError
from app.videos.direct_html import generate_html
from test_direct_html import HTML

CONFIG = type('Config', (), {'base_url': 'https://example.invalid/v1', 'api_key': 'private-key', 'model': 'test'})()

@pytest.fixture(autouse=True)
def no_retry_wait(monkeypatch):
    monkeypatch.setattr('app.outline.model_client._retry_delay', lambda *args: 0)

@pytest.mark.parametrize('fault', [httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError])
async def test_animation_recovers_once_from_transient_transport_failure(fault):
    calls = 0
    def handle(request):
        nonlocal calls
        calls += 1
        if calls == 1: raise fault('private-key and teacher material', request=request)
        return httpx.Response(200, json={'choices': [{'message': {'content': json.dumps({'html': HTML})}}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        assert await generate_html(CONFIG, {}, http) == HTML
    assert calls == 2

@pytest.mark.parametrize('status', [429, 502, 503, 504])
async def test_animation_recovers_once_from_transient_provider_failure(status):
    calls = 0
    def handle(request):
        nonlocal calls
        calls += 1
        if calls == 1: return httpx.Response(status, headers={'Retry-After': '0'}, json={'error': {'message': 'private-key'}})
        return httpx.Response(200, json={'choices': [{'message': {'content': json.dumps({'html': HTML})}}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        assert await generate_html(CONFIG, {}, http) == HTML
    assert calls == 2

async def test_persistent_animation_timeout_is_bounded_classified_and_logged_safely(caplog):
    calls = 0
    def handle(request):
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout('private-key and teacher material', request=request)
    with caplog.at_level(logging.WARNING):
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
            with pytest.raises(ModelCallError) as caught: await generate_html(CONFIG, {}, http)
    assert calls == 2
    assert caught.value.category == 'timeout'
    assert '超时' in str(caught.value)
    assert 'category=timeout' in caplog.text
    assert 'private-key' not in caplog.text + str(caught.value)
    assert 'teacher material' not in caplog.text + str(caught.value)

@pytest.mark.parametrize('status', [400, 401, 403])
async def test_animation_never_retries_permanent_provider_errors(status):
    calls = 0
    def handle(request):
        nonlocal calls
        calls += 1
        return httpx.Response(status, json={'error': {'message': 'private-key'}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        with pytest.raises(ModelCallError): await generate_html(CONFIG, {}, http)
    assert calls == 1

async def test_cut_off_sse_is_retried_without_treating_partial_html_as_complete():
    calls = 0
    def handle(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            event = {'choices': [{'delta': {'content': '{"html":"partial'}, 'finish_reason': None}]}
            return httpx.Response(200, text='data: ' + json.dumps(event) + '\n\n', headers={'Content-Type': 'text/event-stream'})
        assert len(json.loads(request.content)['messages']) == 2
        return httpx.Response(200, json={'choices': [{'message': {'content': json.dumps({'html': HTML})}}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        assert await generate_html(CONFIG, {}, http) == HTML
    assert calls == 2


@pytest.mark.parametrize(('code','category','status','expected_calls'),[
    ('insufficient_quota','quota',502,1),
    ('invalid_api_key','authentication',401,1),
    ('permission_denied','permission',403,1),
    ('context_length_exceeded','invalid_request',400,1),
    ('rate_limit_exceeded','rate_limit',429,2),
    ('upstream_error','unavailable',502,2),
])
async def test_raw_json_error_after_sse_heartbeats_preserves_provider_category(code,category,status,expected_calls,caplog):
    calls=0
    def handle(request):
        nonlocal calls
        calls+=1
        # Some compatible gateways send heartbeats, then an unframed error
        # without a final newline while retaining text/event-stream headers.
        body=': keep-alive\n\n'+json.dumps({'error':{'code':code,'type':code,'message':'private-key and teacher material'}})
        return httpx.Response(200,text=body,headers={'Content-Type':'text/event-stream'})
    with caplog.at_level(logging.WARNING):
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
            with pytest.raises(ModelCallError) as caught:await generate_html(CONFIG,{},http)
    assert caught.value.category==category
    assert caught.value.status_code==status
    assert calls==expected_calls
    assert 'private-key' not in caplog.text+str(caught.value)
    assert 'teacher material' not in caplog.text+str(caught.value)


async def test_sse_final_done_without_newline_is_a_complete_response():
    def handle(request):
        data={'choices':[{'index':0,'delta':{'content':json.dumps({'html':HTML})},'finish_reason':None}]}
        final={'choices':[{'index':0,'delta':{},'finish_reason':'stop'}]}
        return httpx.Response(200,text='data: '+json.dumps(data)+'\r\n\r\ndata: '+json.dumps(final)+'\r\n\r\ndata: [DONE]',headers={'Content-Type':'text/event-stream'})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        assert await generate_html(CONFIG,{},http)==HTML


async def test_length_limited_stream_is_not_retried_as_a_connection_fault():
    calls=0
    def handle(request):
        nonlocal calls
        calls+=1
        event={'choices':[{'delta':{'content':'{"html":"partial'},'finish_reason':'length'}]}
        return httpx.Response(200,text='data: '+json.dumps(event)+'\n\ndata: [DONE]\n\n',headers={'Content-Type':'text/event-stream'})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        with pytest.raises(ModelCallError) as caught:await generate_html(CONFIG,{},http)
    assert caught.value.category=='output_limit'
    assert '长度' in str(caught.value)
    assert calls==1
