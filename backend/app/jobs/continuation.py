"""Intentional durable yield, distinct from job success or failure."""
from datetime import UTC,datetime
from sqlalchemy import update,func
from app.models import OutlineJob


class ContinueJob(Exception):
    def __init__(self, stage):
        self.stage=stage
        super().__init__(stage)


async def requeue_continuation(db,job_id,token,stage):
    # Claim increment is neutral for an intentional yield. A crashed lease still
    # consumes one attempt, so ordinary recovery retains its existing bound.
    changed=await db.execute(update(OutlineJob).where(
        OutlineJob.id==job_id,OutlineJob.kind=='video',OutlineJob.status=='running',
        OutlineJob.lease_token==token,OutlineJob.lease_until>datetime.now(UTC),
    ).values(status='pending',stage=stage[:64],lease_token=None,lease_until=None,
        dispatched_at=None,error_message=None,attempts=func.greatest(0,OutlineJob.attempts-1),
        updated_at=func.clock_timestamp()))
    await db.commit()
    return bool(changed.rowcount)
