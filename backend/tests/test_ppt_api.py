from uuid import uuid4
from sqlalchemy import select, func
from app.models import VideoProject
from app.presentations.models import PptProject, PptJob
from tests.test_ppt_rendering import page

async def create(client):
    response=await client.post('/api/presentations',json={'title':'植物的能量','prompt':'给初中学生讲解光合作用'})
    assert response.status_code==200,response.text
    return response.json()

async def test_ppt_project_is_separate_and_revision_conflicts_do_not_overwrite(teacher_client,db):
    p=await create(teacher_client)
    assert await db.scalar(select(func.count()).select_from(VideoProject))==0
    response=await teacher_client.put('/api/presentations/'+p['id'],json={'title':'新课题','prompt':'观察叶片','revision':p['revision']})
    assert response.status_code==200
    stale=await teacher_client.put('/api/presentations/'+p['id'],json={'title':'旧输入','prompt':'不应覆盖','revision':p['revision']})
    assert stale.status_code==409
    assert (await teacher_client.get('/api/presentations/'+p['id'])).json()['title']=='新课题'

async def test_other_teacher_cannot_read_mutate_or_export_ppt(teacher_client,make_user,make_client,app,db):
    p=await create(teacher_client);await make_user('other');c=make_client(app)
    await c.post('/api/auth/login',json={'username':'other','password':'pass1234'})
    for path in ['', '/export', '/slides/'+str(uuid4())+'/preview']:
        assert (await c.get('/api/presentations/'+p['id']+path)).status_code==404
    assert (await c.delete('/api/presentations/'+p['id']+'?revision=1')).status_code==404

async def test_outline_edits_invalidate_render_and_export(teacher_client,db):
    p=await create(teacher_client);project=await db.get(PptProject,p['id']);a=page()
    project.outline={'slides':[a]};project.pages=[a];project.rendered_revision=1;project.status='ready';await db.commit()
    exported=await teacher_client.get('/api/presentations/'+p['id']+'/export')
    assert exported.status_code==200 and exported.content[:2]==b'PK'
    a['content']='增加叶绿素实验'
    saved=await teacher_client.put('/api/presentations/'+p['id']+'/outline',json={'revision':1,'slides':[a]})
    assert saved.status_code==200,saved.text
    assert saved.json()['pages']==[]
    assert (await teacher_client.get('/api/presentations/'+p['id']+'/export')).status_code==409
    assert (await teacher_client.get('/api/presentations/'+p['id']+'/slides/'+a['id']+'/preview')).status_code==409

async def test_generate_idempotency_and_confirm_exact_saved_outline(teacher_client,db,monkeypatch):
    from app.presentations import router
    monkeypatch.setattr(router,'resolve',__import__('unittest.mock').mock.AsyncMock(return_value=object()))
    p=await create(teacher_client);base='/api/presentations/'+p['id']
    body={'revision':1,'idempotency_key':'first'}
    r=await teacher_client.post(base+'/jobs/outline',json=body);assert r.status_code==200,r.text
    replay=await teacher_client.post(base+'/jobs/outline',json=body)
    assert replay.status_code==200 and replay.json()['id']==r.json()['id']
    assert await db.scalar(select(func.count()).select_from(PptJob))==1
    busy=await teacher_client.put(base,json={'title':'改变','prompt':'需求','revision':1})
    assert busy.status_code==409
    job=await db.get(PptJob,r.json()['id']);job.status='failed';await db.commit()
    assert (await teacher_client.post(base+'/jobs/render',json={'revision':1,'idempotency_key':'bad'})).status_code==409


async def test_native_export_capacity_is_global_nonblocking_and_deduplicates(db_engine):
    import pytest
    from fastapi import HTTPException
    from app.db import create_sessionmaker
    from app.presentations.router import require_export_capacity
    maker=create_sessionmaker(db_engine);pid=uuid4()
    async with maker() as first,maker() as second,maker() as third:
        await require_export_capacity(first,pid,1)
        with pytest.raises(HTTPException) as duplicate:await require_export_capacity(second,pid,1)
        assert duplicate.value.status_code==429
        await second.rollback()
        await require_export_capacity(second,uuid4(),1)
        with pytest.raises(HTTPException) as full:await require_export_capacity(third,uuid4(),1)
        assert full.value.status_code==429
        await third.rollback();await first.rollback()
        await require_export_capacity(third,uuid4(),1)


async def test_preview_and_export_block_previously_published_unapproved_pages(teacher_client,db):
    from uuid import UUID
    p=await create(teacher_client);project=await db.get(PptProject,UUID(p['id']));slide=page()
    slide['review']={'status':'needs_attention','issues':[{'message':'文字重叠'}],'repairs':2}
    project.outline={'slides':[slide]};project.pages=[slide];project.rendered_revision=1;project.status='ready';await db.commit()
    base='/api/presentations/'+p['id']
    for suffix in ['/export','/slides/'+slide['id']+'/preview']:
        response=await teacher_client.get(base+suffix)
        assert response.status_code==409,response.text
        assert response.json()['detail']['code']=='ppt_review_required'


async def test_legacy_partial_revision_is_rejected_before_model_resolution(teacher_client,db,monkeypatch):
    from uuid import UUID
    from unittest.mock import AsyncMock
    from app.presentations import router
    from tests.test_ppt_master_runtime import sample_svg
    p=await create(teacher_client);project=await db.get(PptProject,UUID(p['id']));a=page();b={**page(),'id':str(uuid4())}
    for slide in [a,b]:slide.update(renderer='ppt-master-6.7.0',svg=sample_svg())
    project.outline={'slides':[a,b]};project.pages=[a,b];project.rendered_revision=1;project.status='ready';await db.commit()
    resolver=AsyncMock(side_effect=AssertionError('must preflight before provider resolution'));monkeypatch.setattr(router,'resolve',resolver)
    response=await teacher_client.post('/api/presentations/'+p['id']+'/jobs/revise',json={'revision':1,'idempotency_key':'legacy-review','slide_ids':[a['id']],'instruction':'精简文字'})
    assert response.status_code==409,response.text
    assert response.json()['detail']['code']=='ppt_review_migration_required'
    assert '整份' in response.json()['detail']['message']
    resolver.assert_not_called()
