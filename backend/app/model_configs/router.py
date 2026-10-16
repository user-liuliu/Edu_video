"""管理后台：模型配置（各用途的接口地址、API key、模型名称、音色）。"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.db import get_session
from app.purposes import Purpose
from app.security import SecretBox, get_secret_box

from .schemas import ModelConfigUpdate, ModelConfigView
from .service import list_configs, update_config

router = APIRouter(
    prefix="/api/admin/model-configs", tags=["admin"], dependencies=[Depends(require_admin)]
)

DB = Annotated[AsyncSession, Depends(get_session)]
Box = Annotated[SecretBox, Depends(get_secret_box)]


@router.get("")
async def read_model_configs(db: DB, box: Box) -> list[ModelConfigView]:
    return await list_configs(db, box)


@router.put("/{purpose}")
async def update_model_config(
    purpose: Purpose, body: ModelConfigUpdate, db: DB, box: Box
) -> ModelConfigView:
    return await update_config(db, box, purpose, body)
