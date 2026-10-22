import asyncio
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_active_user
from app.auth.deps import SESSION_VERSION
from app.auth.login_limiter import LoginLimiter
from app.auth.schemas import UserOut
from app.db import get_session
from app.errors import api_error
from app.jobs.dispatcher import enqueue_object_cleanup
from app.materials.storage import MaterialStorage
from app.models import User
from app.redis_client import get_redis
from app.security import hash_password, verify_password

from .avatar import MAX_AVATAR_BYTES, normalize_avatar
from .schemas import ChangePasswordRequest, ProfilePatch

router = APIRouter(prefix="/api/account", tags=["account"])


def check_origin(request: Request) -> None:
    origin = request.headers.get("origin", "")
    expected = urlsplit(str(request.base_url))
    try:
        actual = urlsplit(origin)
        actual.port
    except ValueError:
        raise api_error(403, "invalid_origin", "请求来源无效，请从本站操作") from None

    def normalized(url):
        return url.scheme, url.hostname, url.port or (443 if url.scheme == "https" else 80)

    if (
        not origin
        or normalized(actual) != normalized(expected)
        or actual.username
        or actual.path not in ("", "/")
        or actual.query
        or actual.fragment
    ):
        raise api_error(403, "invalid_origin", "请求来源无效，请从本站操作")


class PasswordChangeLimiter(LoginLimiter):
    @staticmethod
    def _user_key(user_id: str) -> str:
        return f"password_change_fail:u:{user_id}"

    @staticmethod
    def _ip_key(ip: str) -> str:
        return f"password_change_fail:ip:{ip}"


async def lock_current_user(request: Request, db: AsyncSession, user: User) -> User:
    # Recheck session and account status after waiting for concurrent mutations.
    locked = await db.scalar(
        select(User).where(User.id == user.id).with_for_update().execution_options(populate_existing=True)
    )
    if locked is None or request.session.get(SESSION_VERSION) != locked.session_version:
        request.session.clear()
        raise api_error(401, "not_authenticated", "请先登录")
    await require_active_user(locked)
    return locked


@router.get("/profile")
async def get_profile(user: User = Depends(require_active_user)) -> UserOut:
    return UserOut.model_validate(user)


@router.patch("/profile")
async def update_profile(
    request: Request,
    body: ProfilePatch,
    db: AsyncSession = Depends(get_session),
    user: User = Depends(require_active_user),
) -> UserOut:
    check_origin(request)
    user = await lock_current_user(request, db, user)
    for field in body.model_fields_set:
        setattr(user, field, getattr(body, field))
    await db.commit()
    await db.refresh(user)
    return UserOut.model_validate(user)


@router.post("/avatar")
async def upload_avatar(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_session),
    user: User = Depends(require_active_user),
) -> UserOut:
    check_origin(request)
    data = bytearray()
    while chunk := await file.read(64 * 1024):
        data.extend(chunk)
        if len(data) > MAX_AVATAR_BYTES:
            raise api_error(413, "avatar_too_large", "头像不能超过 2 MiB")
    try:
        normalized = await asyncio.to_thread(normalize_avatar, bytes(data))
    except ValueError as error:
        raise api_error(422, "invalid_avatar", str(error)) from None

    key = f"users/{user.id}/profile/avatar/{uuid4()}.png"
    settings = request.app.state.settings
    try:
        storage = MaterialStorage(settings)
        await asyncio.to_thread(storage.put, key, normalized, "image/png")
    except Exception:
        raise api_error(503, "storage_unavailable", "头像存储暂不可用，请稍后重试") from None

    try:
        user = await lock_current_user(request, db, user)
        previous_key = user.avatar_key
        user.avatar_key = key
        if previous_key:
            await enqueue_object_cleanup(db, [previous_key])
        result = UserOut.model_validate(user)
        await db.commit()
    except Exception as error:
        await db.rollback()
        try:
            await asyncio.to_thread(storage.delete, key)
        except Exception:
            await enqueue_object_cleanup(db, [key])
            await db.commit()
        if isinstance(error, HTTPException):
            raise
        raise api_error(503, "avatar_save_failed", "头像保存失败，请重试") from None
    return result


@router.delete("/avatar", status_code=204)
async def delete_avatar(
    request: Request,
    db: AsyncSession = Depends(get_session),
    user: User = Depends(require_active_user),
) -> Response:
    check_origin(request)
    user = await lock_current_user(request, db, user)
    if user.avatar_key:
        await enqueue_object_cleanup(db, [user.avatar_key])
        user.avatar_key = None
        await db.commit()
    return Response(status_code=204)


@router.get("/avatar")
async def get_avatar(
    request: Request,
    user: User = Depends(require_active_user),
) -> Response:
    if not user.avatar_key:
        raise api_error(404, "avatar_not_found", "尚未设置头像")
    try:
        data = await asyncio.to_thread(MaterialStorage(request.app.state.settings).get, user.avatar_key)
    except Exception:
        raise api_error(503, "storage_unavailable", "头像暂时无法读取，请稍后重试") from None
    return Response(
        data,
        media_type="image/png",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.post("/password", status_code=204)
async def change_password(
    request: Request,
    body: ChangePasswordRequest,
    db: AsyncSession = Depends(get_session),
    user: User = Depends(require_active_user),
    redis: Redis = Depends(get_redis),
) -> Response:
    check_origin(request)
    user_id = str(user.id)
    ip = request.client.host if request.client else "unknown"
    limiter = PasswordChangeLimiter(redis)
    if not await limiter.reserve_attempt(user_id, ip):
        raise api_error(429, "password_change_locked", "原密码验证次数过多，请稍后再试（最长 15 分钟）")
    locked_user = await lock_current_user(request, db, user)
    if not locked_user or not await asyncio.to_thread(verify_password, body.current_password, locked_user.password_hash):
        await db.rollback()
        raise api_error(401, "invalid_current_password", "原密码不正确")
    await limiter.release_success(user_id, ip)
    if await asyncio.to_thread(verify_password, body.new_password, locked_user.password_hash):
        await db.rollback()
        raise api_error(409, "password_unchanged", "新密码不能与原密码相同")

    locked_user.password_hash = await asyncio.to_thread(hash_password, body.new_password)
    locked_user.session_version += 1
    next_session_version = locked_user.session_version
    await db.commit()
    request.session[SESSION_VERSION] = next_session_version
    return Response(status_code=204)
