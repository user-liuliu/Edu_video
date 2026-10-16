"""管理后台：系统设置（注册开关、新建视频页面配置、生成参数）。"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.db import get_session
from app.settings_store import (
    FormFieldsConfig,
    GenerationParams,
    RegistrationSettings,
    get_form_fields,
    get_generation_params,
    get_registration,
    put_form_fields,
    put_generation_params,
    put_registration,
)

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


@router.get("/form-fields")
async def read_form_fields(db: DB) -> FormFieldsConfig:
    return await get_form_fields(db)


@router.put("/form-fields")
async def update_form_fields(body: FormFieldsConfig, db: DB) -> FormFieldsConfig:
    """校验失败（例如默认值不在可选值里）时由全局处理器返回 422。"""
    return await put_form_fields(db, body)


@router.get("/generation-params")
async def read_generation_params(db: DB) -> GenerationParams:
    return await get_generation_params(db)


@router.put("/generation-params")
async def update_generation_params(body: GenerationParams, db: DB) -> GenerationParams:
    return await put_generation_params(db, body)
