from datetime import UTC, datetime, timedelta
from sqlalchemy import select, or_, and_
from app.models import OutlineJob, ObjectCleanup


async def dispatch_pending(db, send):
    now = datetime.now(UTC)
    jobs = (await db.scalars(select(OutlineJob).where(or_(
        and_(OutlineJob.status=='pending', or_(OutlineJob.dispatched_at.is_(None), OutlineJob.dispatched_at < now-timedelta(seconds=60))),
        and_(OutlineJob.status=='running', OutlineJob.lease_until < now),
    )).with_for_update(skip_locked=True).limit(50))).all()
    for job in jobs:
        # A lost acknowledgement can enqueue twice; worker lease prevents duplicate writes.
        try:
            send(str(job.id))
        except Exception:
            continue
        job.dispatched_at = now
    await db.commit()
    return len(jobs)


async def cleanup_objects(db, storage):
    import asyncio
    rows = (await db.scalars(select(ObjectCleanup).with_for_update(skip_locked=True).limit(50))).all()
    for row in rows:
        try: await asyncio.to_thread(storage.delete, row.object_key)
        except Exception: continue
        await db.delete(row)
    await db.commit()
