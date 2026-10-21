import asyncio
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit, quote
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, Request, UploadFile, File, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, func

from app.auth import require_active_user
from app.db import get_session
from app.errors import api_error
from app.models import Material, MaterialChunk, OutlineJob, User
from app.projects.service import get_owned_project
from app.jobs.service import create_job, require_idle
from app.jobs.dispatcher import enqueue_object_cleanup
from app.settings_store import get_form_fields
from .parsers import validate_document
from .storage import MaterialStorage

router = APIRouter(prefix='/api/projects/{project_id}/materials', tags=['materials'])

class MaterialView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    filename: str
    content_type: str
    size: int
    status: str
    error_message: str | None
    created_at: datetime
    job_id: UUID | None = None
    parse_warnings: list[dict[str,str]] = Field(default_factory=list)

def check_origin(request):
    origin = request.headers.get('origin', '')
    expected = urlsplit(str(request.base_url))
    try:
        actual = urlsplit(origin)
        actual.port
    except ValueError:
        raise api_error(403,'invalid_origin','上传来源无效，请从本站页面上传') from None
    def normalized(url):
        return url.scheme, url.hostname, url.port or (443 if url.scheme == 'https' else 80)
    if not origin or normalized(actual) != normalized(expected) or actual.username or actual.path not in ('', '/') or actual.query or actual.fragment:
        raise api_error(403, 'invalid_origin', '上传来源无效，请从本站页面上传')

async def owned_material(db, user_id, project_id, material_id):
    await get_owned_project(db, user_id, project_id)
    material = await db.scalar(select(Material).where(Material.id == material_id, Material.owner_id == user_id, Material.project_id == project_id))
    if not material: raise api_error(404, 'material_not_found', '素材不存在')
    return material

@router.post('', status_code=201)
async def upload(project_id: UUID, request: Request, file: UploadFile=File(...), defer_parse: bool = Query(False), db=Depends(get_session), user: User=Depends(require_active_user)) -> MaterialView:
    check_origin(request)
    project = await get_owned_project(db, user.id, project_id, lock=True)
    cfg=await get_form_fields(db)
    if not next(f.visible for f in cfg.fields if f.key=='materials'):
        raise api_error(409,'materials_disabled','管理员已关闭参考素材，请刷新页面后重试')
    await require_idle(db, project, allow_parse=True)
    settings = request.app.state.settings
    data = bytearray()
    while chunk := await file.read(1024*1024):
        data.extend(chunk)
        if len(data) > settings.upload_file_bytes:
            raise api_error(413, 'material_too_large', '单个文件不能超过 25 MiB')
    filename = Path((file.filename or 'material').replace('\\', '/')).name[:255]
    try:
        mime = await asyncio.to_thread(validate_document, filename, bytes(data))
    except ValueError as exc:
        raise api_error(422, 'invalid_document', str(exc)) from None
    count, total = (await db.execute(select(func.count(), func.coalesce(func.sum(Material.size),0)).where(Material.project_id==project.id, Material.owner_id==user.id))).one()
    if count >= settings.upload_project_files or total + len(data) > settings.upload_project_bytes:
        raise api_error(413, 'project_material_limit', '每项目最多 10 个文件，累计不能超过 100 MiB')
    identifier = uuid4()
    key = f'users/{user.id}/projects/{project.id}/materials/{identifier}/original'
    try:
        storage = MaterialStorage(settings)
        await asyncio.to_thread(storage.put, key, bytes(data), mime)
    except Exception:
        raise api_error(503, 'storage_unavailable', '素材存储暂不可用，请稍后重试') from None
    material = Material(id=identifier, owner_id=user.id, project_id=project.id, filename=filename, object_key=key, content_type=mime, size=len(data), status='stored' if defer_parse else 'pending')
    try:
        if project.outline:
            project.needs_regeneration=True;project.status='outline_ready';project.revision+=1
        db.add(material)
        job = None if defer_parse else await create_job(db, project, 'parse', str(identifier), {'material_id':str(identifier)})
        await db.commit()
        await db.refresh(material)
    except Exception:
        await db.rollback()
        try: await asyncio.to_thread(storage.delete, key)
        except Exception:
            await enqueue_object_cleanup(db, [key]); await db.commit()
        raise api_error(503, 'upload_failed', '素材保存失败，请重试') from None
    return MaterialView(**MaterialView.model_validate(material).model_dump(exclude={'job_id'}), job_id=job.id if job else None)

@router.get('')
async def list_materials(project_id: UUID, db=Depends(get_session), user: User=Depends(require_active_user)) -> list[MaterialView]:
    await get_owned_project(db, user.id, project_id)
    rows = (await db.scalars(select(Material).where(Material.project_id==project_id, Material.owner_id==user.id).order_by(Material.created_at))).all()
    return [MaterialView.model_validate(row) for row in rows]

@router.post('/prepare', status_code=202)
async def prepare_materials(project_id: UUID, db=Depends(get_session), user: User=Depends(require_active_user)):
    project = await get_owned_project(db, user.id, project_id, lock=True)
    await require_idle(db, project, allow_parse=True)
    rows = (await db.scalars(select(Material).where(
        Material.project_id == project_id,
        Material.owner_id == user.id,
        Material.status == 'stored',
    ).with_for_update(skip_locked=True))).all()
    job_ids = []
    for material in rows:
        material.status = 'pending'
        job = await create_job(db, project, 'parse', f'parse:{material.id}', {'material_id':str(material.id)})
        job_ids.append(job.id)
    await db.commit()
    return {'job_ids': job_ids}

@router.get('/{material_id}')
async def get_material(project_id: UUID, material_id: UUID, db=Depends(get_session), user: User=Depends(require_active_user)) -> MaterialView:
    return MaterialView.model_validate(await owned_material(db,user.id,project_id,material_id))

@router.get('/{material_id}/download')
async def download(project_id: UUID, material_id: UUID, request: Request, db=Depends(get_session), user: User=Depends(require_active_user)):
    material = await owned_material(db,user.id,project_id,material_id)
    try: data = await asyncio.to_thread(MaterialStorage(request.app.state.settings).get, material.object_key)
    except Exception: raise api_error(503, 'storage_unavailable', '素材暂时无法下载，请重试') from None
    return Response(data,media_type=material.content_type,headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(material.filename), 'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

@router.delete('/{material_id}', status_code=204)
async def delete_material(project_id: UUID, material_id: UUID, db=Depends(get_session), user: User=Depends(require_active_user)):
    project = await get_owned_project(db,user.id,project_id,lock=True)
    await require_idle(db,project)
    material = await owned_material(db,user.id,project_id,material_id)
    keys = list((await db.scalars(select(MaterialChunk.image_key).where(MaterialChunk.material_id==material.id, MaterialChunk.owner_id==user.id, MaterialChunk.image_key.is_not(None)))).all())
    await enqueue_object_cleanup(db, [material.object_key, *keys])
    if project.outline:
        project.needs_regeneration=True;project.status='outline_ready';project.revision+=1
    await db.delete(material)
    await db.commit()
    return Response(status_code=204)

@router.post('/{material_id}/retry')
async def retry_material(project_id: UUID, material_id: UUID, db=Depends(get_session), user: User=Depends(require_active_user)):
    project = await get_owned_project(db,user.id,project_id,lock=True)
    await require_idle(db,project)
    material = await owned_material(db,user.id,project_id,material_id)
    if material.status != 'failed': raise api_error(409,'material_not_failed','只能重试解析失败的素材')
    material.status, material.error_message = 'pending', None
    job = await create_job(db,project,'parse',str(uuid4()),{'material_id':str(material.id)})
    await db.commit()
    return {'job_id':job.id}
