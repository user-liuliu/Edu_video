from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models import Base

class PptProject(Base):
    __tablename__='ppt_projects'
    id: Mapped[UUID]=mapped_column(Uuid,primary_key=True,default=uuid4)
    owner_id: Mapped[UUID]=mapped_column(ForeignKey('users.id'),index=True)
    title: Mapped[str]=mapped_column(String(200))
    prompt: Mapped[str]=mapped_column(Text)
    style: Mapped[str]=mapped_column(String(64),default='auto')
    web_search: Mapped[bool]=mapped_column(default=False)
    template_id: Mapped[str]=mapped_column(String(64),default='clear-blue-teaching')
    template_version: Mapped[str]=mapped_column(String(16),default='1.0.0')
    status: Mapped[str]=mapped_column(String(32),default='draft')
    revision: Mapped[int]=mapped_column(Integer,default=1)
    confirmed_revision: Mapped[int | None]=mapped_column(Integer)
    rendered_revision: Mapped[int | None]=mapped_column(Integer)
    exported_revision: Mapped[int | None]=mapped_column(Integer)
    outline: Mapped[dict | None]=mapped_column(JSONB)
    pages: Mapped[list]=mapped_column(JSONB,default=list)
    history: Mapped[list]=mapped_column(JSONB,default=list)
    warnings: Mapped[list]=mapped_column(JSONB,default=list)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now())

class PptMaterial(Base):
    __tablename__='ppt_materials'
    id: Mapped[UUID]=mapped_column(Uuid,primary_key=True,default=uuid4)
    project_id: Mapped[UUID]=mapped_column(ForeignKey('ppt_projects.id',ondelete='CASCADE'),index=True)
    owner_id: Mapped[UUID]=mapped_column(ForeignKey('users.id'))
    filename: Mapped[str]=mapped_column(String(255))
    object_key: Mapped[str]=mapped_column(String(512))
    content_type: Mapped[str]=mapped_column(String(128))
    size: Mapped[int]=mapped_column(Integer)
    status: Mapped[str]=mapped_column(String(32),default='stored')
    error_message: Mapped[str | None]=mapped_column(Text)
    chunks: Mapped[list]=mapped_column(JSONB,default=list)
    parse_warnings: Mapped[list]=mapped_column(JSONB,default=list)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())

class PptJob(Base):
    __tablename__='ppt_jobs'
    __table_args__=(UniqueConstraint('owner_id','project_id','kind','idempotency_key',name='uq_ppt_jobs_request'),)
    id: Mapped[UUID]=mapped_column(Uuid,primary_key=True,default=uuid4)
    owner_id: Mapped[UUID]=mapped_column(ForeignKey('users.id'),index=True)
    project_id: Mapped[UUID]=mapped_column(ForeignKey('ppt_projects.id',ondelete='CASCADE'),index=True)
    kind: Mapped[str]=mapped_column(String(32))
    idempotency_key: Mapped[str]=mapped_column(String(128))
    expected_revision: Mapped[int]=mapped_column(Integer)
    payload: Mapped[dict]=mapped_column(JSONB,default=dict)
    checkpoint: Mapped[dict]=mapped_column(JSONB,default=dict)
    status: Mapped[str]=mapped_column(String(32),default='pending',index=True)
    stage: Mapped[str]=mapped_column(String(64),default='等待处理')
    progress: Mapped[int]=mapped_column(Integer,default=0)
    attempts: Mapped[int]=mapped_column(Integer,default=0)
    error_message: Mapped[str | None]=mapped_column(Text)
    lease_token: Mapped[UUID | None]=mapped_column(Uuid)
    lease_until: Mapped[datetime | None]=mapped_column(DateTime(timezone=True))
    dispatched_at: Mapped[datetime | None]=mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now())


class PptCreditReservation(Base):
    __tablename__='ppt_credit_reservations'
    job_id: Mapped[UUID]=mapped_column(ForeignKey('ppt_jobs.id',ondelete='CASCADE'),primary_key=True)
    owner_id: Mapped[UUID]=mapped_column(ForeignKey('users.id'),index=True)
    amount: Mapped[int]=mapped_column(Integer)
    description: Mapped[str]=mapped_column(String(240))
    state: Mapped[str]=mapped_column(String(16),default='reserved',server_default='reserved')
