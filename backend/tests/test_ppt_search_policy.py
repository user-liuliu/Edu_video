from types import SimpleNamespace
from uuid import UUID,uuid4
from unittest.mock import AsyncMock
import pytest
from app.models import ModelConfigRow
from app.presentations.models import PptProject
from app.settings_store import get_form_fields,put_form_fields

async def policy(db,box,visible,default,available=True):
    cfg=await get_form_fields(db)
    field=next(f for f in cfg.fields if f.key=='web_search')
    field.visible=visible;field.default=default
    await put_form_fields(db,cfg)
    db.add(ModelConfigRow(purpose='web_search',enabled=available,base_url='https://api.tavily.com',api_key_encrypted=box.encrypt('test-only-search-key'),model=''))
    await db.commit()

@pytest.mark.parametrize('visible,default,available,want',[
    (False,False,True,(False,False,True)),
    (False,True,True,(False,True,True)),
    (True,True,True,(True,True,True)),
    (True,True,False,(False,False,False)),
])
async def test_config_exposes_effective_admin_search_policy(teacher_client,db,box,visible,default,available,want):
    await policy(db,box,visible,default,available)
    r=await teacher_client.get('/api/presentations/config');assert r.status_code==200
    data=r.json()
    assert (data.get('search_visible'),data.get('search_default'),data['search_available'])==want

@pytest.mark.parametrize('visible,default,available,submitted,want',[
    (False,False,True,True,False),
    (False,True,True,False,True),
    (True,True,True,None,True),
    (True,True,True,False,False),
    (True,False,True,True,True),
    (True,True,False,True,False),
])
async def test_project_create_and_save_enforce_search_policy(teacher_client,db,box,visible,default,available,submitted,want):
    await policy(db,box,visible,default,available)
    body={'title':'搜索配置测试','prompt':'讲解光合作用'}
    if submitted is not None:body['web_search']=submitted
    r=await teacher_client.post('/api/presentations',json=body);assert r.status_code==200,r.text
    p=r.json();assert p['web_search'] is want
    r=await teacher_client.put('/api/presentations/'+p['id'],json={**body,'revision':p['revision']});assert r.status_code==200,r.text
    assert r.json()['web_search'] is want

async def test_old_project_search_choice_is_rechecked_when_job_is_submitted(teacher_client,db,box,monkeypatch):
    from app.presentations import router
    await policy(db,box,False,False)
    p=(await teacher_client.post('/api/presentations',json={'title':'旧课件','prompt':'教学','web_search':False})).json()
    row=await db.get(PptProject,UUID(p['id']));row.web_search=True;await db.commit()
    monkeypatch.setattr(router,'resolve',AsyncMock(return_value=object()))
    r=await teacher_client.post('/api/presentations/'+p['id']+'/jobs/outline',json={'revision':p['revision'],'idempotency_key':'policy-change'})
    assert r.status_code==200,r.text
    state=(await teacher_client.get('/api/presentations/'+p['id'])).json()
    assert state['web_search'] is False

@pytest.mark.parametrize('visible,default,requested,want_search,available',[(False,False,True,False,True),(False,True,False,True,True),(True,False,True,True,True),(True,True,False,False,True),(True,True,True,False,False)])
async def test_worker_reference_collection_rechecks_admin_policy(db,box,settings,monkeypatch,visible,default,requested,want_search,available):
    from app.presentations import generation
    await policy(db,box,visible,default,available)
    project=SimpleNamespace(id=uuid4(),owner_id=uuid4(),prompt='植物如何制造养分',web_search=requested)
    async def search(*args,**kwargs):return [{'text':'已检索的教学资料','url':'https://example.org/lesson'}]
    monkeypatch.setattr(generation,'search_cached',search)
    refs,warnings=await generation.references(db,project,settings)
    assert bool(refs) is want_search
    if want_search:assert refs[0]['text']=='已检索的教学资料'
