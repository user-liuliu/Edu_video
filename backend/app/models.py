"""数据库模型：用户、系统设置、模型配置。"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# 固定约束命名规则，让迁移里的约束名稳定、可预期
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UserRole(StrEnum):
    teacher = "teacher"
    admin = "admin"


class UserStatus(StrEnum):
    pending = "pending"
    active = "active"
    rejected = "rejected"
    disabled = "disabled"


def _str_enum(enum_cls: type[StrEnum]) -> Enum:
    """存成普通 VARCHAR（不建 PG 原生枚举类型、不加 CHECK），值为小写字符串。"""
    return Enum(
        enum_cls,
        native_enum=False,
        create_constraint=False,
        values_callable=lambda e: [m.value for m in e],
        length=16,
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(32))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(
        _str_enum(UserRole), default=UserRole.teacher, server_default=UserRole.teacher.value
    )
    status: Mapped[UserStatus] = mapped_column(
        _str_enum(UserStatus), default=UserStatus.pending, server_default=UserStatus.pending.value
    )
    # 改密码、禁用等操作时加一，使旧会话失效
    session_version: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))


# 用户名不区分大小写唯一
Index("ix_users_username_lower", func.lower(User.username), unique=True)


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[Any] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ModelConfigRow(Base):
    __tablename__ = "model_configs"

    purpose: Mapped[str] = mapped_column(String(32), primary_key=True)
    base_url: Mapped[str] = mapped_column(String(512), default="", server_default="")
    api_key_encrypted: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(128), default="", server_default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    extra: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    last_test_ok: Mapped[bool | None] = mapped_column(Boolean)
    last_test_message: Mapped[str | None] = mapped_column(Text)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
