"""Credit mutations share their caller's transaction; never commit here."""
import hashlib
import re
import secrets
from datetime import UTC, datetime
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from app.errors import api_error
from app.models import CreditWallet, CreditTransaction, CreditCode, CreditReservation, OutlineJob
from .schemas import BalanceOut, CodeOut
from app.presentations.models import PptCreditReservation,PptJob

VIDEO_COST = 10
PPT_COST = 10
MAX_BALANCE = 2000000000

def normalize_code(code: str) -> str:
    return re.sub(r'[\s-]', '', code).upper()

def code_digest(code: str) -> str:
    return hashlib.sha256(normalize_code(code).encode()).hexdigest()

def generate_code() -> str:
    token = ''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(24))
    return 'EDU-' + '-'.join(token[i:i+6] for i in range(0,24,6))

def code_view(code: CreditCode) -> CodeOut:
    status = 'redeemed' if code.redeemed_at else 'revoked' if code.revoked_at else 'expired' if code.expires_at <= datetime.now(UTC) else 'available'
    return CodeOut(id=code.id,user_id=code.user_id,amount=code.amount,suffix=code.suffix,status=status,created_at=code.created_at,expires_at=code.expires_at,redeemed_at=code.redeemed_at)

async def lock_wallet(db, owner_id):
    await db.execute(insert(CreditWallet).values(owner_id=owner_id,balance=0).on_conflict_do_nothing())
    return await db.scalar(select(CreditWallet).where(CreditWallet.owner_id==owner_id).with_for_update().execution_options(populate_existing=True))

def active_holds(owner_id,model,job_model):
    return select(func.coalesce(func.sum(model.amount),0)).join(job_model,job_model.id==model.job_id).where(model.owner_id==owner_id,model.state=='reserved',job_model.status.in_(['pending','running'])).scalar_subquery()

async def reserved_total(db,owner_id):
    return int(await db.scalar(select(active_holds(owner_id,CreditReservation,OutlineJob)+active_holds(owner_id,PptCreditReservation,PptJob))) or 0)

async def balance_view(db,owner_id):
    # One statement gives balance, holds and totals a consistent snapshot.
    balance = select(CreditWallet.balance).where(CreditWallet.owner_id==owner_id).scalar_subquery()
    held = active_holds(owner_id,CreditReservation,OutlineJob)+active_holds(owner_id,PptCreditReservation,PptJob)
    income = select(func.coalesce(func.sum(CreditTransaction.amount),0)).where(CreditTransaction.owner_id==owner_id,CreditTransaction.amount>0).scalar_subquery()
    spent = select(func.coalesce(func.sum(CreditTransaction.amount),0)).where(CreditTransaction.owner_id==owner_id,CreditTransaction.amount<0).scalar_subquery()
    balance,reserved,income,spent = (await db.execute(select(func.coalesce(balance,0),held,income,spent))).one()
    return BalanceOut(balance=balance,reserved=reserved,available=balance-reserved,total_credited=income,total_spent=-spent)

async def redeem(db,owner_id,raw):
    wallet=await lock_wallet(db,owner_id)
    code=await db.scalar(select(CreditCode).where(CreditCode.digest==code_digest(raw),CreditCode.user_id==owner_id).with_for_update().execution_options(populate_existing=True))
    if not code or code.revoked_at or code.expires_at<=datetime.now(UTC):
        raise api_error(400,'invalid_credit_code','兑换码无效或已过期，请确认由管理员为当前账户生成')
    if code.redeemed_at:
        raise api_error(409,'credit_code_used','该兑换码已经使用，请勿重复兑换')
    if wallet.balance + code.amount > MAX_BALANCE:
        raise api_error(409,'credit_balance_limit','积分余额已达上限，请联系管理员')
    wallet.balance += code.amount
    code.redeemed_at=datetime.now(UTC)
    db.add(CreditTransaction(owner_id=owner_id,kind='redemption',source_id=code.id,description='兑换码充值 · 尾号 '+code.suffix,amount=code.amount,balance_after=wallet.balance))
    await db.flush()

async def reserve_generation(db,job,title,model,cost,label):
    wallet=await lock_wallet(db,job.owner_id)
    if await db.get(model,job.id): return
    available=wallet.balance-await reserved_total(db,job.owner_id)
    if available<cost:
        raise api_error(409,'insufficient_credits',f'积分不足，本次生成需要 {cost} 积分，当前可用 {available} 积分，请先前往账户余额兑换积分')
    db.add(model(job_id=job.id,owner_id=job.owner_id,amount=cost,description=(label+' · '+title)[:240]))
    await db.flush()

async def settle_generation(db,job,model,kind):
    wallet=await lock_wallet(db,job.owner_id)
    hold=await db.scalar(select(model).where(model.job_id==job.id).with_for_update().execution_options(populate_existing=True))
    if not hold or hold.state!='reserved': return
    if wallet.balance<hold.amount: raise ValueError('积分结算失败，请联系管理员')
    wallet.balance-=hold.amount;hold.state='settled'
    db.add(CreditTransaction(owner_id=job.owner_id,kind=kind,source_id=job.id,description=hold.description,amount=-hold.amount,balance_after=wallet.balance))
    await db.flush()

async def release_generation(db,job,model):
    # Active holds alone affect available credits; release is idempotent.
    await lock_wallet(db,job.owner_id)
    hold=await db.scalar(select(model).where(model.job_id==job.id).with_for_update().execution_options(populate_existing=True))
    if hold and hold.state=='reserved': hold.state='released'
    await db.flush()


async def reserve_video(db,job,title):await reserve_generation(db,job,title,CreditReservation,VIDEO_COST,'视频生成')
async def settle_video(db,job):await settle_generation(db,job,CreditReservation,'video_generation')
async def release_video(db,job):await release_generation(db,job,CreditReservation)

async def reserve_ppt(db,job,title):await reserve_generation(db,job,title,PptCreditReservation,PPT_COST,'PPT 生成')
async def settle_ppt(db,job):await settle_generation(db,job,PptCreditReservation,'ppt_generation')
async def release_ppt(db,job):await release_generation(db,job,PptCreditReservation)
