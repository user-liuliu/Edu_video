import asyncio
from copy import deepcopy
from datetime import datetime,UTC,timedelta
from uuid import UUID,uuid4
from unittest.mock import AsyncMock
import pytest
from sqlalchemy import select,func,update
from app.models import CreditWallet,CreditTransaction,OutlineJob
from app.presentations.models import PptProject,PptJob
from app.presentations import router,tasks,generation
from app.presentations.delivery import certify_pages
from app.presentations.knowledge import outline_digest,VERSION
from tests.test_ppt_text_editing import source
from tests.test_ppt_api import create
from app.settings_store import GenerationParams,put_generation_params

async def prepared(client,db,monkeypatch,credits=30):
    monkeypatch.setattr(router,'resolve',AsyncMock(return_value=object()))
    p=await create(client);row=await db.get(PptProject,UUID(p['id']));slide=source()
    outline={'slides':[{k:slide[k] for k in ('id','layout','title','content','slots')}]}
    outline['review']={'version':VERSION,'status':'passed','issues':[],'content_sha256':outline_digest(outline)}
    row.outline=outline;row.confirmed_revision=row.revision;row.status='outline_confirmed'
    wallet=await db.get(CreditWallet,row.owner_id)
    if not wallet:db.add(CreditWallet(owner_id=row.owner_id,balance=credits))
    else:wallet.balance=credits
    await db.commit()
    return row,'/api/presentations/'+str(row.id),slide

async def submit(client,base,revision=1,key='bill-once',kind='render',**extra):
    return await client.post(base+'/jobs/'+kind,json={'revision':revision,'idempotency_key':key,**extra})

async def balance(client):return (await client.get('/api/account/credits')).json()

async def complete(db,project,job,settings,progress):
    page=source();page['id']=project.outline['slides'][0]['id']
    return {'outline':deepcopy(project.outline),'pages':certify_pages([page],[b'actual-file-proof']),'warnings':[],'partial':False}

async def test_ppt_insufficient_balance_does_not_create_job(teacher_client,db,monkeypatch):
    row,base,_=await prepared(teacher_client,db,monkeypatch,9)
    result=await submit(teacher_client,base)
    assert result.status_code==409,result.text
    assert result.json()['detail']['code']=='insufficient_credits'
    assert not await db.scalar(select(PptJob.id))
    assert (await balance(teacher_client))['available']==9

async def test_ppt_reserves_ten_and_idempotent_replay_has_one_hold(teacher_client,db,monkeypatch):
    row,base,_=await prepared(teacher_client,db,monkeypatch)
    first=await submit(teacher_client,base);assert first.status_code==200,first.text
    again=await submit(teacher_client,base);assert again.json()['id']==first.json()['id']
    b=await balance(teacher_client)
    assert (b['balance'],b['reserved'],b['available'],b['total_spent'])==(30,10,20,0)
    assert b['ppt_cost']==10

async def test_ppt_success_settles_once_revise_costs_ten_and_ledger_survives_delete(teacher_client,db,settings,monkeypatch):
    row,base,_=await prepared(teacher_client,db,monkeypatch)
    monkeypatch.setattr(generation,'build_result',complete)
    job=(await submit(teacher_client,base)).json()
    await tasks.run_job(job['id'],settings);await tasks.run_job(job['id'],settings)
    b=await balance(teacher_client);assert (b['balance'],b['reserved'],b['total_spent'])==(20,0,10)
    current=(await teacher_client.get(base)).json()
    revised=await submit(teacher_client,base,revision=current['revision'],key='revise',kind='revise',slide_ids=[current['pages'][0]['id']],instruction='换个例子')
    assert revised.status_code==200,revised.text
    await tasks.run_job(revised.json()['id'],settings)
    b=await balance(teacher_client);assert (b['balance'],b['reserved'],b['total_spent'])==(10,0,20)
    expense=(await teacher_client.get('/api/account/credits/transactions?type=expense')).json()
    assert expense['total']==2 and all(x['kind']=='ppt_generation' and x['amount']==-10 for x in expense['items'])
    assert all('PPT' in x['description'] for x in expense['items'])
    current=(await teacher_client.get(base)).json()
    assert (await teacher_client.delete(base+'?revision='+str(current['revision']))).status_code==204
    assert (await teacher_client.get('/api/account/credits/transactions?type=expense')).json()['total']==2

@pytest.mark.parametrize('reason',['failure','exhaustion','cancelled','partial'])
async def test_ppt_unsuccessful_output_releases_without_debit(teacher_client,db,settings,monkeypatch,reason):
    row,base,_=await prepared(teacher_client,db,monkeypatch,10)
    job=(await submit(teacher_client,base)).json()
    if reason=='exhaustion':
        r=await db.get(PptJob,UUID(job['id']));r.attempts=99;await db.commit()
    elif reason=='cancelled':
        r=await db.get(PptJob,UUID(job['id']));r.status='cancelled';await db.commit()
    async def result(*args):
        if reason=='partial':return {**await complete(*args),'partial':True}
        raise generation.GenerationError('模拟生成失败')
    monkeypatch.setattr(generation,'build_result',result)
    await tasks.run_job(job['id'],settings);await tasks.run_job(job['id'],settings)
    b=await balance(teacher_client);assert (b['balance'],b['reserved'],b['available'],b['total_spent'])==(10,0,10,0)
    from app.presentations.models import PptCreditReservation
    hold=await db.get(PptCreditReservation,UUID(job['id']),populate_existing=True);assert hold.state=='released'

@pytest.mark.parametrize('kind',['outline','rewrite','check'])
async def test_ppt_outline_operations_are_free(teacher_client,db,monkeypatch,kind):
    row,base,slide=await prepared(teacher_client,db,monkeypatch,0)
    extra={'slide_ids':[slide['id']],'instruction':'改大纲'} if kind=='rewrite' else {}
    response=await submit(teacher_client,base,kind=kind,**extra)
    assert response.status_code==200,response.text
    assert (await balance(teacher_client))['reserved']==0

async def test_ppt_and_video_share_last_ten_credits(teacher_client,db,box,monkeypatch):
    row,base,_=await prepared(teacher_client,db,monkeypatch,10)
    from test_videos import ready_project
    _,video_path=await ready_project(db,teacher_client,box,credits=0)
    await put_generation_params(db,GenerationParams(max_concurrent_jobs=3))
    a,b=await asyncio.gather(submit(teacher_client,base),teacher_client.post(video_path,json={'revision':1,'idempotency_key':'video-race'}))
    assert sorted([a.status_code,b.status_code]) in ([200,409],[202,409])
    rejected=a if a.status_code==409 else b
    assert rejected.json()['detail']['code']=='insufficient_credits'
    state=await balance(teacher_client);assert (state['reserved'],state['available'])==(10,0)

async def test_preexisting_ppt_job_without_reservation_is_not_retroactively_charged(teacher_client,db,settings,monkeypatch):
    row,base,_=await prepared(teacher_client,db,monkeypatch,0)
    job=PptJob(owner_id=row.owner_id,project_id=row.id,kind='render',expected_revision=1,idempotency_key='legacy',payload={'slide_ids':[],'instruction':''})
    db.add(job);await db.commit();monkeypatch.setattr(generation,'build_result',complete)
    await tasks.run_job(job.id,settings)
    assert (await teacher_client.get(base)).json()['status']=='ready'
    assert (await balance(teacher_client))['total_spent']==0

async def test_stale_ppt_worker_cannot_settle_or_release_new_lease_hold(teacher_client,db,settings,monkeypatch):
    row,base,_=await prepared(teacher_client,db,monkeypatch,10)
    job=(await submit(teacher_client,base)).json();jid=UUID(job['id']);replacement=uuid4()
    async def steal(*args):
        await db.execute(update(PptJob).where(PptJob.id==jid).values(lease_token=replacement,lease_until=datetime.now(UTC)+timedelta(seconds=90)))
        await db.commit();return await complete(*args)
    monkeypatch.setattr(generation,'build_result',steal)
    await tasks.run_job(jid,settings)
    b=await balance(teacher_client);assert (b['balance'],b['reserved'],b['total_spent'])==(10,10,0)


async def test_ppt_settlement_failure_rolls_back_new_pages_and_debit_then_releases(teacher_client,db,settings,monkeypatch):
    row,base,_=await prepared(teacher_client,db,monkeypatch,20)
    monkeypatch.setattr(generation,'build_result',complete)
    job=(await submit(teacher_client,base)).json();original=tasks.settle_ppt
    async def fail_after_settle(session,current):
        await original(session,current)
        raise generation.GenerationError('模拟结算后发布失败')
    monkeypatch.setattr(tasks,'settle_ppt',fail_after_settle)
    await tasks.run_job(job['id'],settings)
    state=(await teacher_client.get(base)).json();assert state['job']['status']=='failed' and state['pages']==[]
    b=await balance(teacher_client);assert (b['balance'],b['reserved'],b['total_spent'])==(20,0,0)

async def test_ppt_manual_edit_and_export_are_free_with_zero_balance(teacher_client,db,monkeypatch):
    row,base,page=await prepared(teacher_client,db,monkeypatch,0)
    row.pages=certify_pages([page],[b'old-page']);row.rendered_revision=1;row.status='ready';await db.commit()
    saved=await teacher_client.patch(base+'/slides/'+page['id']+'/text',json={'revision':1,'edits':[{'key':'text-0','text':'教师修改'}]})
    assert saved.status_code==200,saved.text
    exported=await teacher_client.get(base+'/export');assert exported.status_code==200,exported.text
    assert (await balance(teacher_client))['total_spent']==0
    assert not (await teacher_client.get('/api/account/credits/transactions?type=expense')).json()['items']
