from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select,func
from app.account.router import check_origin, lock_current_user
from app.auth import require_active_user, require_admin
from app.auth.login_limiter import LoginLimiter
from app.db import get_session
from app.errors import api_error
from app.models import CreditCode, CreditTransaction, User, UserStatus
from app.redis_client import get_redis
from .schemas import BalanceOut, RedeemRequest, CodeRequest, IssuedCode, CodeList, CodeOut, TransactionList, TransactionOut
from .service import balance_view, code_digest, code_view, generate_code, redeem

router=APIRouter(tags=['credits'])

class RedemptionLimiter(LoginLimiter):
    @staticmethod
    def _user_key(value): return 'credit_redeem_fail:u:'+value
    @staticmethod
    def _ip_key(value): return 'credit_redeem_fail:ip:'+value

@router.get('/api/account/credits')
async def balance(db=Depends(get_session),user=Depends(require_active_user))->BalanceOut:
    return await balance_view(db,user.id)

@router.get('/api/account/credits/transactions')
async def transactions(db=Depends(get_session),user=Depends(require_active_user),page:Annotated[int,Query(ge=1)]=1,page_size:Annotated[int,Query(ge=1,le=100)]=20,type:Literal['all','income','expense']='all')->TransactionList:
    conditions=[CreditTransaction.owner_id==user.id]
    if type=='income':conditions.append(CreditTransaction.amount>0)
    if type=='expense':conditions.append(CreditTransaction.amount<0)
    total=await db.scalar(select(func.count()).select_from(CreditTransaction).where(*conditions))
    rows=(await db.scalars(select(CreditTransaction).where(*conditions).order_by(CreditTransaction.created_at.desc(),CreditTransaction.id.desc()).offset((page-1)*page_size).limit(page_size))).all()
    return TransactionList(items=[TransactionOut.model_validate(row) for row in rows],total=total or 0)

@router.post('/api/account/credits/redeem')
async def redeem_code(request:Request,body:RedeemRequest,db=Depends(get_session),user=Depends(require_active_user),redis=Depends(get_redis))->BalanceOut:
    check_origin(request)
    ip=request.client.host if request.client else 'unknown'
    limiter=RedemptionLimiter(redis)
    if not await limiter.reserve_attempt(str(user.id),ip):raise api_error(429,'credit_redeem_locked','兑换尝试过多，请 15 分钟后再试')
    await lock_current_user(request,db,user)
    await redeem(db,user.id,body.code)
    await db.commit()
    await limiter.release_success(str(user.id),ip)
    return await balance_view(db,user.id)

@router.post('/api/admin/users/{user_id}/credit-codes',status_code=201)
async def issue_code(user_id:UUID,request:Request,body:CodeRequest,db=Depends(get_session),actor=Depends(require_admin))->IssuedCode:
    check_origin(request)
    actor = await lock_current_user(request,db,actor)
    await require_admin(actor)
    user=await db.get(User,user_id)
    if not user or user.status!=UserStatus.active:raise api_error(409,'credit_user_inactive','只能为正常状态的用户生成兑换码')
    raw=generate_code()
    row=CreditCode(user_id=user_id,created_by=actor.id,digest=code_digest(raw),suffix=raw[-4:],amount=body.amount,expires_at=datetime.now(UTC)+timedelta(days=body.expires_in_days))
    db.add(row);await db.commit();await db.refresh(row)
    return IssuedCode(**code_view(row).model_dump(),code=raw)

@router.get('/api/admin/users/{user_id}/credit-codes')
async def codes(user_id:UUID,db=Depends(get_session),actor=Depends(require_admin),page:Annotated[int,Query(ge=1)]=1)->CodeList:
    if not await db.get(User,user_id):raise api_error(404,'user_not_found','用户不存在')
    total=await db.scalar(select(func.count()).select_from(CreditCode).where(CreditCode.user_id==user_id))
    rows=(await db.scalars(select(CreditCode).where(CreditCode.user_id==user_id).order_by(CreditCode.created_at.desc(),CreditCode.id.desc()).offset((page-1)*20).limit(20))).all()
    return CodeList(items=[code_view(row) for row in rows],total=total or 0)

@router.post('/api/admin/credit-codes/{code_id}/revoke')
async def revoke(code_id:UUID,request:Request,db=Depends(get_session),actor=Depends(require_admin))->CodeOut:
    check_origin(request)
    actor = await lock_current_user(request,db,actor)
    await require_admin(actor)
    row=await db.scalar(select(CreditCode).where(CreditCode.id==code_id).with_for_update())
    if not row:raise api_error(404,'credit_code_not_found','兑换码不存在')
    if row.redeemed_at:raise api_error(409,'credit_code_used','已兑换的兑换码不能停用')
    row.revoked_at=row.revoked_at or datetime.now(UTC)
    await db.commit();await db.refresh(row)
    return code_view(row)
