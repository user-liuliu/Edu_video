from uuid import UUID, uuid4
from unittest.mock import AsyncMock
import pytest
from fastapi import HTTPException
from langgraph.checkpoint.memory import InMemorySaver
from app.models import VideoProject
from app.jobs.service import create_job
from app.settings_store import get_form_fields, put_form_fields, GenerationParams
from app.outline.schemas import JobRequest, OutlineData, normalize_outline_visual_kinds
from app.outline.service import start_outline, execute_outline_job, normalize_review_results
from app.outline.graph import build_outline_graph
from test_outline_edit import segment

async def test_generate_requires_form_version(db, teacher_client, box, monkeypatch):
    p=(await teacher_client.post('/api/projects',json={'prompt':'数学'})).json()
    project=await db.get(VideoProject, UUID(p['id']))
    monkeypatch.setattr('app.outline.service.system_available',AsyncMock(return_value=True))
    user=type('Teacher',(),{'id':project.owner_id})()
    with pytest.raises(HTTPException) as exc:
        await start_outline(db,user,project.id,JobRequest(revision=1,idempotency_key='missing-version'),'generate',box)
    assert exc.value.status_code==409
    assert exc.value.detail['code']=='form_config_changed'

async def test_queued_generation_rejects_changed_policy_before_search(db, teacher_client, box, settings, monkeypatch):
    p=(await teacher_client.post('/api/projects',json={'prompt':'数学'})).json()
    project=await db.get(VideoProject,UUID(p['id']))
    version=(await teacher_client.get('/api/config/form')).json()['form_version']
    job=await create_job(db,project,'generate','policy',{'form_version':version})
    job.status='running';job.lease_token=uuid4();await db.commit()
    cfg=await get_form_fields(db)
    next(f for f in cfg.fields if f.key=='web_search').visible=False
    await put_form_fields(db,cfg);await db.commit()
    collect=AsyncMock();monkeypatch.setattr('app.outline.service.collect_evidence',collect)
    monkeypatch.setattr('app.outline.service.resolve',AsyncMock(return_value=object()))
    with pytest.raises(ValueError,match='页面配置已更新'):
        await execute_outline_job(db,job,settings)
    collect.assert_not_awaited()

async def test_hidden_materials_cannot_be_uploaded(db,teacher_client):
    p=(await teacher_client.post('/api/projects',json={'prompt':'数学'})).json()
    cfg=await get_form_fields(db)
    next(f for f in cfg.fields if f.key=='materials').visible=False
    await put_form_fields(db,cfg);await db.commit()
    response=await teacher_client.post('/api/projects/'+p['id']+'/materials',headers={'Origin':'http://test'},files={'file':('test.png',b'bad')})
    assert response.status_code==409
    assert response.json()['detail']['code']=='materials_disabled'

async def test_agent_enforces_visual_count_and_reports_duration_tolerance():
    s=segment()
    async def generate(state):return {'segments':[s]}
    async def review(state):return {s['id']:{'passed':True,'issues':[],'notes':[]}}
    params=GenerationParams().model_dump()
    state={'prompt':'数学','form_values':{'duration_seconds':300},'evidence':[],'operation':'generate','generation_params':params}
    graph=build_outline_graph(InMemorySaver(),generate,review)
    with pytest.raises(ValueError,match='画面数'):
        await graph.ainvoke(state,{'configurable':{'thread_id':'bad-count'}})
    s['visuals']*=3
    result=await graph.ainvoke(state,{'configurable':{'thread_id':'duration'}})
    assert any('时长偏差' in n for n in result['outline']['segments'][0]['review_notes'])


def test_model_visual_kind_aliases_are_normalized_before_schema_validation():
    raw = {
        'segments': [{
            'id': str(uuid4()),
            'title': '串联电路',
            'objective': '理解串联电路',
            'narration': '串联电路中各元件首尾相连。',
            'visuals': [
                {'kind': '对比图', 'description': '串联与并联的对比'},
                {'kind': '动画示意图', 'description': '电流路径动画'},
                {'kind': '文字卡', 'description': '电路特点'},
            ],
            'evidence_ids': [],
            'content_kind': 'knowledge',
        }],
    }

    normalized = normalize_outline_visual_kinds(raw)
    OutlineData.model_validate(normalized)
    assert [visual['kind'] for visual in normalized['segments'][0]['visuals']] == [
        '学科示意图', '学科示意图', '文字卡',
    ]


def test_legacy_notes_without_verdict_do_not_imply_approval():
    identifier = str(uuid4())
    with pytest.raises(ValueError):
        normalize_review_results({'notes': {identifier: []}}, [identifier])


def test_structured_review_requires_explicit_verdict():
    identifier = str(uuid4())
    result = {'items': [{'segment_id': identifier, 'passed': True, 'issues': [], 'notes': ['建议补充单位']}]}
    assert normalize_review_results(result, [identifier]) == {identifier: {'passed': True, 'issues': [], 'notes': ['建议补充单位']}}
