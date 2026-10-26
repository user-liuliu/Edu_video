from datetime import UTC,datetime,timedelta
from uuid import UUID,uuid4
from copy import deepcopy
import json

import pytest
from sqlalchemy import select,func,update

from app.jobs.tasks import run_job
from app.jobs.service import count_active_generation_jobs
from app.models import OutlineJob,VideoVersion,VideoProject,CreditReservation
from app.settings_store import GenerationParams,put_generation_params
from test_direct_pipeline import prepare
from app.outline.review import mark_saved


async def test_many_intentional_batches_keep_one_job_hold_and_capacity_with_zero_retry_budget(db,teacher_client,box,settings,monkeypatch):
    from app.jobs.continuation import ContinueJob
    project,path,store,renderer,counts,calls=await prepare(db,teacher_client,box,settings,monkeypatch)
    await put_generation_params(db,GenerationParams(max_retries=0));await db.commit()
    response=await teacher_client.post(path,json={'revision':1,'idempotency_key':'continued'})
    job_id=UUID(response.json()['job']['id']);version_id=UUID(response.json()['id']);runs=[]
    async def execute(session,job,settings):
        runs.append(job.id)
        if len(runs)<=5:raise ContinueJob('正在恢复下一批')
        version=await session.get(VideoVersion,version_id);version.status='preview_ready'
        project=await session.get(VideoProject,job.project_id);project.status='preview_ready'
    monkeypatch.setattr('app.videos.pipeline.execute_video_job',execute)
    for _ in range(5):
        await run_job(job_id,settings)
        job=await db.get(OutlineJob,job_id,populate_existing=True)
        hold=await db.get(CreditReservation,job_id,populate_existing=True)
        assert job.status=='pending' and job.attempts==0
        assert job.lease_token is None and job.lease_until is None and job.dispatched_at is None
        assert hold.state=='reserved'
        assert await count_active_generation_jobs(db,project.owner_id)==1
        await db.commit()
    await run_job(job_id,settings);await run_job(job_id,settings)
    assert len(runs)==6 and len(set(runs))==1
    assert (await teacher_client.get('/api/account/credits/transactions?type=expense')).json()['total']==1
    assert (await teacher_client.get(path+'/'+str(version_id))).json()['status']=='preview_ready'


async def test_stale_worker_cannot_requeue_or_release_new_lease(db,teacher_client,box,settings,monkeypatch):
    from app.jobs.continuation import ContinueJob
    from app.db import create_sessionmaker
    project,path,*_=await prepare(db,teacher_client,box,settings,monkeypatch)
    result=(await teacher_client.post(path,json={'revision':1,'idempotency_key':'stale-continuation'})).json()
    job_id=UUID(result['job']['id']);replacement=uuid4()
    async def execute(session,job,settings):
        async with create_sessionmaker(db.bind)() as other:
            await other.execute(update(OutlineJob).where(OutlineJob.id==job_id).values(lease_token=replacement,lease_until=datetime.now(UTC)+timedelta(seconds=90)))
            await other.commit()
        raise ContinueJob('下一批')
    monkeypatch.setattr('app.videos.pipeline.execute_video_job',execute)
    await run_job(job_id,settings)
    job=await db.get(OutlineJob,job_id,populate_existing=True)
    assert job.status=='running' and job.lease_token==replacement
    assert (await db.get(CreditReservation,job_id,populate_existing=True)).state=='reserved'


async def multi_project(db,teacher_client,box,settings,monkeypatch):
    project,path,store,renderer,counts,calls=await prepare(db,teacher_client,box,settings,monkeypatch)
    first=deepcopy(project.outline['segments'][0])
    first['estimated_duration_seconds']=100
    project.outline=mark_saved({'segments':[{**deepcopy(first),'id':str(uuid4()),'position':i} for i in range(3)]})
    await db.commit()
    # Exercise the real generator; replace only its external provider boundary.
    import app.videos.direct_pipeline as pipeline
    from app.videos.film_modules import generate_film as generate_html
    monkeypatch.setattr(pipeline,'generate_html',generate_html)
    return project,path,store,renderer,counts


async def test_failed_partial_generation_retry_version_resumes_prefix_without_rewriting(db,teacher_client,box,settings,monkeypatch):
    project,path,store,renderer,counts=await multi_project(db,teacher_client,box,settings,monkeypatch)
    from app.outline.model_client import ModelCallError
    from test_film_generation_recovery import response
    seen=[];fail=[True]
    async def provider(http,url,headers,payload,**kwargs):
        user=json.loads(payload['messages'][1]['content']);keys=[t['render_key'] for t in user['segments']];seen.extend(keys)
        key=keys[0];position=int(key.split('-')[-1])
        if position==1 and fail[0]:raise ModelCallError('服务不可用',category='unavailable')
        part={'id':key,'html':'<svg><text>'+key+'</text></svg>','code':';'}
        if position==0:return response({'shared_html':'','shared_code':'return {};','segments':[part],'transitions':[]})
        return response({'segments':[part],'transitions':[{'from_id':f'segment-{position-1}','to_id':key,'duration':.5,'mode':'dissolve','code':';'}]})
    monkeypatch.setattr('app.videos.model_stream.animation_response',provider)
    result=(await teacher_client.post(path,json={'revision':1,'idempotency_key':'partial-failure'})).json()
    await run_job(result['job']['id'],settings)
    failed=await db.get(VideoVersion,UUID(result['id']),populate_existing=True)
    assert failed.status=='failed'
    checkpoint=deepcopy(failed.snapshot['animation_checkpoint']);assert len(checkpoint['parts'])==1
    assert checkpoint['shared']['key'] in failed.asset_keys
    assert (await db.get(CreditReservation,UUID(result['job']['id']),populate_existing=True)).state=='released'
    fail[0]=False;seen.clear()
    retried=await teacher_client.post(path,json={'revision':1,'idempotency_key':'partial-resume','retry_version_id':result['id']})
    assert retried.status_code==202,retried.text
    resumed=retried.json()
    for _ in range(4):
        await run_job(resumed['job']['id'],settings)
        job=await db.get(OutlineJob,UUID(resumed['job']['id']),populate_existing=True)
        if job.status!='pending':break
        await db.commit()
    value=(await teacher_client.get(path+'/'+resumed['id'])).json()
    assert value['status']=='preview_ready',value
    assert seen==['segment-1','segment-2'] and counts['speech']==3
    saved=await db.get(VideoVersion,UUID(resumed['id']),populate_existing=True)
    assert saved.snapshot['animation_checkpoint']['parts'][0]==checkpoint['parts'][0]
    assert (await teacher_client.get('/api/account/credits/transactions?type=expense')).json()['total']==1
    # Project deletion owns both source and retry references and cleans all keys.
    all_keys=set(store.files)
    deleted=await teacher_client.delete(f'/api/projects/{project.id}?revision=1');assert deleted.status_code==204
    from app.models import ObjectCleanup
    cleanup=set((await db.scalars(select(ObjectCleanup.object_key))).all())
    assert all_keys<=cleanup


async def test_slow_audio_yields_after_saved_pair_and_next_claim_reuses_audio_without_new_html(db,teacher_client,box,settings,monkeypatch):
    import app.videos.direct_pipeline as pipeline
    project,path,store,renderer,counts,calls=await prepare(db,teacher_client,box,settings,monkeypatch)
    first=deepcopy(project.outline['segments'][0])
    project.outline=mark_saved({'segments':[{**deepcopy(first),'id':str(uuid4()),'position':i} for i in range(3)]});await db.commit()
    ticks=[0.]
    monkeypatch.setattr(pipeline,'batch_clock',lambda:ticks[0],raising=False)
    import app.videos.pipeline as shared
    speech=shared.synthesize_narration
    async def slow(*args,**kwargs):
        ticks[0]+=310
        return await speech(*args,**kwargs)
    monkeypatch.setattr(shared,'synthesize_narration',slow)
    result=(await teacher_client.post(path,json={'revision':1,'idempotency_key':'slow-audio'})).json()
    await run_job(result['job']['id'],settings)
    job=await db.get(OutlineJob,UUID(result['job']['id']),populate_existing=True)
    assert job.status=='pending' and counts['speech']==1
    assert (await db.get(CreditReservation,job.id,populate_existing=True)).state=='reserved'
    await db.commit()
    for _ in range(4):
        await run_job(result['job']['id'],settings)
        job=await db.get(OutlineJob,job.id,populate_existing=True)
        if job.status!='pending':break
        await db.commit()
    assert (await teacher_client.get(path+'/'+result['id'])).json()['status']=='preview_ready'
    assert counts['speech']==3 and len(calls)==1


async def test_expired_lease_cannot_yield_and_is_recovered_with_checkpoint_intact(db,teacher_client,box,settings,monkeypatch):
    from app.jobs.continuation import requeue_continuation
    project,path,*_=await prepare(db,teacher_client,box,settings,monkeypatch)
    result=(await teacher_client.post(path,json={'revision':1,'idempotency_key':'expired-batch'})).json()
    job=await db.get(OutlineJob,UUID(result['job']['id']));token=uuid4()
    job.status='running';job.lease_token=token;job.lease_until=datetime.now(UTC)-timedelta(seconds=1);job.attempts=1
    row=await db.get(VideoVersion,UUID(result['id']));row.snapshot={**row.snapshot,'animation_checkpoint':{'proof':'preserved'}}
    await db.commit()
    assert not await requeue_continuation(db,job.id,token,'stale yield')
    job=await db.get(OutlineJob,job.id,populate_existing=True);assert job.status=='running' and job.attempts==1
    await db.commit()
    async def verify(session,claimed,settings):
        row=await session.get(VideoVersion,UUID(result['id']))
        assert row.snapshot['animation_checkpoint']=={'proof':'preserved'}
        row.status='preview_ready'
    monkeypatch.setattr('app.videos.pipeline.execute_video_job',verify)
    await run_job(job.id,settings)
    job=await db.get(OutlineJob,job.id,populate_existing=True)
    assert job.status=='succeeded' and job.attempts==2


async def test_saved_batches_are_dispatched_by_existing_outbox(db,teacher_client,box,settings,monkeypatch):
    from app.jobs.continuation import ContinueJob
    from app.jobs.dispatcher import dispatch_pending
    project,path,*_=await prepare(db,teacher_client,box,settings,monkeypatch)
    result=(await teacher_client.post(path,json={'revision':1,'idempotency_key':'outbox-batch'})).json()
    job_id=UUID(result['job']['id'])
    async def yield_once(*args):raise ContinueJob('动画已完成 2/6 段')
    monkeypatch.setattr('app.videos.pipeline.execute_video_job',yield_once)
    await run_job(job_id,settings)
    sent=[]
    await dispatch_pending(db,sent.append)
    assert sent==[str(job_id)]
    again=[];await dispatch_pending(db,again.append);assert again==[]


async def test_slow_runtime_repair_yields_after_saved_html_and_keeps_repair_budget(db,teacher_client,box,settings,monkeypatch):
    import app.videos.direct_pipeline as pipeline
    from app.videos.render_contract import DirectHtmlRuntimeError
    project,path,store,renderer,counts,calls=await prepare(db,teacher_client,box,settings,monkeypatch)
    ticks=[0.];monkeypatch.setattr(pipeline,'batch_clock',lambda:ticks[0],raising=False)
    original_generate=pipeline.generate_html
    async def slow_repair(config,request,http,**kwargs):
        if request.get('previous_film_bundle'):ticks[0]+=310
        return await original_generate(config,request,http,**kwargs)
    monkeypatch.setattr(pipeline,'generate_html',slow_repair)
    async def invalid(*args,**kwargs):raise DirectHtmlRuntimeError('持续的代码错误')
    renderer.direct=invalid
    result=(await teacher_client.post(path,json={'revision':1,'idempotency_key':'slow-repair'})).json()
    await run_job(result['job']['id'],settings)
    job=await db.get(OutlineJob,UUID(result['job']['id']),populate_existing=True)
    assert job.status=='pending'
    row=await db.get(VideoVersion,UUID(result['id']),populate_existing=True)
    assert row.snapshot['direct_source']['repair_attempts']==1
    await db.commit()
    for _ in range(4):
        await run_job(job.id,settings)
        job=await db.get(OutlineJob,job.id,populate_existing=True)
        if job.status!='pending':break
        await db.commit()
    assert job.status=='failed' and len(calls)==3 and counts['speech']==1
    assert (await db.get(CreditReservation,job.id,populate_existing=True)).state=='released'


@pytest.mark.parametrize('slow_kind',['audio','raw_html'])
async def test_slow_cache_replay_without_new_work_never_yields_forever(db,teacher_client,box,settings,monkeypatch,slow_kind):
    import app.videos.direct_pipeline as pipeline
    project,path,store,renderer,counts,calls=await prepare(db,teacher_client,box,settings,monkeypatch)
    first=deepcopy(project.outline['segments'][0])
    project.outline=mark_saved({'segments':[{**deepcopy(first),'id':str(uuid4()),'position':i} for i in range(4)]});await db.commit()
    renderer.fail=True
    initial=(await teacher_client.post(path,json={'revision':1,'idempotency_key':'cache-replay-source'})).json()
    await run_job(initial['job']['id'],settings)
    assert (await teacher_client.get(path+'/'+initial['id'])).json()['status']=='failed'
    assert counts['speech']==4 and len(calls)==1
    renderer.fail=False
    ticks=[0.];monkeypatch.setattr(pipeline,'batch_clock',lambda:ticks[0],raising=False)
    real_read=pipeline.read_asset
    async def slow_read(storage,key,digest,kind):
        if kind==slow_kind:ticks[0]+=101 if slow_kind=='audio' else 310
        return await real_read(storage,key,digest,kind)
    monkeypatch.setattr(pipeline,'read_asset',slow_read)
    retry=await teacher_client.post(path,json={'revision':1,'idempotency_key':'slow-cache-retry','retry_version_id':initial['id']})
    assert retry.status_code==202,retry.text
    result=retry.json()
    await run_job(result['job']['id'],settings)
    value=(await teacher_client.get(path+'/'+result['id'])).json()
    assert value['status']=='preview_ready',value
    assert counts['speech']==4 and len(calls)==1
    assert (await teacher_client.get('/api/account/credits/transactions?type=expense')).json()['total']==1


async def test_five_minute_ten_module_job_completes_across_batches_without_repeat_calls_or_charges(db,teacher_client,box,settings,monkeypatch):
    import io,wave
    from app.videos.speech import Narration
    from app.videos.direct_html import validate_manifest
    from test_film_generation_recovery import response
    project,path,store,renderer,counts=await multi_project(db,teacher_client,box,settings,monkeypatch)
    first=deepcopy(project.outline['segments'][0]);first['estimated_duration_seconds']=30
    project.outline=mark_saved({'segments':[{**deepcopy(first),'id':str(uuid4()),'position':i} for i in range(10)]})
    await put_generation_params(db,GenerationParams(max_retries=0));await db.commit()
    audio=io.BytesIO()
    with wave.open(audio,'wb') as wav:
        wav.setparams((1,2,48000,0,'NONE','not compressed'));wav.writeframes(bytes(30*48000*2))
    spoken=[];requested=[]
    async def speech(config,text,*args,**kwargs):
        spoken.append(text);return Narration(audio.getvalue(),[{'start':0.,'end':30.,'text':text}])
    monkeypatch.setattr('app.videos.pipeline.synthesize_narration',speech)
    async def provider(http,url,headers,payload,**kwargs):
        user=json.loads(payload['messages'][1]['content']);key=user['segments'][0]['render_key'];requested.append(key)
        position=int(key.split('-')[-1])
        part={'id':key,'html':'<svg><text>'+key+'</text></svg>','code':';'}
        if position==0:return response({'shared_html':'','shared_code':'return {};','segments':[part],'transitions':[]})
        assert user['previous_segment_context']['end']==position*30
        return response({'segments':[part],'transitions':[{'from_id':f'segment-{position-1}','to_id':key,'duration':.5,'mode':'dissolve','code':';'}]})
    monkeypatch.setattr('app.videos.model_stream.animation_response',provider)
    result=(await teacher_client.post(path,json={'revision':1,'idempotency_key':'five-minutes'})).json()
    job_id=UUID(result['job']['id']);stages=[]
    for _ in range(8):
        await run_job(job_id,settings)
        job=await db.get(OutlineJob,job_id,populate_existing=True);stages.append(job.status)
        if job.status!='pending':break
        assert (await db.get(CreditReservation,job_id,populate_existing=True)).state=='reserved'
        assert job.attempts==0 and await count_active_generation_jobs(db,project.owner_id)==1
        await db.commit()
    assert stages==['pending']*4+['succeeded']
    assert requested==[f'segment-{i}' for i in range(10)] and len(spoken)==10
    version=await db.get(VideoVersion,UUID(result['id']),populate_existing=True)
    assert version.status=='preview_ready' and version.duration==300.
    timeline=version.snapshot['direct_manifest']['timeline'];validate_manifest(timeline)
    assert timeline['source_duration']==300. and timeline['duration']==300.
    assert len(version.snapshot['animation_checkpoint']['parts'])==10
    assert (await teacher_client.get('/api/account/credits/transactions?type=expense')).json()['total']==1


async def test_slow_new_expression_yields_after_freeze_and_next_claim_does_not_repeat_expression(db,teacher_client,box,settings,monkeypatch):
    import app.videos.direct_pipeline as pipeline
    import app.videos.expression as expression
    project,path,store,renderer,counts,calls=await prepare(db,teacher_client,box,settings,monkeypatch)
    ticks=[0.];monkeypatch.setattr(pipeline,'batch_clock',lambda:ticks[0],raising=False)
    build=expression.build_expression;built=[]
    async def slow(*args,**kwargs):
        built.append(True);ticks[0]+=310;return await build(*args,**kwargs)
    monkeypatch.setattr(expression,'build_expression',slow)
    result=(await teacher_client.post(path,json={'revision':1,'idempotency_key':'slow-expression'})).json()
    await run_job(result['job']['id'],settings)
    job=await db.get(OutlineJob,UUID(result['job']['id']),populate_existing=True)
    assert job.status=='pending' and not calls and counts['speech']==0
    row=await db.get(VideoVersion,UUID(result['id']),populate_existing=True)
    assert row.snapshot['film_expression']['segments'] and len(built)==1
    await db.commit()
    await run_job(job.id,settings)
    assert (await teacher_client.get(path+'/'+result['id'])).json()['status']=='preview_ready'
    assert len(built)==1 and len(calls)==1 and counts['speech']==1
