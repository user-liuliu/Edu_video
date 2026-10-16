"""会话校验依赖：当前用户、只允许 active 用户、只允许管理员。"""

import uuid
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.errors import api_error
from app.models import User, UserRole, UserStatus

SESSION_UID = "uid"
SESSION_VERSION = "sv"

_INACTIVE_ERRORS: dict[UserStatus, tuple[str, str]] = {
    UserStatus.pending: ("account_pending", "账号正在等待管理员审核"),
    UserStatus.rejected: ("account_rejected", "注册申请未通过"),
    UserStatus.disabled: ("account_disabled", "账号已被停用"),
}


async def get_current_user(
    request: Request, db: Annotated[AsyncSession, Depends(get_session)]
) -> User:
    """会话里没有用户、用户不存在或会话版本过期时，清空会话并返回 401。"""
    user: User | None = None
    raw_uid = request.session.get(SESSION_UID)
    if isinstance(raw_uid, str):
        try:
            user = await db.get(User, uuid.UUID(raw_uid))
        except ValueError:
            user = None
    if user is None or request.session.get(SESSION_VERSION) != user.session_version:
        request.session.clear()
        raise api_error(401, "not_authenticated", "请先登录")
    return user


async def require_active_user(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.status != UserStatus.active:
        code, message = _INACTIVE_ERRORS.get(user.status, ("account_disabled", "账号已被停用"))
        raise api_error(403, code, message)
    return user


async def require_admin(user: Annotated[User, Depends(require_active_user)]) -> User:
    if user.role != UserRole.admin:
        raise api_error(403, "forbidden", "没有权限执行此操作")
    return user
