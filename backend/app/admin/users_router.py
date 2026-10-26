"""管理后台：用户列表、审核与停用、重置密码、修改角色。"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import UserOut, require_admin
from app.db import get_session
from app.models import User, UserStatus, VideoProject
from app.presentations.models import PptProject

from .schemas import ResetPasswordRequest, SetRoleRequest, UserActionRequest, UserListOut, AdminUserOut
from .user_actions import apply_user_action, reset_password, set_role

router = APIRouter(
    prefix="/api/admin/users", tags=["admin"], dependencies=[Depends(require_admin)]
)

DB = Annotated[AsyncSession, Depends(get_session)]
Admin = Annotated[User, Depends(require_admin)]


def _escape_like(raw: str) -> str:
    """把用户输入里的 LIKE 通配符当普通字符。"""
    return raw.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("")
async def list_users(
    db: DB,
    status: UserStatus | None = None,
    q: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> UserListOut:
    conditions = []
    if status is not None:
        conditions.append(User.status == status)
    if q and q.strip():
        conditions.append(User.username.ilike(f"%{_escape_like(q.strip())}%", escape="\\"))

    total = await db.scalar(select(func.count()).select_from(User).where(*conditions))
    stmt = (
        select(User)
        .where(*conditions)
        # 待审核的排最前，其余按注册时间倒序；id 兜底，让分页顺序稳定
        .order_by(
            case((User.status == UserStatus.pending, 0), else_=1),
            User.created_at.desc(),
            User.id,
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    users = (await db.execute(stmt)).scalars().all()
    counts = dict((await db.execute(select(VideoProject.owner_id,func.count()).where(VideoProject.owner_id.in_([u.id for u in users])).group_by(VideoProject.owner_id))).all()) if users else {}
    ppt_counts = dict((await db.execute(select(PptProject.owner_id,func.count()).where(PptProject.owner_id.in_([u.id for u in users])).group_by(PptProject.owner_id))).all()) if users else {}
    return UserListOut(items=[AdminUserOut(**UserOut.model_validate(u).model_dump(),video_count=counts.get(u.id,0),ppt_count=ppt_counts.get(u.id,0),project_count=counts.get(u.id,0)+ppt_counts.get(u.id,0)) for u in users], total=total or 0)


@router.post("/{user_id}/actions")
async def user_action(
    user_id: uuid.UUID, body: UserActionRequest, db: DB, actor: Admin
) -> UserOut:
    user = await apply_user_action(db, actor, user_id, body.action)
    return UserOut.model_validate(user)


@router.post("/{user_id}/password", status_code=204)
async def user_reset_password(user_id: uuid.UUID, body: ResetPasswordRequest, db: DB) -> Response:
    await reset_password(db, user_id, body.password)
    return Response(status_code=204)


@router.put("/{user_id}/role")
async def user_set_role(user_id: uuid.UUID, body: SetRoleRequest, db: DB) -> UserOut:
    user = await set_role(db, user_id, body.role)
    return UserOut.model_validate(user)
