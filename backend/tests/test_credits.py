import asyncio
from datetime import UTC,datetime,timedelta
from uuid import UUID

import pytest
from sqlalchemy import select
from conftest import login

ORIGIN={'Origin':'http://test'}

async def issue(admin_client,user_id,amount=100,**extra):
 r=await admin_client.post(f'/api/admin/users/{user_id}/credit-codes',headers=ORIGIN,json={'amount':amount,**extra})
 assert r.status_code==201,r.text
 return r.json()

async def teacher_id(client):
 return (await client.get('/api/auth/me')).json()['id']

async def test_new_account_zero_balance_and_empty_ledger(teacher_client):
 r=await teacher_client.get('/api/account/credits')
 assert r.status_code==200,r.text
 assert r.json()=={'balance':0,'reserved':0,'available':0,'video_cost':10,'total_credited':0,'total_spent':0}
 records=await teacher_client.get('/api/account/credits/transactions')
 assert records.status_code==200 and records.json()=={'items':[],'total':0}

async def test_bound_code_redeems_once_and_records_balance(admin_client,teacher_client):
 uid=await teacher_id(teacher_client);code=await issue(admin_client,uid,125)
 assert code['amount']==125 and code['user_id']==uid and code['status']=='available'
 r=await teacher_client.post('/api/account/credits/redeem',headers=ORIGIN,json={'code':code['code'].lower().replace('-',' ')})
 assert r.status_code==200,r.text
 assert r.json()['available']==125 and r.json()['total_credited']==125
 again=await teacher_client.post('/api/account/credits/redeem',headers=ORIGIN,json={'code':code['code']})
 assert again.status_code==409
 records=(await teacher_client.get('/api/account/credits/transactions?type=income')).json()
 assert records['total']==1 and records['items'][0]['amount']==125 and records['items'][0]['balance_after']==125
 assert records['items'][0]['kind']=='redemption'
 listed=(await admin_client.get(f'/api/admin/users/{uid}/credit-codes')).json()
 assert listed['items'][0]['status']=='redeemed' and code['code'] not in str(listed)
 assert (await teacher_client.get('/api/account/credits/transactions?type=expense')).json()['total']==0

async def test_wrong_user_invalid_expired_and_revoked_codes_never_credit(app,make_client,make_user,teacher_client,admin_client,db):
 from app.models import CreditCode
 uid=await teacher_id(teacher_client);other=await make_user('another_credit_user')
 code=await issue(admin_client,str(other.id))
 r=await teacher_client.post('/api/account/credits/redeem',headers=ORIGIN,json={'code':code['code']})
 assert r.status_code==400 and other.username not in r.text
 own=await issue(admin_client,uid)
 row=await db.get(CreditCode,UUID(own['id']));row.expires_at=datetime.now(UTC)-timedelta(seconds=1);await db.commit()
 assert (await teacher_client.post('/api/account/credits/redeem',headers=ORIGIN,json={'code':own['code']})).status_code==400
 rev=await issue(admin_client,uid)
 assert (await admin_client.post(f"/api/admin/credit-codes/{rev['id']}/revoke",headers=ORIGIN)).status_code==200
 assert (await teacher_client.post('/api/account/credits/redeem',headers=ORIGIN,json={'code':rev['code']})).status_code==400
 assert (await teacher_client.get('/api/account/credits')).json()['balance']==0
 assert (await teacher_client.get('/api/account/credits/transactions')).json()['total']==0

async def test_credit_authorization_validation_origin_and_rate_limit(client,teacher_client,admin_client):
 uid=await teacher_id(teacher_client)
 assert (await client.get('/api/account/credits')).status_code==401
 assert (await teacher_client.post(f'/api/admin/users/{uid}/credit-codes',headers=ORIGIN,json={'amount':100})).status_code==403
 assert (await admin_client.post(f'/api/admin/users/{uid}/credit-codes',headers=ORIGIN,json={'amount':0})).status_code==422
 assert (await admin_client.post(f'/api/admin/users/{uid}/credit-codes',headers=ORIGIN,json={'amount':1.5})).status_code==422
 assert (await teacher_client.post('/api/account/credits/redeem',json={'code':'invalid'})).status_code==403
 for _ in range(5):
  assert (await teacher_client.post('/api/account/credits/redeem',headers=ORIGIN,json={'code':'INVALID-CODE'})).status_code==400
 assert (await teacher_client.post('/api/account/credits/redeem',headers=ORIGIN,json={'code':'INVALID-CODE'})).status_code==429

@pytest.mark.parametrize('operation',['issue','revoke'])
async def test_admin_mutation_rechecks_role_after_concurrent_demotion(app,admin_client,teacher_client,db,monkeypatch,operation):
 from app.credits import router as credits_router
 from app.models import User,UserRole
 original=credits_router.lock_current_user
 uid=await teacher_id(teacher_client)
 existing=await issue(admin_client,uid)
 actor_id=(await admin_client.get('/api/auth/me')).json()['id']
 entered,proceed=asyncio.Event(),asyncio.Event()
 async def wait_after_dependency(request,session,actor):
  entered.set()
  await proceed.wait()
  return await original(request,session,actor)
 monkeypatch.setattr(credits_router,'lock_current_user',wait_after_dependency)
 path=f'/api/admin/users/{uid}/credit-codes' if operation=='issue' else f"/api/admin/credit-codes/{existing['id']}/revoke"
 pending=asyncio.create_task(admin_client.post(path,headers=ORIGIN,**({'json':{'amount':100}} if operation=='issue' else {})))
 try:
  await asyncio.wait_for(entered.wait(),5)
  async with app.state.sessionmaker() as other:
   actor=await other.get(User,UUID(actor_id));actor.role=UserRole.teacher;await other.commit()
 finally:
  proceed.set()
 response=await pending
 assert response.status_code==403,response.text
 from app.models import CreditCode
 rows=(await db.scalars(select(CreditCode).where(CreditCode.user_id==UUID(uid)))).all()
 assert len(rows)==1 and rows[0].revoked_at is None

async def test_concurrent_code_redeem_credits_exactly_once(app,make_client,teacher_client,admin_client):
 uid=await teacher_id(teacher_client);code=await issue(admin_client,uid,75)
 second=make_client(app);await login(second,'teacher1','pass1234')
 results=await asyncio.gather(*(c.post('/api/account/credits/redeem',headers=ORIGIN,json={'code':code['code']}) for c in (teacher_client,second)))
 assert sorted(r.status_code for r in results)==[200,409]
 assert (await teacher_client.get('/api/account/credits')).json()['balance']==75
 assert (await teacher_client.get('/api/account/credits/transactions')).json()['total']==1

async def test_ledger_pagination_and_user_isolation(admin_client,teacher_client,make_user,app,make_client):
 uid=await teacher_id(teacher_client)
 for amount in (11,22,33):
  code=await issue(admin_client,uid,amount)
  assert (await teacher_client.post('/api/account/credits/redeem',headers=ORIGIN,json={'code':code['code']})).status_code==200
 result=(await teacher_client.get('/api/account/credits/transactions?page=2&page_size=2')).json()
 assert result['total']==3 and len(result['items'])==1 and result['items'][0]['balance_after']==11
 await make_user('empty_wallet');other=make_client(app);await login(other,'empty_wallet','pass1234')
 assert (await other.get('/api/account/credits/transactions')).json()['total']==0
 assert (await other.get('/api/account/credits')).json()['balance']==0
