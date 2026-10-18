import asyncio
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select, update, delete, func, text

from app.config import get_settings
from app.db import create_engine, create_sessionmaker
from app.models import OutlineJob, Material, MaterialChunk, User, VideoProject
from app.materials.storage import MaterialStorage
from .celery_app import celery_app
from .dispatcher import dispatch_pending, cleanup_objects
from .service import count_active_generation_jobs, lock_generation_capacity


@celery_app.task(name='edu.dispatch')
def dispatch():
    async def run():
        settings = get_settings()
        engine = create_engine(settings.database_url)
        try:
            async with create_sessionmaker(engine)() as db:
                await dispatch_pending(db, lambda job_id: execute.delay(job_id))
                if settings.minio_endpoint:
                    await cleanup_objects(db, MaterialStorage(settings))
        finally: await engine.dispose()
    asyncio.run(run())


async def heartbeat(maker, job_id, token):
    while True:
        await asyncio.sleep(20)
        async with maker() as db:
            await db.execute(update(OutlineJob).where(OutlineJob.id==job_id, OutlineJob.lease_token==token, OutlineJob.status=='running').values(lease_until=datetime.now(UTC)+timedelta(seconds=90)))
            await db.commit()


async def parse_job(db, job, settings, storage):
    from app.materials.parsers import parse_document
    from app.outline.model_client import recognize_image
    from app.model_configs import resolve
    from app.security import SecretBox
    from app.purposes import Purpose
    token=job.lease_token
    vision=await resolve(db,SecretBox(settings.master_key),Purpose.vision_llm)
    current = await db.scalar(select(OutlineJob).where(OutlineJob.id==job.id).with_for_update().execution_options(populate_existing=True))
    if current is None or current.lease_token != token or current.status != 'running':
        raise ValueError('任务已由其他进程接管或终止')
    material = await db.scalar(select(Material).where(Material.id==UUID(job.payload['material_id']), Material.owner_id==job.owner_id, Material.project_id==job.project_id))
    if not material: raise ValueError('素材已不存在')
    filename, key, material_id = material.filename, material.object_key, material.id
    material.status = 'parsing'
    await db.commit()
    data = await asyncio.to_thread(storage.get,key)
    warnings = []
    chunks = await asyncio.to_thread(parse_document,filename,data,settings.temp_dir,warnings=warnings)
    records = []
    for i, chunk in enumerate(chunks):
        if chunk.get('image'):
            if not vision: raise ValueError('看图识别模型尚不可用，请联系管理员')
            chunk['text'] = await recognize_image(db,settings,chunk['image'],vision)
        if not chunk['text'].strip(): continue
        records.append(MaterialChunk(owner_id=job.owner_id,project_id=job.project_id,material_id=material_id,position=i,location=chunk['location'],text=chunk['text']))
    if not records: raise ValueError('未识别到可用文字，请检查素材')
    # Recheck the lease before making the result visible.
    current = await db.scalar(select(OutlineJob).where(OutlineJob.id==job.id).with_for_update().execution_options(populate_existing=True))
    if current.lease_token != token or current.status!='running': raise ValueError('任务已由其他进程接管或终止')
    await db.execute(delete(MaterialChunk).where(MaterialChunk.material_id==material_id,MaterialChunk.owner_id==job.owner_id))
    db.add_all(records)
    material.status,material.error_message = 'ready',None
    material.parse_warnings = warnings
    # Caller commits material output and succeeded state atomically.


async def run_job(job_id, settings=None):
    settings = settings or get_settings()
    engine = create_engine(settings.database_url)
    maker = create_sessionmaker(engine)
    pulse = None
    try:
        async with maker() as db:
            # Serialize capacity claims across processes; release before external work.
            await db.execute(text('SELECT pg_advisory_xact_lock(73016422)'))
            job = await db.scalar(select(OutlineJob).where(OutlineJob.id==UUID(str(job_id))).with_for_update())
            now = datetime.now(UTC)
            if not job or job.status in ('succeeded','failed') or (job.lease_until and job.lease_until>now): return
            if job.kind == 'generate':
                from app.materials.pipeline import dependency_state
                ready, dependency_error, completed, total = await dependency_state(db, job)
                if dependency_error:
                    job.status, job.stage, job.error_message = 'failed', '素材解析失败', dependency_error[:500]
                    job.lease_token, job.lease_until = None, None
                    await db.execute(update(VideoProject).where(
                        VideoProject.id==job.project_id, VideoProject.owner_id==job.owner_id,
                        VideoProject.revision==job.expected_revision,
                    ).values(status='failed'))
                    await db.commit()
                    return
                if not ready:
                    job.status, job.stage = 'pending', f'解析参考素材（{completed}/{total}）'
                    job.progress = max(job.progress, 5 + int(15 * completed / total))
                    job.lease_token, job.lease_until, job.dispatched_at = None, None, None
                    await db.commit()
                    return
            from app.settings_store import get_generation_params
            params = await get_generation_params(db)
            if job.kind != 'parse':
                await lock_generation_capacity(db,job.owner_id)
                running = await count_active_generation_jobs(db,job.owner_id,now,exclude_job_id=job.id,running_only=True)
                if running >= params.max_concurrent_jobs: return
            if job.attempts > params.max_retries:
                job.status,job.error_message='failed','任务重试次数已用完，请重新提交'
                job.stage,job.lease_until='处理失败',None
                job.lease_token=None
                if job.kind=='parse':
                    await db.execute(update(Material).where(Material.id==UUID(job.payload['material_id']),Material.owner_id==job.owner_id).values(status='failed',error_message=job.error_message))
                else:
                    await db.execute(update(VideoProject).where(VideoProject.id==job.project_id,VideoProject.owner_id==job.owner_id,VideoProject.revision==job.expected_revision).values(status='failed'))
                await db.commit(); return
            token=uuid4()
            job.lease_token,job.lease_until=token,now+timedelta(seconds=90)
            job.status,job.stage='running','解析素材' if job.kind=='parse' else '准备大纲'
            job.progress=max(job.progress,5)
            job.attempts += 1
            await db.commit()
            owner_id,project_id,kind,payload,expected_revision=job.owner_id,job.project_id,job.kind,dict(job.payload),job.expected_revision
            pulse=asyncio.create_task(heartbeat(maker,job.id,token))
            try:
                owner = await db.get(User,job.owner_id)
                if not owner or owner.status != 'active': raise ValueError('账号状态已变化，无法继续执行')
                if job.kind=='parse':
                    await parse_job(db,job,settings,MaterialStorage(settings))
                else:
                    from app.outline.service import execute_outline_job
                    await execute_outline_job(db,job,settings)
                changed=await db.execute(update(OutlineJob).where(OutlineJob.id==job.id,OutlineJob.lease_token==token,OutlineJob.status=='running').values(status='succeeded',stage='处理完成',progress=100,lease_until=None,error_message=None,updated_at=func.clock_timestamp()))
                if not changed.rowcount: raise ValueError('任务已由其他进程接管或终止')
                await db.commit()
            except Exception as exc:
                await db.rollback()
                # Only deliberate Chinese validation errors are safe for users; never expose provider bodies.
                message=str(exc) if isinstance(exc,ValueError) and any('一'<=c<='鿿' for c in str(exc)) else '任务处理失败，请重试或联系管理员检查接口配置'
                changed=await db.execute(update(OutlineJob).where(OutlineJob.id==UUID(str(job_id)),OutlineJob.lease_token==token,OutlineJob.status=='running').values(status='failed',stage='处理失败',error_message=message[:500],lease_until=None,lease_token=None))
                if changed.rowcount:
                    if kind=='parse':
                        await db.execute(update(Material).where(Material.id==UUID(payload['material_id']),Material.owner_id==owner_id).values(status='failed',error_message=message[:500]))
                    else:
                        await db.execute(update(VideoProject).where(VideoProject.id==project_id,VideoProject.owner_id==owner_id,VideoProject.revision==expected_revision).values(status='failed'))
                await db.commit()
    finally:
        if pulse:
            pulse.cancel()
            with suppress(asyncio.CancelledError): await pulse
        await engine.dispose()


@celery_app.task(name='edu.execute')
def execute(job_id):
    asyncio.run(run_job(job_id))
