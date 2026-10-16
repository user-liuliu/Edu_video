"""管理后台：系统设置（注册开关）。"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.db import get_session
from app.settings_store import RegistrationSettings, get_registration, put_registration

router = APIRouter(
    prefix="/api/admin/settings", tags=["admin"], dependencies=[Depends(require_admin)]
)

DB = Annotated[AsyncSession, Depends(get_session)]


@router.get("/registration")
async def read_registration(db: DB) -> RegistrationSettings:
    return await get_registration(db)


@router.put("/registration")
async def update_registration(body: RegistrationSettings, db: DB) -> RegistrationSettings:
    return await put_registration(db, body)
