"""Durable PPT outbox and expiring-lease worker, independent of video execution."""
import asyncio
from contextlib import suppress
from datetime import datetime,UTC,timedelta
from uuid import UUID,uuid4
from sqlalchemy import select,update,or_,text,func
from app.config import get_settings
from app.db import create_engine,create_sessionmaker
from app.jobs.celery_app import celery_app
from app.jobs.service import lock_generation_capacity,count_active_generation_jobs
from app.models import User
from app.credits.service import settle_ppt,release_ppt
from app.settings_store import get_generation_params
from .models import PptProject,PptJob
from .service import invalidate
from .versions import prune_archived_materials
from . import generation
from .knowledge import KnowledgeError,outline_digest

async def dispatch_pending(db,send):
    now=datetime.now(UTC)
    jobs=(await db.scalars(select(PptJob).where(or_(
        (PptJob.status=='pending') & or_(PptJob.dispatched_at.is_(None),PptJob.dispatched_at<now-timedelta(seconds=60)),
        (PptJob.status=='running') & or_(PptJob.lease_until.is_(None),PptJob.lease_until<now)
    )).order_by(PptJob.created_at).with_for_update(skip_locked=True).limit(50))).all()
    for job in jobs:
        try:send(str(job.id))
        except Exception:continue
        job.dispatched_at=now
    await db.commit()

async def heartbeat(maker,jid,token):
    while True:
        await asyncio.sleep(20)
        async with maker() as db:
            await db.execute(update(PptJob).where(PptJob.id==jid,PptJob.lease_token==token,PptJob.status=='running').values(lease_until=datetime.now(UTC)+timedelta(seconds=90)))
            await db.commit()

async def run_job(job_id,settings=None):
    settings=settings or get_settings();engine=create_engine(settings.database_url);maker=create_sessionmaker(engine);pulse=None
    jid=UUID(str(job_id));token=uuid4()
    try:
        async with maker() as db:
            await db.execute(text('SELECT pg_advisory_xact_lock(73016422)'))
            job=await db.scalar(select(PptJob).where(PptJob.id==jid).with_for_update())
            now=datetime.now(UTC)
            if not job:return
            if job.status in ('failed','cancelled'):
                if job.kind in ('render','revise'):await release_ppt(db,job);await db.commit()
                return
            if job.status not in ['pending','running'] or (job.lease_until and job.lease_until>now):return
            params=await get_generation_params(db);await lock_generation_capacity(db,job.owner_id)
            if await count_active_generation_jobs(db,job.owner_id,now,exclude_job_id=job.id,running_only=True)>=params.max_concurrent_jobs:return
            if job.attempts>params.max_retries:
                job.status='failed';job.stage='处理失败';job.error_message='任务重试次数已用完，请重新提交';job.lease_token=None;job.lease_until=None
                await db.execute(update(PptProject).where(PptProject.id==job.project_id,PptProject.revision==job.expected_revision).values(status='failed'))
                if job.kind in ('render','revise'):await release_ppt(db,job)
                await db.commit();return
            job.status='running';job.stage='准备课件';job.lease_token=token;job.lease_until=now+timedelta(seconds=90);job.attempts+=1
            await db.commit();pulse=asyncio.create_task(heartbeat(maker,jid,token))
            expected=job.expected_revision;pid=job.project_id;owner_id=job.owner_id;kind=job.kind
            async def progress(value,stage,checkpoint=None):
                async with maker() as progress_db:
                    values={'progress':value,'stage':stage}
                    if checkpoint is not None:values['checkpoint']=checkpoint
                    changed=await progress_db.execute(update(PptJob).where(PptJob.id==jid,PptJob.lease_token==token,PptJob.status=='running',PptJob.lease_until>datetime.now(UTC)).values(**values))
                    if not changed.rowcount:raise generation.GenerationError('任务已由其他进程接管')
                    await progress_db.commit()
            try:
                user=await db.get(User,owner_id);project=await db.get(PptProject,pid)
                if not user or user.status!='active':raise generation.GenerationError('账号状态已变化，无法继续执行')
                if not project or project.revision!=expected:raise generation.GenerationError('课件已更新，本次任务已停止')
                if kind=='render' and project.confirmed_revision!=expected:raise generation.GenerationError('请先确认当前大纲')
                result=await generation.build_result(db,project,job,settings,progress)
                if kind in ['render','revise']:
                    from .delivery import require_deliverable_pages
                    require_deliverable_pages(result['pages'])
                    if kind=='revise' and not any(p['id'] in job.payload['slide_ids'] for p in result['pages']):raise generation.GenerationError('所选页面制作未完成，上一版课件已保留。')
                    if [p['id'] for p in result['pages']]!=[s['id'] for s in result['outline']['slides']]:raise generation.GenerationError('课件页序与大纲不一致，原课件已保留')
                await db.rollback()
                # Lock in project -> job order, matching HTTP mutations.
                project=await db.scalar(select(PptProject).where(PptProject.id==pid).with_for_update().execution_options(populate_existing=True))
                current=await db.scalar(select(PptJob).where(PptJob.id==jid).with_for_update().execution_options(populate_existing=True))
                if not current or current.status!='running' or current.lease_token!=token or not current.lease_until or current.lease_until<=datetime.now(UTC):return
                user=await db.get(User,owner_id,populate_existing=True)
                if not project or project.revision!=expected or not user or user.status!='active':raise generation.GenerationError('课件或账号已变化，本次结果未应用')
                preserve=kind=='check' and project.outline and outline_digest(project.outline)==outline_digest(result['outline'])
                if not preserve:invalidate(project)
                project.revision+=1;project.outline=result['outline'];project.warnings=result['warnings']
                if not preserve:project.pages=result['pages']
                partial=bool(result.get('partial'))
                if preserve and project.pages:
                    from .delivery import require_deliverable_pages
                    try:require_deliverable_pages(project.pages)
                    except generation.QualityError:partial=True
                project.status=('partial_ready' if partial else 'ready') if project.pages else 'outline_ready'
                if project.pages:project.rendered_revision=project.revision;project.confirmed_revision=project.revision
                await prune_archived_materials(db,project)
                if kind in ('render','revise'):
                    if partial:await release_ppt(db,current)
                    else:await settle_ppt(db,current)
                current.status='succeeded';current.stage='已完成自动修复，部分页面待补齐' if result.get('partial') else '处理完成';current.progress=100;current.lease_until=None;current.lease_token=None;current.error_message=None;current.checkpoint={}
                await db.commit()
            except Exception as exc:
                await db.rollback()
                message=str(exc)[:300] if isinstance(exc,(generation.GenerationError,generation.QualityError,KnowledgeError)) else '课件任务处理失败，请重试或联系管理员'
                changed=await db.execute(update(PptJob).where(PptJob.id==jid,PptJob.lease_token==token,PptJob.status=='running').values(status='failed',stage='处理失败',error_message=message,lease_token=None,lease_until=None))
                if changed.rowcount:
                    if kind in ('render','revise'):
                        failed_job=await db.get(PptJob,jid,populate_existing=True)
                        await release_ppt(db,failed_job)
                    await db.execute(update(PptProject).where(PptProject.id==pid,PptProject.owner_id==owner_id,PptProject.revision==expected).values(status='failed'))
                await db.commit()
    finally:
        if pulse:
            pulse.cancel()
            with suppress(asyncio.CancelledError):await pulse
        await engine.dispose()

@celery_app.task(name='edu.ppt_run')
def execute(job_id):asyncio.run(run_job(job_id))

async def dispatch():
    settings=get_settings();engine=create_engine(settings.database_url)
    try:
        async with create_sessionmaker(engine)() as db:await dispatch_pending(db,lambda jid:execute.delay(jid))
    finally:await engine.dispose()

@celery_app.task(name='edu.ppt_dispatch')
def recover():asyncio.run(dispatch())
