"""管理后台：模型配置（各用途的接口地址、API key、模型名称、音色）。"""

from typing import Annotated

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.db import get_session
from app.errors import api_error
from app.http_client import get_http
from app.purposes import Purpose
from app.security import SecretBox, get_secret_box

from .probe import ProbeResult, ProbeUnsupported, run_probe
from .schemas import ModelConfigUpdate, ModelConfigView
from .service import list_configs, record_test, resolve, update_config

router = APIRouter(
    prefix="/api/admin/model-configs", tags=["admin"], dependencies=[Depends(require_admin)]
)

DB = Annotated[AsyncSession, Depends(get_session)]
Box = Annotated[SecretBox, Depends(get_secret_box)]
Http = Annotated[httpx.AsyncClient, Depends(get_http)]


@router.get("")
async def read_model_configs(db: DB, box: Box) -> list[ModelConfigView]:
    return await list_configs(db, box)


@router.put("/{purpose}")
async def update_model_config(
    purpose: Purpose, body: ModelConfigUpdate, db: DB, box: Box
) -> ModelConfigView:
    return await update_config(db, box, purpose, body)


@router.post("/{purpose}/test")
async def probe_model_config(purpose: Purpose, db: DB, box: Box, http: Http) -> ProbeResult:
    """向接口发一个最小的请求，记录并返回结果。没启用的配置也可以测。"""
    cfg = await resolve(db, box, purpose, require_enabled=False)
    if cfg is None:
        message = '请先填写接口地址和 API Key' if purpose == Purpose.web_search else '请先填写接口地址、API key 和模型名称'
        raise api_error(409, "config_incomplete", message)
    # 结束只读事务，免得等待接口响应时一直占着数据库连接上的事务
    await db.rollback()
    try:
        result = await run_probe(http, cfg)
    except ProbeUnsupported:
        raise api_error(400, "probe_unsupported", "这种用途暂不支持测试连接") from None
    await record_test(db, purpose, result.ok, result.message)
    return result
