"""模型配置的读写：每种用途一行 model_configs，API key 用 SecretBox 加密保存。

库里没有的用途按 DEFAULTS 展示；第一次修改（或记录测试结果）时才建行。
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import api_error
from app.models import ModelConfigRow
from app.purposes import PURPOSE_LABELS, REQUIRED_PURPOSES, Purpose
from app.security import SecretBox, SecretDecryptError, mask_secret

from .schemas import ApiKeyStatus, ModelConfigUpdate, ModelConfigView, ResolvedConfig, Voice

# 每种用途的默认（base_url, model）
DEFAULTS: dict[Purpose, tuple[str, str]] = {
    p: ("", "") for p in Purpose
} | {
    Purpose.tts: ("https://openspeech.bytedance.com", "seed-audio-1.0"),
    Purpose.embedding: ("", "qwen3.7-text-embedding-flash"),
}

# 不需要填模型名称的用途
_MODEL_OPTIONAL: frozenset[Purpose] = frozenset({Purpose.web_search})

TEST_MESSAGE_MAX_LENGTH = 500

_PURPOSE_VALUES = frozenset(p.value for p in Purpose)


def _decrypt(box: SecretBox, ciphertext: str | None) -> tuple[ApiKeyStatus, str | None]:
    """返回 (状态, 明文)。解不开时不抛异常，状态为 undecryptable。"""
    if not ciphertext:
        return "missing", None
    try:
        return "set", box.decrypt(ciphertext)
    except SecretDecryptError:
        return "undecryptable", None


def _voices(extra: dict[str, Any] | None) -> list[Voice]:
    """从 extra 里读音色；格式不对的条目直接跳过。"""
    raw = (extra or {}).get("voices")
    if not isinstance(raw, list):
        return []
    voices: list[Voice] = []
    for item in raw:
        try:
            voices.append(Voice.model_validate(item))
        except ValueError:
            continue
    return voices


def _view(box: SecretBox, purpose: Purpose, row: ModelConfigRow | None) -> ModelConfigView:
    from app.videos.system_speech import available as system_voice_available
    if row is None:
        base_url, model = DEFAULTS[purpose]
        status, plain = "missing", None
        enabled, extra = False, {}
        last_ok = last_msg = last_at = None
    else:
        base_url, model = row.base_url, row.model
        status, plain = _decrypt(box, row.api_key_encrypted)
        enabled, extra = row.enabled, row.extra
        last_ok, last_msg, last_at = row.last_test_ok, row.last_test_message, row.last_tested_at
    return ModelConfigView(
        purpose=purpose,
        label=PURPOSE_LABELS[purpose],
        required=purpose in REQUIRED_PURPOSES and not (purpose==Purpose.tts and system_voice_available()),
        base_url=base_url,
        model=model,
        enabled=enabled,
        api_key_status=status,
        api_key_masked=mask_secret(plain) if plain is not None else None,
        voices=_voices(extra) if purpose == Purpose.tts else [],
        last_test_ok=last_ok,
        last_test_message=last_msg,
        last_tested_at=last_at,
    )


async def _load_rows(db: AsyncSession) -> dict[Purpose, ModelConfigRow]:
    # populate_existing：会话里缓存的旧对象也用库里的最新值刷新
    stmt = select(ModelConfigRow).execution_options(populate_existing=True)
    rows = (await db.execute(stmt)).scalars().all()
    return {Purpose(r.purpose): r for r in rows if r.purpose in _PURPOSE_VALUES}


async def _lock_row(db: AsyncSession, purpose: Purpose) -> ModelConfigRow:
    """没有就按默认值建行，然后 SELECT ... FOR UPDATE 锁住，避免并发修改互相覆盖。"""
    base_url, model = DEFAULTS[purpose]
    await db.execute(
        insert(ModelConfigRow)
        .values(purpose=purpose.value, base_url=base_url, model=model, enabled=False, extra={})
        .on_conflict_do_nothing(index_elements=[ModelConfigRow.purpose])
    )
    stmt = (
        select(ModelConfigRow)
        .where(ModelConfigRow.purpose == purpose.value)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return (await db.execute(stmt)).scalar_one()


def _resolve_row(
    box: SecretBox, purpose: Purpose, row: ModelConfigRow | None, *, require_enabled: bool
) -> ResolvedConfig | None:
    if row is None or (require_enabled and not row.enabled):
        return None
    _, api_key = _decrypt(box, row.api_key_encrypted)
    if api_key is None or not row.base_url:
        return None
    if not row.model and purpose not in _MODEL_OPTIONAL:
        return None
    return ResolvedConfig(
        purpose=purpose,
        base_url=row.base_url,
        api_key=api_key,
        model=row.model,
        extra=dict(row.extra or {}),
    )


async def list_configs(db: AsyncSession, box: SecretBox) -> list[ModelConfigView]:
    rows = await _load_rows(db)
    return [_view(box, p, rows.get(p)) for p in Purpose]


async def update_config(
    db: AsyncSession, box: SecretBox, purpose: Purpose | str, upd: ModelConfigUpdate
) -> ModelConfigView:
    purpose = Purpose(purpose)
    row = await _lock_row(db, purpose)
    try:
        _apply_update(box, purpose, row, upd)
    except Exception:
        await db.rollback()
        raise
    await db.commit()
    return _view(box, purpose, row)


def _apply_update(
    box: SecretBox, purpose: Purpose, row: ModelConfigRow, upd: ModelConfigUpdate
) -> None:
    """校验并把修改写到 row 上（不提交）。校验失败时抛 422。"""
    new_key = upd.api_key  # 已在 schema 里去掉首尾空白，空的变成 None
    clearing = upd.clear_api_key and new_key is None
    if upd.enabled:
        if new_key is not None:
            has_key = True
        elif clearing:
            has_key = False
        else:
            has_key = _decrypt(box, row.api_key_encrypted)[0] == "set"
        missing = []
        if not upd.base_url:
            missing.append("接口地址")
        if not has_key:
            missing.append("API key")
        if not upd.model and purpose not in _MODEL_OPTIONAL:
            missing.append("模型名称")
        if missing:
            raise api_error(
                422, "config_incomplete", f"启用前请先填写：{'、'.join(missing)}"
            )

    voices: list[Voice] | None = None
    if purpose == Purpose.tts:
        voices = upd.voices if upd.voices is not None else _voices(row.extra)
        ids = [v.speaker_id for v in voices]
        if len(set(ids)) != len(ids):
            raise api_error(422, "invalid_voices", "音色 ID 不能重复")
        if upd.enabled and not voices:
            raise api_error(422, "invalid_voices", "启用配音前至少要添加一个音色")

    key_changed = new_key is not None or (clearing and row.api_key_encrypted is not None)
    if key_changed or upd.base_url != row.base_url or upd.model != row.model:
        row.last_test_ok = None
        row.last_test_message = None
        row.last_tested_at = None

    if new_key is not None:
        row.api_key_encrypted = box.encrypt(new_key)
    elif clearing:
        row.api_key_encrypted = None
    row.base_url = upd.base_url
    row.model = upd.model
    row.enabled = upd.enabled
    if purpose == Purpose.tts and upd.voices is not None:
        # JSONB 要整体换成新 dict，原地修改不会被 ORM 发现
        row.extra = {**(row.extra or {}), "voices": [v.model_dump() for v in voices]}


async def resolve(
    db: AsyncSession, box: SecretBox, purpose: Purpose, *, require_enabled: bool = True
) -> ResolvedConfig | None:
    """取一项能直接调用的配置；没启用、没 key、key 解不开、地址或模型为空时返回 None。"""
    purpose = Purpose(purpose)
    stmt = (
        select(ModelConfigRow)
        .where(ModelConfigRow.purpose == purpose.value)
        .execution_options(populate_existing=True)
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    return _resolve_row(box, purpose, row, require_enabled=require_enabled)


async def system_available(db: AsyncSession, box: SecretBox, *, voice: str | None = None, allow_system_voice: bool = False) -> bool:
    """必需的用途都能用，并且最近一次测试没有失败（没测过也算可用）。"""
    rows = await _load_rows(db)
    from app.videos.system_speech import available,SYSTEM_VOICE
    offline=available() and (voice==SYSTEM_VOICE or allow_system_voice)
    for p in REQUIRED_PURPOSES:
        if p==Purpose.tts and offline:continue
        row = rows.get(p)
        if _resolve_row(box, p, row, require_enabled=True) is None:
            return False
        if row.last_test_ok is False:
            return False
    return True


async def list_voices(db: AsyncSession) -> list[Voice]:
    stmt = select(ModelConfigRow.extra).where(ModelConfigRow.purpose == Purpose.tts.value)
    extra = (await db.execute(stmt)).scalar_one_or_none()
    return _voices(extra)


async def record_test(db: AsyncSession, purpose: Purpose, ok: bool, message: str) -> None:
    """保存一次连通性测试的结果。message 不要带 API key。"""
    row = await _lock_row(db, Purpose(purpose))
    row.last_test_ok = ok
    row.last_test_message = message[:TEST_MESSAGE_MAX_LENGTH]
    row.last_tested_at = datetime.now(UTC)
    await db.commit()
