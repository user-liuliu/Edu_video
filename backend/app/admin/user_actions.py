"""管理员对用户的操作：审核、停用/启用、重置密码、修改角色。"""

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import api_error
from app.models import User, UserRole, UserStatus
from app.security import hash_password

LAST_ADMIN_MESSAGE = "系统至少需要保留一个管理员"


class UserAction(StrEnum):
    approve = "approve"
    reject = "reject"
    disable = "disable"
    enable = "enable"


# 每个操作允许的起始状态，以及执行后的状态
_TRANSITIONS: dict[UserAction, tuple[frozenset[UserStatus], UserStatus]] = {
    UserAction.approve: (frozenset({UserStatus.pending, UserStatus.rejected}), UserStatus.active),
    UserAction.reject: (frozenset({UserStatus.pending}), UserStatus.rejected),
    UserAction.disable: (frozenset({UserStatus.active}), UserStatus.disabled),
    UserAction.enable: (frozenset({UserStatus.disabled}), UserStatus.active),
}
_REVIEW_ACTIONS = frozenset({UserAction.approve, UserAction.reject})

_ACTIVE_ADMIN = (User.role == UserRole.admin, User.status == UserStatus.active)


async def _lock_active_admins(db: AsyncSession) -> None:
    """锁住所有正常状态的管理员行（按 id 顺序加锁，避免死锁）。

    并发地停用或降级两个不同的管理员时，后一个请求要等前一个提交后再数人数，
    这样"至少保留一个管理员"的检查不会被绕过。
    """
    await db.execute(select(User.id).where(*_ACTIVE_ADMIN).order_by(User.id).with_for_update())


async def _lock_target(db: AsyncSession, target_id: uuid.UUID) -> User:
    """锁住并重新读取目标用户；用户不存在返回 404。

    populate_existing：目标可能就是当前管理员本人，会话里已有这个对象，要用加锁后读到的最新值覆盖。
    """
    stmt = (
        select(User)
        .where(User.id == target_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    user = (await db.execute(stmt)).scalar_one_or_none()
    if user is None:
        raise api_error(404, "user_not_found", "用户不存在")
    return user


async def _ensure_admin_remains(db: AsyncSession) -> None:
    """在提交前数一下改动后的正常管理员人数；变成 0 就回滚并返回 409。"""
    await db.flush()
    count = await db.scalar(select(func.count()).select_from(User).where(*_ACTIVE_ADMIN))
    if not count:
        await db.rollback()
        raise api_error(409, "last_admin", LAST_ADMIN_MESSAGE)


async def apply_user_action(
    db: AsyncSession, actor: User, target_id: uuid.UUID, action: UserAction
) -> User:
    if action == UserAction.disable:
        await _lock_active_admins(db)
    user = await _lock_target(db, target_id)

    allowed_from, new_status = _TRANSITIONS[action]
    if user.status not in allowed_from:
        raise api_error(409, "invalid_transition", "当前状态下不能执行这个操作")

    user.status = new_status
    if action in _REVIEW_ACTIONS:
        user.reviewed_at = datetime.now(UTC)
        user.reviewed_by = actor.id
    if action == UserAction.disable:
        user.session_version += 1  # 让该用户已有的会话失效
        await _ensure_admin_remains(db)
    await db.commit()
    return user


async def reset_password(db: AsyncSession, target_id: uuid.UUID, new_password: str) -> None:
    password_hash = hash_password(new_password)  # 先算哈希（较慢），再加锁
    user = await _lock_target(db, target_id)
    user.password_hash = password_hash
    user.session_version += 1  # 让该用户已有的会话失效
    await db.commit()


async def set_role(db: AsyncSession, target_id: uuid.UUID, role: UserRole) -> User:
    await _lock_active_admins(db)
    user = await _lock_target(db, target_id)
    user.role = role
    await _ensure_admin_remains(db)
    await db.commit()
    return user
