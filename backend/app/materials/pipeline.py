from uuid import uuid4

from sqlalchemy import select

from app.jobs.service import create_job
from app.models import Material, OutlineJob


async def prepare_dependencies(db, project):
    """Create/reuse parse jobs inside the generation submission transaction."""
    materials = (await db.scalars(select(Material).where(
        Material.project_id == project.id, Material.owner_id == project.owner_id,
    ).order_by(Material.created_at).with_for_update())).all()
    dependencies = []
    for material in materials:
        if material.status == 'ready':
            continue
        active = await db.scalar(select(OutlineJob).where(
            OutlineJob.owner_id == project.owner_id, OutlineJob.project_id == project.id,
            OutlineJob.kind == 'parse', OutlineJob.status.in_(['pending', 'running']),
            OutlineJob.payload['material_id'].astext == str(material.id),
        ).order_by(OutlineJob.created_at.desc()).limit(1))
        if active is None:
            active = await create_job(db, project, 'parse', str(uuid4()), {'material_id': str(material.id)})
            material.status, material.error_message = 'pending', None
        dependencies.append(str(active.id))
    return [str(material.id) for material in materials], dependencies


async def dependency_state(db, job):
    """Return readiness without blocking a worker or consuming a retry attempt."""
    ids = job.payload.get('material_job_ids', [])
    if not ids:
        return True, None, 0, 0
    from uuid import UUID
    rows = (await db.scalars(select(OutlineJob).where(
        OutlineJob.id.in_([UUID(value) for value in ids]),
        OutlineJob.owner_id == job.owner_id, OutlineJob.project_id == job.project_id,
        OutlineJob.kind == 'parse',
    ))).all()
    if len(rows) != len(ids):
        return False, '素材解析任务已不存在，请重新生成大纲', 0, len(ids)
    failed = next((row for row in rows if row.status == 'failed'), None)
    if failed:
        material = await db.scalar(select(Material).where(
            Material.id == UUID(failed.payload['material_id']),
            Material.owner_id == job.owner_id, Material.project_id == job.project_id,
        ))
        reason = failed.error_message or (material.error_message if material else None)
        return False, '素材解析失败：' + (reason or '请检查素材后重新生成'), 0, len(ids)
    ready = sum(row.status == 'succeeded' for row in rows)
    if ready == len(ids):
        material_ids = [UUID(row.payload['material_id']) for row in rows]
        materials = (await db.scalars(select(Material).where(
            Material.id.in_(material_ids), Material.owner_id == job.owner_id,
            Material.project_id == job.project_id,
        ))).all()
        if len(materials) != len(material_ids) or any(row.status != 'ready' for row in materials):
            return False, '素材解析结果不可用，请检查素材后重新生成', ready, len(ids)
    return ready == len(ids), None, ready, len(ids)
