"""数据库模型：用户、系统设置、模型配置。"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Float,
    MetaData,
    String,
    Text,
    Uuid,
    UniqueConstraint,
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


class UserGender(StrEnum):
    unspecified = "unspecified"
    male = "male"
    female = "female"
    undisclosed = "undisclosed"


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
    display_name: Mapped[str | None] = mapped_column(String(40))
    gender: Mapped[UserGender] = mapped_column(
        _str_enum(UserGender), default=UserGender.unspecified, server_default=UserGender.unspecified.value
    )
    school: Mapped[str | None] = mapped_column(String(100))
    avatar_key: Mapped[str | None] = mapped_column(String(512))
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

    @property
    def avatar_url(self) -> str | None:
        return "/api/account/avatar" if self.avatar_key else None


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


class VideoProject(Base):
    __tablename__ = 'video_projects'

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('users.id'), index=True)
    title: Mapped[str] = mapped_column(String(200))
    prompt: Mapped[str] = mapped_column(Text)
    form_values: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    status: Mapped[str] = mapped_column(String(32), default='draft', server_default='draft')
    revision: Mapped[int] = mapped_column(Integer, default=1, server_default=text('1'))
    outline: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    needs_regeneration: Mapped[bool] = mapped_column(Boolean,default=False,server_default=text('false'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Material(Base):
    __tablename__ = 'materials'
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('users.id'), index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('video_projects.id', ondelete='CASCADE'), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    object_key: Mapped[str] = mapped_column(String(512))
    content_type: Mapped[str] = mapped_column(String(128))
    size: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default='pending', server_default='pending')
    error_message: Mapped[str | None] = mapped_column(Text)
    parse_warnings: Mapped[list[dict[str, str]]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MaterialChunk(Base):
    __tablename__ = 'material_chunks'
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('users.id'), index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('video_projects.id', ondelete='CASCADE'), index=True)
    material_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('materials.id', ondelete='CASCADE'), index=True)
    position: Mapped[int] = mapped_column(Integer)
    location: Mapped[str] = mapped_column(String(128))
    text: Mapped[str] = mapped_column(Text)
    image_key: Mapped[str | None] = mapped_column(String(512))


class OutlineJob(Base):
    __tablename__ = 'outline_jobs'
    __table_args__ = (UniqueConstraint('owner_id', 'project_id', 'kind', 'idempotency_key', name='uq_outline_jobs_request'),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('users.id'), index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('video_projects.id', ondelete='CASCADE'), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    expected_revision: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    status: Mapped[str] = mapped_column(String(32), default='pending', server_default='pending')
    stage: Mapped[str] = mapped_column(String(64), default='等待处理', server_default='等待处理')
    progress: Mapped[int] = mapped_column(Integer, default=0, server_default=text('0'))
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default=text('0'))
    error_message: Mapped[str | None] = mapped_column(Text)
    lease_token: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Evidence(Base):
    __tablename__ = 'evidence'
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('users.id'), index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('video_projects.id', ondelete='CASCADE'), index=True)
    claim: Mapped[str] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(32))
    source_ref: Mapped[str] = mapped_column(Text)
    location: Mapped[str] = mapped_column(String(128), default='', server_default='')
    excerpt: Mapped[str] = mapped_column(Text)
    source_grade: Mapped[str] = mapped_column(String(32))
    verification_status: Mapped[str] = mapped_column(String(32), default='unverified', server_default='unverified')


class Preference(Base):
    __tablename__ = 'preferences'
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('users.id'), index=True)
    category: Mapped[str] = mapped_column(String(32))
    value: Mapped[str] = mapped_column(String(200))
    accepted: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text('true'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ObjectCleanup(Base):
    __tablename__ = 'object_cleanup'
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    object_key: Mapped[str] = mapped_column(String(512), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class VideoVersion(Base):
    __tablename__ = 'video_versions'
    __table_args__ = (UniqueConstraint('project_id', 'number', name='uq_video_version_number'),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('users.id'), index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('video_projects.id', ondelete='CASCADE'), index=True)
    job_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('outline_jobs.id', ondelete='CASCADE'), unique=True)
    source_version_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey('video_versions.id', ondelete='SET NULL'))
    number: Mapped[int] = mapped_column(Integer)
    outline_revision: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default='queued', server_default='queued')
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    media_key: Mapped[str | None] = mapped_column(String(512))
    asset_keys: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    duration: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class VideoSegment(Base):
    __tablename__ = 'video_segments'
    __table_args__ = (UniqueConstraint('version_id', 'position', name='uq_video_segment_position'),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    version_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('video_versions.id', ondelete='CASCADE'), index=True)
    outline_segment_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    position: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200))
    narration: Mapped[str] = mapped_column(Text)
    start: Mapped[float | None] = mapped_column(Float)
    end: Mapped[float | None] = mapped_column(Float)
    fingerprint: Mapped[str] = mapped_column(String(64), default='', server_default='')
    assets: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))


class CreditWallet(Base):
    __tablename__ = 'credit_wallets'
    __table_args__ = (CheckConstraint('balance >= 0', name='nonnegative_balance'),)
    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('users.id'), primary_key=True)
    balance: Mapped[int] = mapped_column(Integer, default=0, server_default=text('0'))


class CreditCode(Base):
    __tablename__ = 'credit_codes'
    __table_args__ = (CheckConstraint('amount > 0 AND amount <= 1000000', name='positive_amount'),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('users.id'), index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('users.id'))
    digest: Mapped[str] = mapped_column(String(64), unique=True)
    suffix: Mapped[str] = mapped_column(String(4))
    amount: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CreditTransaction(Base):
    __tablename__ = 'credit_transactions'
    __table_args__ = (UniqueConstraint('kind', 'source_id', name='uq_credit_transactions_source'),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('users.id'), index=True)
    kind: Mapped[str] = mapped_column(String(24))
    source_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    description: Mapped[str] = mapped_column(String(240))
    amount: Mapped[int] = mapped_column(Integer)
    balance_after: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CreditReservation(Base):
    __tablename__ = 'credit_reservations'
    job_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('outline_jobs.id', ondelete='CASCADE'), primary_key=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('users.id'), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(String(240))
    state: Mapped[str] = mapped_column(String(16), default='reserved', server_default='reserved')
