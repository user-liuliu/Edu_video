from copy import deepcopy
from types import SimpleNamespace
import json

import pytest

from app.videos.direct_pipeline import html_repair_request
from app.videos.film_modules import assemble_film,extract_film,generate_film
from test_film_generation_recovery import request,bundle,response


def seam(left='s0',right='s1'):
    return f'连续场景 {left} → {right} 边界画面不一致（平均差异0.10）；保持背景、坐标、主体和标注末态'


def test_known_seam_repairs_only_the_incoming_module_and_keeps_source_immutable():
    req=request();original=bundle();before=deepcopy(original)
    patch=html_repair_request(req,assemble_film(original,req['segments']),feedback=seam())
    assert patch['editable_segment_ids']==['s1']
    assert patch['film_revision_source']==original
    assert 'previous_film_bundle' not in patch
    assert original==before


@pytest.mark.parametrize('feedback',[
    '整片动画运行失败',seam('s0','not-in-film'),seam('s0','s2'),
    '用户内容里提到了 '+seam(),
])
def test_unknown_or_nonadjacent_feedback_does_not_guess_a_repair_scope(feedback):
    req=request();original=bundle()
    patch=html_repair_request(req,assemble_film(original,req['segments']),feedback=feedback)
    assert patch['previous_film_bundle']==original
    assert 'editable_segment_ids' not in patch


@pytest.mark.parametrize('selected',[['s0'],['s1'],['s2']])
def test_runtime_repair_never_expands_teacher_selected_revision_scope(selected):
    req=request();original=bundle();req.update(film_revision_source=original,editable_segment_ids=selected)
    patch=html_repair_request(req,assemble_film(original,req['segments']),feedback=seam())
    assert patch['editable_segment_ids']==selected


async def test_scoped_repair_requests_delta_and_preserves_all_other_modules(monkeypatch):
    req=request();original=bundle();raw=assemble_film(original,req['segments'])
    repair=html_repair_request(req,raw,feedback=seam());calls=[]
    changed={**original['segments'][1],'code':original['segments'][1]['code']+';'}
    async def send(http,url,headers,payload,**kwargs):
        calls.append(payload)
        user=json.loads(payload['messages'][1]['content'])
        assert user['response_schema']['title']=='FilmDelta'
        assert user['editable_segment_ids']==['s1']
        assert [s['id'] for s in user['film']['segments']]==['s1']
        assert 'film_repair_source' not in user
        return response({'segments':[changed],'transitions':original['transitions']})
    monkeypatch.setattr('app.videos.model_stream.animation_response',send)
    result=await generate_film(SimpleNamespace(base_url='https://test.invalid',api_key='test',model='test'),repair,None,feedback=seam())
    actual=extract_film(result)
    assert len(calls)==1
    assert actual['segments'][1]==changed
    assert actual['segments'][0]==original['segments'][0] and actual['segments'][2]==original['segments'][2]
    assert actual['shared_code']==original['shared_code'] and actual['shared_html']==original['shared_html']


async def test_real_pipeline_routes_the_runtime_seam_to_local_repair_and_reuses_narration(db,teacher_client,box,settings,monkeypatch):
    from uuid import UUID,uuid4
    from app.models import VideoVersion
    from app.jobs.tasks import run_job
    from app.outline.review import mark_saved
    from app.videos.render_contract import DirectHtmlRuntimeError
    from test_direct_pipeline import prepare
    project,path,store,renderer,counts,calls=await prepare(db,teacher_client,box,settings,monkeypatch)
    import app.videos.direct_pipeline as pipeline
    original_generate=pipeline.generate_html
    async def continuous(*args,**kwargs):
        raw=await original_generate(*args,**kwargs);value=extract_film(raw)
        for transition in value['transitions']:transition.update(mode='continuous',code=';')
        return assemble_film(value,args[1]['segments'])
    monkeypatch.setattr(pipeline,'generate_html',continuous)
    first=deepcopy(project.outline['segments'][0])
    project.outline=mark_saved({'segments':[{**deepcopy(first),'id':str(uuid4()),'position':i} for i in range(3)]});await db.commit()
    original_render=renderer.direct;seen=[]
    async def fail_once(html,manifest,audio,size,*,validate=False):
        seen.append(audio)
        if len(seen)==1:raise DirectHtmlRuntimeError(seam('segment-0','segment-1'))
        return await original_render(html,manifest,audio,size,validate=validate)
    renderer.direct=fail_once
    response=await teacher_client.post(path,json={'revision':1,'idempotency_key':'scoped-runtime-repair'})
    value=response.json();await run_job(value['job']['id'],settings)
    result=(await teacher_client.get(path+'/'+value['id'])).json()
    assert result['status']=='preview_ready',result
    assert len(calls)==2 and calls[1]['editable_segment_ids']==['segment-1']
    assert 'previous_film_bundle' not in calls[1]
    assert counts['speech']==3 and seen[0]==seen[1]
    row=await db.get(VideoVersion,UUID(value['id']),populate_existing=True)
    assert row.snapshot['direct_source']['last_runtime_error']==seam('segment-0','segment-1')
