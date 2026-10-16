"""注册、登录、退出、查看当前用户。"""

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.errors import api_error
from app.models import User, UserRole, UserStatus
from app.redis_client import get_redis
from app.security import hash_password, verify_password
from app.settings_store import get_registration

from .deps import SESSION_UID, SESSION_VERSION, get_current_user
from .login_limiter import LoginLimiter
from .schemas import LoginRequest, RegisterRequest, UserOut, normalize_username

router = APIRouter(prefix="/api/auth", tags=["auth"])

# 用户名不存在时也跑一次 argon2 校验，让耗时和"密码错误"接近，避免借响应时间探测用户名
_DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(16))

DB = Annotated[AsyncSession, Depends(get_session)]


async def _username_taken(db: AsyncSession, name: str) -> bool:
    stmt = select(User.id).where(func.lower(User.username) == name.lower())
    return (await db.execute(stmt)).first() is not None


def _username_taken_error() -> HTTPException:
    return api_error(409, "username_taken", "用户名已被占用")


@router.post("/register", status_code=201)
async def register(body: RegisterRequest, db: DB) -> UserOut:
    if not (await get_registration(db)).open:
        raise api_error(403, "registration_closed", "暂未开放注册")
    if await _username_taken(db, body.username):
        raise _username_taken_error()
    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        role=UserRole.teacher,
        status=UserStatus.pending,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        # 并发注册同名用户：查重时还没有，插入时撞上唯一索引
        await db.rollback()
        raise _username_taken_error() from None
    await db.refresh(user)  # 取回数据库生成的 created_at
    return UserOut.model_validate(user)


@router.post("/login")
async def login(
    body: LoginRequest,
    request: Request,
    db: DB,
    redis: Annotated[Redis, Depends(get_redis)],
) -> UserOut:
    name = normalize_username(body.username)
    ip = request.client.host if request.client else "unknown"
    limiter = LoginLimiter(redis)
    # 先占用一次尝试（原子计数）再查库和校验密码，并发请求也会被阈值挡住
    if not await limiter.reserve_attempt(name, ip):
        raise api_error(429, "login_locked", "登录失败次数过多，请 15 分钟后再试")

    stmt = select(User).where(func.lower(User.username) == name.lower())
    user = (await db.execute(stmt)).scalar_one_or_none()
    if user is None:
        verify_password(body.password, _DUMMY_PASSWORD_HASH)
        ok = False
    else:
        ok = verify_password(body.password, user.password_hash)
    if not ok:
        # 这次尝试在 reserve_attempt 里已经计过数
        raise api_error(401, "invalid_credentials", "用户名或密码错误")

    await limiter.release_success(name, ip)
    request.session.clear()
    request.session[SESSION_UID] = str(user.id)
    request.session[SESSION_VERSION] = user.session_version
    return UserOut.model_validate(user)


@router.post("/logout", status_code=204)
async def logout(request: Request) -> Response:
    request.session.clear()
    return Response(status_code=204)


@router.get("/me")
async def me(user: Annotated[User, Depends(get_current_user)]) -> UserOut:
    return UserOut.model_validate(user)
