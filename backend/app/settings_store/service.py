"""系统设置的读写：每项设置存成 system_settings 表里的一行 JSONB。"""

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SystemSetting

from .defaults import DEFAULT_FORM_FIELDS
from .schemas import FormFieldsConfig, GenerationParams, RegistrationSettings

FORM_FIELDS_KEY = "form_fields"
GENERATION_PARAMS_KEY = "generation_params"
REGISTRATION_KEY = "registration"


async def _get[M: BaseModel](db: AsyncSession, key: str, model: type[M], default: M) -> M:
    # 只查 value 列，不经过 ORM 对象的身份映射，避免拿到会话里缓存的旧值
    row = (
        await db.execute(select(SystemSetting.value).where(SystemSetting.key == key))
    ).one_or_none()
    if row is None:
        return default.model_copy(deep=True)
    return model.model_validate(row.value)


async def _put[M: BaseModel](db: AsyncSession, key: str, value: M) -> M:
    # 重新校验一遍：模型实例构造后可能被直接改过字段（赋值不会触发校验）
    checked = type(value).model_validate(value.model_dump())
    data = checked.model_dump(mode="json")
    stmt = insert(SystemSetting).values(key=key, value=data)
    stmt = stmt.on_conflict_do_update(
        index_elements=[SystemSetting.key],
        set_={"value": stmt.excluded.value, "updated_at": func.now()},
    )
    await db.execute(stmt)
    await db.commit()
    return checked


async def get_form_fields(db: AsyncSession) -> FormFieldsConfig:
    return await _get(db, FORM_FIELDS_KEY, FormFieldsConfig, DEFAULT_FORM_FIELDS)


async def put_form_fields(db: AsyncSession, cfg: FormFieldsConfig) -> FormFieldsConfig:
    return await _put(db, FORM_FIELDS_KEY, cfg)


async def get_generation_params(db: AsyncSession) -> GenerationParams:
    return await _get(db, GENERATION_PARAMS_KEY, GenerationParams, GenerationParams())


async def put_generation_params(db: AsyncSession, p: GenerationParams) -> GenerationParams:
    return await _put(db, GENERATION_PARAMS_KEY, p)


async def get_registration(db: AsyncSession) -> RegistrationSettings:
    return await _get(db, REGISTRATION_KEY, RegistrationSettings, RegistrationSettings())


async def put_registration(db: AsyncSession, r: RegistrationSettings) -> RegistrationSettings:
    return await _put(db, REGISTRATION_KEY, r)
