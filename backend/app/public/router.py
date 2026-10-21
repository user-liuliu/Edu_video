"""老师端：新建视频页面的表单配置。

只返回管理员设为显示的表单项，不返回生成参数，也不返回任何模型配置（地址、模型、key）。
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_active_user
from app.db import get_session
from app.model_configs import list_voices, resolve, system_available
from app.purposes import Purpose
from app.security import SecretBox, get_secret_box
from app.settings_store import FieldKey, FieldOption, get_form_fields
from app.settings_store.form_values import form_version

router = APIRouter(prefix="/api/config", tags=["public"])

DB = Annotated[AsyncSession, Depends(get_session)]
Box = Annotated[SecretBox, Depends(get_secret_box)]


class PublicField(BaseModel):
    key: FieldKey
    label: str
    default: str | bool | None
    options: list[FieldOption]
    default_by_subject: dict[str, str]


class PublicFormConfig(BaseModel):
    form_version: str
    # 必需的模型都配好了才能生成视频；老师端据此提示“系统暂不可用”
    system_available: bool
    fields: list[PublicField]


async def build_public_form(db: AsyncSession, box: SecretBox) -> PublicFormConfig:
    cfg = await get_form_fields(db)
    from app.videos.system_speech import voice_options
    voices = await voice_options(db,box)
    web_search_ready = await resolve(db, box, Purpose.web_search) is not None

    fields: list[PublicField] = []
    for f in cfg.fields:
        if not f.visible:
            continue
        options, default = f.options, f.default
        if f.key == FieldKey.voice:
            # Include offline system speech independently of TTS configuration.
            if not voices:
                continue
            options = [FieldOption(value=v.speaker_id, label=v.label) for v in voices]
            default = f.default if f.default in [v.speaker_id for v in voices] else voices[0].speaker_id
        elif f.key == FieldKey.web_search and not web_search_ready:
            continue
        fields.append(
            PublicField(
                key=f.key,
                label=f.label,
                default=default,
                options=options,
                default_by_subject=f.default_by_subject,
            )
        )
    voice_field=next(f for f in cfg.fields if f.key==FieldKey.voice)
    default_voice=voice_field.default if voice_field.default in [v.speaker_id for v in voices] else (voices[0].speaker_id if voices else None)
    ready=await system_available(db,box,voice=default_voice if not voice_field.visible else None,allow_system_voice=voice_field.visible)
    return PublicFormConfig(form_version=form_version(cfg, voices, web_search_ready), system_available=ready, fields=fields)


@router.get("/form", dependencies=[Depends(require_active_user)])
async def read_form_config(db: DB, box: Box) -> PublicFormConfig:
    return await build_public_form(db, box)
