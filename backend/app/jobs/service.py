from datetime import datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func,select,text,update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_active_user
from app.db import get_session
from app.errors import api_error
from app.models import OutlineJob, User, VideoVersion


class JobView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    kind: str
    status: str
    stage: str
    progress: int
    workflow: str | None = None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


async def lock_generation_capacity(db, owner_id):
    """Serialize capacity claims per teacher, not across the whole system."""
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {'key': f'edu-video:generation-capacity:{owner_id}'},
    )


async def count_active_generation_jobs(db, owner_id, now=None, exclude_job_id: UUID | None = None, *, running_only=False):
    conditions = [
        OutlineJob.owner_id == owner_id,
        OutlineJob.kind != 'parse',
        OutlineJob.status.in_(['pending', 'running']),
    ]
    if running_only:
        conditions.append(OutlineJob.status == 'running')
    if exclude_job_id is not None:
        conditions.append(OutlineJob.id != exclude_job_id)
    if now is not None:
        conditions.append((OutlineJob.status != 'running') | (OutlineJob.lease_until.is_(None)) | (OutlineJob.lease_until > now))
    return int(await db.scalar(select(func.count()).select_from(OutlineJob).where(*conditions)) or 0)


async def require_generation_capacity(db, owner_id, max_jobs):
    await lock_generation_capacity(db, owner_id)
    active = await count_active_generation_jobs(db, owner_id)
    if active >= max_jobs:
        raise api_error(409, 'generation_capacity_exceeded', f'超出最大任务数：已存在{active}个生成任务')
    return active


async def create_job(db, project, kind, idempotency_key, payload):
    # The transaction itself is the outbox. Broker dispatch happens separately.
    await db.execute(insert(OutlineJob).values(
        id=uuid4(), owner_id=project.owner_id, project_id=project.id, kind=kind,
        idempotency_key=idempotency_key, expected_revision=project.revision, payload=payload,
    ).on_conflict_do_nothing(constraint='uq_outline_jobs_request'))
    return (await db.scalars(select(OutlineJob).where(
        OutlineJob.owner_id == project.owner_id, OutlineJob.project_id == project.id,
        OutlineJob.kind == kind, OutlineJob.idempotency_key == idempotency_key,
    ))).one()


async def update_job_progress(db, job_id: UUID, lease_token: UUID, progress: int, stage: str):
    """Persist an in-flight job's progress without allowing stale workers to overwrite it."""
    progress = max(0, min(99, int(progress)))
    # A progress event must never flush or commit unpublished outline/material output.
    async with AsyncSession(bind=db.bind, expire_on_commit=False) as progress_db:
        changed = await progress_db.execute(
            update(OutlineJob).where(
                OutlineJob.id == job_id,
                OutlineJob.lease_token == lease_token,
                OutlineJob.status == 'running',
            ).values(progress=func.greatest(OutlineJob.progress, progress), stage=stage)
        )
        if not changed.rowcount:
            raise ValueError('任务已由其他进程接管或终止')
        await progress_db.commit()


async def require_idle(db, project, *, allow_parse=False):
    stmt=select(OutlineJob.id).where(
        OutlineJob.project_id == project.id, OutlineJob.owner_id == project.owner_id,
        OutlineJob.status.in_(['pending', 'running']),
    )
    if allow_parse: stmt=stmt.where(OutlineJob.kind!='parse')
    busy = await db.scalar(stmt.limit(1))
    if busy:
        raise api_error(409, 'project_busy', '项目正在处理中，请等待任务完成后再修改')


router = APIRouter(prefix='/api/jobs', tags=['jobs'])

@router.get('/{job_id}')
async def get_job(job_id: UUID, db=Depends(get_session), user: User=Depends(require_active_user)) -> JobView:
    job = await db.scalar(select(OutlineJob).where(OutlineJob.id == job_id, OutlineJob.owner_id == user.id))
    if not job:
        raise api_error(404, 'job_not_found', '任务不存在')
    version=await db.scalar(select(VideoVersion).where(VideoVersion.job_id==job.id)) if job.kind=='video' else None
    return JobView.model_validate(job).model_copy(update={'workflow':version.snapshot.get('workflow') if version else None})
