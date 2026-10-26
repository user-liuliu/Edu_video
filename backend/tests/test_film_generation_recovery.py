from copy import deepcopy
import json
from types import SimpleNamespace

import httpx
import pytest

from app.outline.model_client import ModelCallError
from app.videos.film_modules import generate_film, extract_film
from test_film_modules import film, timeline

CONFIG = SimpleNamespace(base_url='https://test.invalid/v1', api_key='private-test-key', model='writer')

def response(value):
    return httpx.Response(200, json={'choices': [{'message': {'content': json.dumps(value)}}]})

def request():
    targets = [{**t, 'scene_id': 'board', 'entry_state': 'start', 'exit_state': 'end',
                'sentences': [{'start': t['start'], 'end': t['end'], 'text': t['narration']}]} for t in timeline()]
    return {'title': '教学测试', 'segments': targets, 'film_module_protocol': 'film-modules-1',
            'whole_film_visual_prompt': '同一坐标轴，保持刻度和配色',
            'continuity_manifest': {'characters': [], 'segments': [{'id': t['id'], 'scene_id': t['scene_id'],
                'entry_state': t['entry_state'], 'exit_state': t['exit_state']} for t in targets]},
            'approved_outline': {'segments': [{'id': 'outline-'+str(i), 'narration': t['narration'],
                'visuals': '不得遗漏的受力公式F=ma'} for i,t in enumerate(targets)]}}

def bundle():
    value = film()
    for item in value['transitions']: item.update(mode='continuous', code=';')
    return value

async def test_request_compaction_keeps_unique_approved_facts_and_frozen_timing():
    calls=[];original=request();before=deepcopy(original)
    def handle(req):
        calls.append(json.loads(req.content));return response(bundle())
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        await generate_film(CONFIG,original,http)
    user=json.loads(calls[0]['messages'][1]['content'])
    assert original==before
    assert user['segments']==original['segments']
    assert 'segments' not in user['continuity_manifest']
    assert all('narration' not in s for s in user['approved_outline']['segments'])
    assert 'F=ma' in json.dumps(user,ensure_ascii=False)

async def test_slow_whole_response_recovers_in_order_without_redrawing_shared_code(monkeypatch):
    import app.videos.model_stream as transport
    ticks=iter([0.,121.]);monkeypatch.setattr(transport,'request_clock',lambda:next(ticks,121.))
    monkeypatch.setattr('app.outline.model_client._retry_delay',lambda *args:0)
    calls=[];value=bundle();frozen=request()
    def handle(req):
        payload=json.loads(req.content);calls.append(payload)
        if len(calls)==1:return httpx.Response(502)
        user=json.loads(payload['messages'][1]['content'])
        keys=[t['render_key'] for t in user['segments']]
        if len(calls)==2:
            return response({**value,'segments':value['segments'][:1],'transitions':[]})
        assert len(keys)==1
        index=int(keys[0][1:])
        assert user['film']['shared_code']==value['shared_code']
        assert user['read_only_boundary_context'][-1]==value['segments'][index-1]
        assert user['previous_segment_context']=={k:v for k,v in frozen['segments'][index-1].items() if k!='sentences'}
        return response({'segments':[value['segments'][index]],'transitions':[value['transitions'][index-1]]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        raw=await generate_film(CONFIG,frozen,http)
    assert len(calls)==4
    assert extract_film(raw)==value
    assert all(p['stream'] is True for p in calls)
    assert frozen==request()

@pytest.mark.parametrize('category,status',[('authentication',401),('permission',403),('invalid_request',400),('rate_limit',429)])
async def test_permanent_or_rate_limit_errors_do_not_expand_requests(monkeypatch,category,status):
    calls=[]
    async def fail(*args,**kwargs):
        calls.append(args);raise ModelCallError('服务不可用',category=category,status_code=status)
    monkeypatch.setattr('app.videos.model_stream.animation_response',fail)
    with pytest.raises(ModelCallError): await generate_film(CONFIG,request(),None)
    assert len(calls)==1

async def test_local_revision_failure_never_switches_to_full_generation(monkeypatch):
    calls=[];req={**request(),'film_revision_source':bundle(),'editable_segment_ids':['s1']}
    async def fail(*args,**kwargs):
        calls.append(args);raise ModelCallError('连接失败',category='connection')
    monkeypatch.setattr('app.videos.model_stream.animation_response',fail)
    with pytest.raises(ModelCallError): await generate_film(CONFIG,req,None)
    assert len(calls)==1

@pytest.mark.parametrize('fault',['shared','unselected','wrong_join','missing'])
async def test_split_recovery_rejects_changed_shared_code_or_missing_modules(monkeypatch,fault):
    calls=[];value=bundle()
    async def send(http,url,headers,payload,**kwargs):
        calls.append(payload)
        if len(calls)==1:raise ModelCallError('输出过长',category='output_limit')
        if len(calls)==2:return response({**value,'segments':value['segments'][:1],'transitions':[]})
        delta={'segments':[value['segments'][1]],'transitions':[value['transitions'][0]]}
        if fault=='shared':delta['shared_code']='return {changed:true};'
        if fault=='unselected':delta['segments']=[value['segments'][2]]
        if fault=='wrong_join':delta['transitions']=[value['transitions'][1]]
        if fault=='missing':delta['segments']=[]
        return response(delta)
    monkeypatch.setattr('app.videos.model_stream.animation_response',send)
    with pytest.raises(ValueError):await generate_film(CONFIG,request(),None)
    assert len(calls)==4


async def test_compaction_preserves_nonduplicate_boundary_and_approved_narration():
    original=request()
    original['continuity_manifest']['segments'][0]['entry_state']='unique required pose'
    original['approved_outline']['segments'][0]['narration']='独有的审核条件与限制'
    calls=[]
    def handle(req):
        calls.append(json.loads(req.content));return response(bundle())
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        await generate_film(CONFIG,original,http)
    user=json.loads(calls[0]['messages'][1]['content'])
    assert user['continuity_manifest']['segments'][0]['entry_state']=='unique required pose'
    assert user['approved_outline']['segments'][0]['narration']=='独有的审核条件与限制'


async def test_output_limit_recovers_from_real_stream_and_preserves_all_modules(monkeypatch):
    from test_expression_stream import streamed
    calls=[];value=bundle()
    def handle(req):
        payload=json.loads(req.content);calls.append(payload)
        if len(calls)==1:return streamed({'partial':'discard this'},finish='length')
        if len(calls)==2:return streamed({**value,'segments':value['segments'][:1],'transitions':[]})
        index=len(calls)-2
        return streamed({'segments':[value['segments'][index]],'transitions':[value['transitions'][index-1]]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        html=await generate_film(CONFIG,request(),http)
    assert len(calls)==4
    assert extract_film(html)==value


async def test_failed_split_stops_after_existing_transport_budget(monkeypatch,caplog):
    from test_expression_stream import streamed
    monkeypatch.setattr('app.outline.model_client._retry_delay',lambda *args:0)
    calls=[]
    def handle(req):
        calls.append(req)
        return streamed({},finish='length') if len(calls)==1 else httpx.Response(502,text='private-test-key')
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        with pytest.raises(ModelCallError) as error:await generate_film(CONFIG,request(),http)
    assert len(calls)==5  # original truncated output, then at most four seed attempts
    assert error.value.status_code==502
    assert 'private-test-key' not in str(error.value)+caplog.text


@pytest.mark.parametrize('mode',['revision','repair','single'])
async def test_output_limit_never_expands_frozen_revision_or_runtime_repair(monkeypatch,mode):
    original=request();calls=[]
    if mode=='revision':original.update(film_revision_source=bundle(),editable_segment_ids=['s1'])
    elif mode=='repair':original['previous_film_bundle']=bundle()
    else:original['segments']=original['segments'][:1]
    async def fail(*args,**kwargs):
        calls.append(args);raise ModelCallError('输出过长',category='output_limit')
    monkeypatch.setattr('app.videos.model_stream.animation_response',fail)
    with pytest.raises(ModelCallError):await generate_film(CONFIG,original,None)
    assert len(calls)==1


async def test_total_generation_deadline_stops_pending_recovery(monkeypatch):
    import asyncio
    import app.videos.film_modules as modules
    monkeypatch.setattr(modules,'MAX_GENERATION_SECONDS',0.01,raising=False)
    completed=[]
    async def send(*args,**kwargs):
        try:
            await asyncio.sleep(1)
        finally:
            completed.append('cancelled')
    monkeypatch.setattr('app.videos.model_stream.animation_response',send)
    with pytest.raises(ModelCallError,match='等待超时') as failure:
        await generate_film(CONFIG,request(),None)
    assert failure.value.category=='timeout' and completed==['cancelled']


async def test_buffered_truncation_uses_same_recovery_as_streaming():
    calls=[];value=bundle()
    def handle(req):
        calls.append(json.loads(req.content))
        if len(calls)==1:
            return httpx.Response(200,json={'choices':[{'message':{'content':'{partial'},'finish_reason':'length'}]})
        if len(calls)==2:return response({**value,'segments':value['segments'][:1],'transitions':[]})
        index=len(calls)-2
        return response({'segments':[value['segments'][index]],'transitions':[value['transitions'][index-1]]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        html=await generate_film(CONFIG,request(),http)
    assert len(calls)==4 and extract_film(html)==value


async def test_buffered_quota_error_is_not_retried_as_bad_code_or_split():
    calls=[]
    def handle(req):
        calls.append(req)
        return httpx.Response(200,json={'error':{'code':'insufficient_quota','message':'private-test-key'}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        with pytest.raises(ModelCallError) as error:await generate_film(CONFIG,request(),http)
    assert error.value.category=='quota' and len(calls)==1
    assert 'private-test-key' not in str(error.value)


async def test_buffered_nonstop_completion_retries_before_accepting_complete_result(monkeypatch):
    monkeypatch.setattr('app.outline.model_client._retry_delay',lambda *args:0)
    calls=[];value=bundle()
    def handle(req):
        calls.append(req)
        return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps(value)},
            'finish_reason':'tool_calls' if len(calls)==1 else 'stop'}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        html=await generate_film(CONFIG,request(),http)
    assert len(calls)==2 and extract_film(html)==value
