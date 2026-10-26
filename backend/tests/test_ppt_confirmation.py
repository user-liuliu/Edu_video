from copy import deepcopy
from unittest.mock import AsyncMock
from uuid import UUID,uuid4
import pytest
from sqlalchemy import select,func
from app.presentations import router
from app.presentations.models import PptProject,PptJob
from tests.test_ppt_api import create
from tests.test_ppt_workflow import checked_outline

async def reviewed_project(client,db):
    data=await create(client)
    p=await db.get(PptProject,UUID(data['id']))
    p.outline=checked_outline({'slides':[{'id':str(uuid4()),'layout':'concept','title':'二次函数','content':'y=ax²+bx+c，a≠0','slots':{}}]})
    p.status='outline_ready'
    await db.commit()
    return p,'/api/presentations/'+data['id']

async def test_confirm_persists_without_jobs_or_model_calls(teacher_client,db,monkeypatch):
    p,base=await reviewed_project(teacher_client,db)
    resolver=AsyncMock(side_effect=AssertionError('confirmation must not call models'))
    monkeypatch.setattr(router,'resolve',resolver)
    for _ in range(2):
        response=await teacher_client.post(base+'/confirm',json={'revision':1})
        assert response.status_code==200,response.text
        state=response.json()
        assert state['confirmed_revision']==state['revision']==1
        assert state['status']=='outline_confirmed' and state['pages']==[] and state['job'] is None
    assert await db.scalar(select(func.count()).select_from(PptJob))==0
    resolver.assert_not_called()
    assert (await teacher_client.get(base)).json()['confirmed_revision']==1

@pytest.mark.parametrize('condition,code',[('stale','revision_conflict'),('missing','outline_missing'),('unchecked','outline_review_required'),('changed','outline_review_required'),('busy','project_busy')])
async def test_confirm_rejects_stale_unreviewed_or_busy_outline(teacher_client,db,condition,code):
    p,base=await reviewed_project(teacher_client,db)
    revision=1
    if condition=='stale':revision=2
    elif condition=='missing':p.outline=None
    elif condition=='unchecked':p.outline={'slides':p.outline['slides']}
    elif condition=='changed':
        changed=deepcopy(p.outline);changed['slides'][0]['content']='改变内容';p.outline=changed
    elif condition=='busy':db.add(PptJob(owner_id=p.owner_id,project_id=p.id,kind='check',idempotency_key='busy',expected_revision=1,payload={}))
    await db.commit()
    response=await teacher_client.post(base+'/confirm',json={'revision':revision})
    assert response.status_code==409,response.text
    assert response.json()['detail']['code']==code
    assert (await teacher_client.get(base)).json()['confirmed_revision'] is None

async def test_other_owner_cannot_confirm_outline(teacher_client,db,make_user,make_client,app):
    p,base=await reviewed_project(teacher_client,db)
    await make_user('other-confirm');other=make_client(app)
    await other.post('/api/auth/login',json={'username':'other-confirm','password':'pass1234'})
    response=await other.post(base+'/confirm',json={'revision':1})
    assert response.status_code==404
    assert (await teacher_client.get(base)).json()['confirmed_revision'] is None

async def test_reviewed_outline_requires_separate_confirmation_before_render(teacher_client,db,monkeypatch):
    p,base=await reviewed_project(teacher_client,db)
    monkeypatch.setattr(router,'resolve',AsyncMock(return_value=object()))
    denied=await teacher_client.post(base+'/jobs/render',json={'revision':1,'idempotency_key':'before-confirm'})
    assert denied.status_code==409,denied.text
    assert denied.json()['detail']['code']=='outline_not_confirmed'
    assert await db.scalar(select(func.count()).select_from(PptJob))==0
    assert (await teacher_client.post(base+'/confirm',json={'revision':1})).status_code==200
    started=await teacher_client.post(base+'/jobs/render',json={'revision':1,'idempotency_key':'after-confirm'})
    assert started.status_code==200,started.text
    assert started.json()['kind']=='render'
    assert await db.scalar(select(func.count()).select_from(PptJob))==1

async def test_edit_invalidates_confirmation_and_blocks_render(teacher_client,db,monkeypatch):
    p,base=await reviewed_project(teacher_client,db)
    monkeypatch.setattr(router,'resolve',AsyncMock(return_value=object()))
    assert (await teacher_client.post(base+'/confirm',json={'revision':1})).status_code==200
    slides=deepcopy(p.outline['slides']);slides[0]['title']='新标题'
    saved=await teacher_client.put(base+'/outline',json={'revision':1,'slides':slides})
    assert saved.status_code==200,saved.text
    assert saved.json()['revision']==2 and saved.json()['confirmed_revision'] is None
    response=await teacher_client.post(base+'/jobs/render',json={'revision':2,'idempotency_key':'edited'})
    assert response.status_code==409
    assert await db.scalar(select(func.count()).select_from(PptJob))==0
