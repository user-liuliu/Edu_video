import asyncio
from datetime import UTC,datetime,timedelta
from uuid import UUID,uuid4
import pytest
from sqlalchemy import select,func
from app.jobs.tasks import run_job
from app.models import CreditWallet,CreditTransaction,CreditReservation,OutlineJob,VideoVersion,VideoProject
from app.settings_store import GenerationParams,put_generation_params
from test_videos import ready_project
from test_credits import issue,teacher_id,ORIGIN

async def funded_project(db,teacher_client,admin_client,box,amount=30):
    project,path=await ready_project(db,teacher_client,box,credits=0)
    code=await issue(admin_client,str(project.owner_id),amount)
    response=await teacher_client.post('/api/account/credits/redeem',headers=ORIGIN,json={'code':code['code']})
    assert response.status_code==200,response.text
    return project,path

async def submit(client,path,key='credit-once'):
    return await client.post(path,json={'revision':1,'idempotency_key':key})

async def test_insufficient_credits_creates_no_job_or_reservation(db,teacher_client,box):
    project,path=await ready_project(db,teacher_client,box,credits=0)
    response=await submit(teacher_client,path)
    assert response.status_code==409 and response.json()['detail']['code']=='insufficient_credits'
    assert not await db.scalar(select(OutlineJob.id).where(OutlineJob.kind=='video'))
    assert (await teacher_client.get('/api/account/credits')).json()['available']==0

async def test_submission_reserves_and_idempotent_replay_reserves_only_once(db,teacher_client,admin_client,box):
    project,path=await funded_project(db,teacher_client,admin_client,box)
    result=await submit(teacher_client,path);assert result.status_code==202,result.text
    repeated=await submit(teacher_client,path)
    assert repeated.status_code==202 and repeated.json()['id']==result.json()['id']
    balance=(await teacher_client.get('/api/account/credits')).json()
    assert (balance['balance'],balance['reserved'],balance['available'],balance['total_spent'])==(30,10,20,0)
    assert (await teacher_client.get('/api/account/credits/transactions?type=expense')).json()['total']==0

async def test_worker_success_charges_once_and_preserves_ledger_after_project_deletion(db,teacher_client,admin_client,box,settings,monkeypatch):
    project,path=await funded_project(db,teacher_client,admin_client,box)
    result=(await submit(teacher_client,path)).json();job_id=UUID(result['job']['id'])
    async def complete(db,job,settings):
        version=await db.scalar(select(VideoVersion).where(VideoVersion.job_id==job.id));version.status='preview_ready'
        owned=await db.get(VideoProject,job.project_id);owned.status='preview_ready'
    monkeypatch.setattr('app.videos.pipeline.execute_video_job',complete)
    await run_job(job_id,settings);await run_job(job_id,settings)
    balance=(await teacher_client.get('/api/account/credits')).json()
    assert (balance['balance'],balance['available'],balance['reserved'],balance['total_spent'])==(20,20,0,10)
    records=(await teacher_client.get('/api/account/credits/transactions?type=expense')).json()
    assert records['total']==1 and records['items'][0]['amount']==-10 and records['items'][0]['balance_after']==20
    assert '一次函数' in records['items'][0]['description']
    assert (await teacher_client.delete(f'/api/projects/{project.id}?revision=1')).status_code==204
    assert (await teacher_client.get('/api/account/credits/transactions?type=expense')).json()['total']==1

@pytest.mark.parametrize('exhausted',[False,True])
async def test_worker_failure_or_exhaustion_releases_without_charge(db,teacher_client,admin_client,box,settings,monkeypatch,exhausted):
    project,path=await funded_project(db,teacher_client,admin_client,box,10)
    result=(await submit(teacher_client,path)).json();job_id=UUID(result['job']['id'])
    async def fail(*args):raise ValueError('模拟生成失败')
    monkeypatch.setattr('app.videos.pipeline.execute_video_job',fail)
    if exhausted:
        job=await db.get(OutlineJob,job_id);job.attempts=99;await db.commit()
    await run_job(job_id,settings)
    balance=(await teacher_client.get('/api/account/credits')).json()
    assert (balance['balance'],balance['reserved'],balance['available'],balance['total_spent'])==(10,0,10,0)
    async with db.bind.connect() as conn:
        row=await conn.execute(select(CreditReservation.state).where(CreditReservation.job_id==job_id));assert row.scalar_one()=='released'

async def test_concurrent_last_ten_points_only_admits_one_video(db,teacher_client,admin_client,box):
    project,path=await funded_project(db,teacher_client,admin_client,box,10)
    other,other_path=await ready_project(db,teacher_client,box,credits=0)
    await put_generation_params(db,GenerationParams(max_concurrent_jobs=3))
    results=await asyncio.gather(submit(teacher_client,path,'first'),submit(teacher_client,other_path,'second'))
    assert sorted(r.status_code for r in results)==[202,409]
    rejected=next(r for r in results if r.status_code==409);assert rejected.json()['detail']['code']=='insufficient_credits'
    assert (await teacher_client.get('/api/account/credits')).json()['available']==0
    assert int(await db.scalar(select(func.count()).select_from(OutlineJob).where(OutlineJob.kind=='video')))==1

async def test_cancelled_hold_releases_without_execution_or_charge(db,teacher_client,admin_client,box,settings,monkeypatch):
    project,path=await funded_project(db,teacher_client,admin_client,box,10)
    result=(await submit(teacher_client,path)).json()
    job=await db.get(OutlineJob,UUID(result['job']['id']));job.status='cancelled';await db.commit()
    assert (await teacher_client.get('/api/account/credits')).json()['available']==10

    async def forbidden(*args):raise AssertionError('Cancelled jobs must not run')
    monkeypatch.setattr('app.videos.pipeline.execute_video_job',forbidden)
    await run_job(job.id,settings);await run_job(job.id,settings)
    async with db.bind.connect() as conn:
        state=await conn.scalar(select(CreditReservation.state).where(CreditReservation.job_id==job.id))
        assert state=='released'
    assert (await teacher_client.get('/api/account/credits/transactions?type=expense')).json()['total']==0

async def test_export_with_zero_available_credits_never_reserves_or_debits(db,teacher_client,admin_client,box,settings,monkeypatch):
    project,path=await funded_project(db,teacher_client,admin_client,box,10)
    result=(await submit(teacher_client,path)).json();job_id=UUID(result['job']['id'])
    async def complete(session,job,settings):
        version=await session.scalar(select(VideoVersion).where(VideoVersion.job_id==job.id))
        version.status='preview_ready';version.snapshot={**version.snapshot,'workflow':'html-preview-1'}
        owned=await session.get(VideoProject,job.project_id);owned.status='preview_ready'
    async def verified(*args):return None
    async def exported(*args):return None
    monkeypatch.setattr('app.videos.pipeline.execute_video_job',complete)
    monkeypatch.setattr('app.videos.direct_pipeline.verify_direct',verified)
    monkeypatch.setattr('app.videos.media.MaterialStorage',lambda settings:object())
    monkeypatch.setattr('app.videos.direct_pipeline.execute_direct_export',exported)
    await run_job(job_id,settings)
    response=await teacher_client.post(path+'/'+result['id']+'/export',json={'idempotency_key':'free-export'})
    assert response.status_code==202,response.text
    export_job=UUID(response.json()['id'])
    await run_job(export_job,settings)
    balance=(await teacher_client.get('/api/account/credits')).json()
    assert (balance['balance'],balance['reserved'],balance['total_spent'])==(0,0,10)
    assert (await teacher_client.get('/api/account/credits/transactions?type=expense')).json()['total']==1
    assert await db.get(CreditReservation,export_job) is None
