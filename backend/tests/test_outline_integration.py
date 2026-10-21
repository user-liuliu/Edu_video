from uuid import UUID,uuid4
from unittest.mock import AsyncMock
import pytest
from sqlalchemy import select,text
from app.models import VideoProject,OutlineJob,Material
from app.purposes import Purpose
from app.model_configs.schemas import ResolvedConfig
from app.jobs.service import create_job
from app.jobs.dispatcher import dispatch_pending
from app.outline.service import execute_outline_job,confirm_outline,save_outline
from app.jobs.setup import initialize_agent_state
from app.outline.schemas import OutlineSave

async def test_outbox_broker_failure_and_expired_lease(db,teacher_client):
    from datetime import UTC,datetime,timedelta
    p=(await teacher_client.post('/api/projects',json={'prompt':'数学'})).json()
    row=await db.get(VideoProject,UUID(p['id']))
    job=await create_job(db,row,'parse','durable',{});await db.commit()
    def fail(identifier): raise ConnectionError('offline')
    await dispatch_pending(db,fail)
    await db.refresh(job);assert job.dispatched_at is None
    sent=[];await dispatch_pending(db,sent.append);assert sent==[str(job.id)]
    job.status='running';job.lease_until=datetime.now(UTC)-timedelta(seconds=1);await db.commit()
    await dispatch_pending(db,sent.append);assert len(sent)==2

async def test_persisted_outline_review_and_confirmation(db,teacher_client,settings,monkeypatch):
    schema='agent_test_'+uuid4().hex
    isolated=settings.model_copy(update={'agent_schema':schema})
    await initialize_agent_state(isolated)
    try:
        project=(await teacher_client.post('/api/projects',json={'prompt':'二次函数'})).json()
        p=await db.get(VideoProject,UUID(project['id']))
        version=(await teacher_client.get('/api/config/form')).json()['form_version']
        job=await create_job(db,p,'generate','integration',{'segment_ids':[],'instruction':'','form_version':version})
        job.status='running';job.lease_token=uuid4();await db.commit()
        async def resolve(db,box,purpose):
            if purpose not in (Purpose.outline_llm,Purpose.review_llm):return None
            return ResolvedConfig(purpose,'https://mock.invalid/v1','fake-test-key','test',{})
        monkeypatch.setattr('app.outline.service.resolve',resolve)
        sid=str(uuid4());calls=[];observed_job=job
        async def chat(config,messages,*args,**kwargs):
            from app.db import create_sessionmaker
            async with create_sessionmaker(db.bind)() as observer:
                current=await observer.get(OutlineJob,observed_job.id)
                assert current.stage == ('审核大纲' if config.purpose==Purpose.review_llm else '改写大纲' if observed_job.kind=='rewrite' else '生成大纲')
                assert current.progress == (80 if config.purpose==Purpose.review_llm else 45)
            calls.append(config.purpose)
            if config.purpose==Purpose.review_llm:
                import json
                payload=json.loads(messages[0]['content'].split('待审核资料：',1)[-1])
                assert payload['timing_policy']['estimate_owner']=='server'
                assert payload['timing_policy']['duration_tolerance_pct']==15
                assert 'estimated_duration_seconds' not in payload['segments'][0]
                assert payload['timing_policy']['segment_estimates_seconds'][sid]>1
                return {'items':[{'segment_id':sid,'passed':True,'issues':[],'notes':['请核对教材']}]}
            assert '每段画面数在' not in messages[0]['content']
            return {'segments':[{'id':sid,'title':'开场','objective':'理解函数','narration':'同学们好，今天学习二次函数。','visuals':[{'kind':'文字卡','description':'函数表达式'}]*(7 if observed_job.kind=='rewrite' else 1),'evidence_ids':[],'content_kind':'knowledge'}]}
        monkeypatch.setattr('app.outline.service.chat_json',chat)
        await execute_outline_job(db,job,isolated)
        await db.commit()
        await db.refresh(p)
        assert p.status=='outline_ready' and p.revision==2
        assert len(p.outline['segments'][0]['visuals']) == 1
        assert p.outline['segments'][0]['estimated_duration_seconds']>1
        assert calls==[Purpose.outline_llm,Purpose.review_llm]
        job.status='succeeded';await db.commit()
        # Recreate all persistence clients during confirmation, proving restart recovery.
        await save_outline(db,p.owner_id,p.id,OutlineSave(revision=p.revision,segments=p.outline['segments']))
        confirmed=await confirm_outline(db,p.owner_id,p.id,p.revision,isolated)
        assert confirmed.status=='outline_confirmed'
        assert calls==[Purpose.outline_llm,Purpose.review_llm]
        # A finished confirmation graph must also accept later reordered saved drafts.
        p.outline={**p.outline,'segments':[{**p.outline['segments'][0],'title':'再次确认的稿件'}]}
        p.status='outline_ready';await db.commit()
        await save_outline(db,p.owner_id,p.id,OutlineSave(revision=p.revision,segments=p.outline['segments']))
        await confirm_outline(db,p.owner_id,p.id,p.revision,isolated)
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from app.outline.service import checkpoint_url,thread_id
        from app.outline.graph import build_outline_graph
        async with AsyncPostgresSaver.from_conn_string(checkpoint_url(isolated)) as saver:
            async def unused(state):raise AssertionError('确认不调用模型')
            snapshot=await build_outline_graph(saver,unused,unused).aget_state({'configurable':{'thread_id':thread_id(p.owner_id,p.id,job.id)}})
            assert snapshot.values['outline']==p.outline
            assert snapshot.values['confirmed'] is True
        # A fresh durable graph for a selected rewrite preserves identity and resumes confirmation.
        rewrite=await create_job(db,p,'rewrite','integration-rewrite',{'form_version':version,'segment_ids':[sid],'instruction':'简洁清晰'})
        rewrite.status='running';rewrite.lease_token=uuid4();await db.commit()
        observed_job=rewrite
        await execute_outline_job(db,rewrite,isolated);await db.commit();await db.refresh(p)
        assert p.outline['segments'][0]['id']==sid
        assert p.outline['segments'][0]['content_revision']==2
        assert len(p.outline['segments'][0]['visuals']) == 7
        assert p.outline['segments'][0]['reviewed_revision']==2
        rewrite.status='succeeded';await db.commit()
        await save_outline(db,p.owner_id,p.id,OutlineSave(revision=p.revision,segments=p.outline['segments']))
        assert (await confirm_outline(db,p.owner_id,p.id,p.revision,isolated)).status=='outline_confirmed'
    finally:
        await db.rollback()
        await db.execute(text('DROP SCHEMA '+schema+' CASCADE'));await db.commit()

async def test_material_multiple_uploads_and_private_download(teacher_client,admin_client,monkeypatch,settings):
    import io
    from docx import Document
    doc=Document();doc.add_paragraph('教学资料');stream=io.BytesIO();doc.save(stream)
    objects={}
    class Storage:
        def __init__(self,settings):pass
        def put(self,key,data,mime):objects[key]=data
        def get(self,key):return objects[key]
        def delete(self,key):objects.pop(key,None)
    monkeypatch.setattr('app.materials.router.MaterialStorage',Storage)
    p=(await teacher_client.post('/api/projects',json={'prompt':'数学'})).json()
    path='/api/projects/'+p['id']+'/materials'
    ids=[]
    for i in range(2):
        response=await teacher_client.post(path,headers={'Origin':'http://test'},files={'file':(f'课件{i}.docx',stream.getvalue())})
        assert response.status_code==201,response.text
        ids.append(response.json()['id'])
    assert len(objects)==2
    assert (await admin_client.get(path+'/'+ids[0]+'/download')).status_code==404
    assert (await teacher_client.get(path+'/'+ids[0]+'/download')).content==stream.getvalue()

async def test_provider_error_is_not_rewritten_as_invalid_outline(db, teacher_client, settings, monkeypatch):
    import httpx
    from app.outline.model_client import chat_json as real_chat
    from app.jobs.tasks import run_job
    schema = 'agent_test_' + uuid4().hex
    isolated = settings.model_copy(update={'agent_schema': schema})
    await initialize_agent_state(isolated)
    try:
        response = await teacher_client.post('/api/projects', json={'prompt': '串联电路'})
        project = await db.get(VideoProject, UUID(response.json()['id']))
        old_outline = {'segments': []}
        project.outline = old_outline
        version = (await teacher_client.get('/api/config/form')).json()['form_version']
        job = await create_job(db, project, 'generate', 'provider-error', {'segment_ids': [], 'instruction': '', 'form_version': version})
        await db.commit()
        revision = project.revision
        async def resolve(db, box, purpose):
            if purpose not in (Purpose.outline_llm, Purpose.review_llm):
                return None
            return ResolvedConfig(purpose, 'https://model.example/v1', 'private-test-key', 'test', {})
        monkeypatch.setattr('app.outline.service.resolve', resolve)
        requests = []
        def respond(request):
            requests.append(request)
            return httpx.Response(401, json={'error': {'message': 'private-test-key'}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            async def chat(config, messages, *args, **kwargs):
                kwargs['client'] = http
                return await real_chat(config, messages, *args, **kwargs)
            monkeypatch.setattr('app.outline.service.chat_json', chat)
            await run_job(job.id, isolated)
        await db.refresh(job)
        await db.refresh(project)
        assert job.status == 'failed'
        assert '401' in job.error_message and '认证失败' in job.error_message
        assert '结构' not in job.error_message and 'private-test-key' not in job.error_message
        assert len(requests) == 1
        assert project.outline == old_outline and project.revision == revision
    finally:
        await db.rollback()
        await db.execute(text('DROP SCHEMA ' + schema + ' CASCADE'))
        await db.commit()

async def test_review_failure_can_resume_without_regenerating_saved_checkpoint(db, teacher_client, settings, monkeypatch):
    from app.outline.model_client import ModelCallError
    from app.jobs.tasks import run_job
    schema = 'agent_test_' + uuid4().hex
    isolated = settings.model_copy(update={'agent_schema': schema})
    await initialize_agent_state(isolated)
    try:
        project_id = (await teacher_client.post('/api/projects', json={'prompt': '孔融让梨'})).json()['id']
        project = await db.get(VideoProject, UUID(project_id))
        old_outline = {'segments': []}
        project.outline = old_outline
        version = (await teacher_client.get('/api/config/form')).json()['form_version']
        job = await create_job(db, project, 'generate', 'resume-audit', {'segment_ids': [], 'instruction': '', 'form_version': version})
        await db.commit()
        initial_revision = project.revision
        sid = str(uuid4())
        calls = []
        fail_review = True
        async def resolve(db, box, purpose):
            if purpose not in (Purpose.outline_llm, Purpose.review_llm):
                return None
            return ResolvedConfig(purpose, 'https://model.example/v1', 'private-test-key', 'test', {})
        async def chat(config, messages, *args, **kwargs):
            calls.append(config.purpose)
            if config.purpose == Purpose.outline_llm:
                assert kwargs['request_retries'] == 2
                return {'segments': [{'id': sid, 'title': '让梨', 'objective': '理解故事', 'narration': '孔融把大梨让给哥哥。', 'visuals': [{'kind': '文字卡', 'description': '梨'}], 'evidence_ids': [], 'content_kind': 'reenactment'}]}
            if fail_review:
                raise ModelCallError('模型服务暂时异常（HTTP 503）', category='unavailable', status_code=503)
            return {'items': [{'segment_id': sid, 'passed': True, 'issues': [], 'notes': []}]}
        monkeypatch.setattr('app.outline.service.resolve', resolve)
        monkeypatch.setattr('app.outline.service.chat_json', chat)
        await run_job(job.id, isolated)
        await db.refresh(job)
        await db.refresh(project)
        assert job.status == 'failed' and job.progress == 80
        assert project.outline == old_outline and project.revision == initial_revision
        fail_review = False
        job.status = 'pending'
        await db.commit()
        await run_job(job.id, isolated)
        await db.refresh(job)
        await db.refresh(project)
        assert job.status == 'succeeded' and job.progress == 100
        assert project.revision == initial_revision + 1
        assert project.outline['segments'][0]['review_passed'] is True
        assert calls == [Purpose.outline_llm, Purpose.review_llm, Purpose.review_llm]
    finally:
        await db.rollback()
        await db.execute(text('DROP SCHEMA ' + schema + ' CASCADE'))
        await db.commit()
