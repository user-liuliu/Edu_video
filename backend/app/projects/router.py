from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_active_user
from app.db import get_session
from app.models import User, VideoProject, VideoVersion, VideoSegment
from app.errors import api_error
from app.model_configs import resolve, list_voices
from app.purposes import Purpose
from app.security import SecretBox, get_secret_box
from app.settings_store import get_form_fields
from app.settings_store.form_values import form_version, resolve_form_values
from .schemas import ProjectCreate, ProjectUpdate, ProjectView, ProjectList
from .service import check_revision, get_owned_project
from app.jobs.service import require_idle
from app.models import Material, MaterialChunk, ObjectCleanup

router = APIRouter(prefix='/api/projects', tags=['projects'])
DB = Annotated[AsyncSession, Depends(get_session)]
CurrentTeacher = Annotated[User, Depends(require_active_user)]
Box = Annotated[SecretBox, Depends(get_secret_box)]


async def submission_policy(db, box):
    cfg = await get_form_fields(db)
    from app.videos.system_speech import voice_options
    voices = await voice_options(db,box)
    search_ready = await resolve(db, box, Purpose.web_search) is not None
    return cfg, voices, search_ready, form_version(cfg, voices, search_ready)


async def resolve_submission(db, box, body):
    cfg, voices, search_ready, version = await submission_policy(db, box)
    if body.form_version and body.form_version != version:
        raise api_error(409, 'form_config_changed', '页面配置已更新，请刷新后重新确认参数')
    return resolve_form_values(cfg, body.form_values, voices=voices, search_ready=search_ready)


@router.post('', status_code=201)
async def create_project(body: ProjectCreate, db: DB, user: CurrentTeacher, box: Box) -> ProjectView:
    values = await resolve_submission(db, box, body)
    project = VideoProject(owner_id=user.id, title=body.title.strip() or body.prompt[:60], prompt=body.prompt, form_values=values)
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return ProjectView.model_validate(project)


@router.get('')
async def list_projects(db: DB, user: CurrentTeacher, scope: Literal['all', 'drafts', 'completed'] = 'all', page: Annotated[int, Query(ge=1)] = 1, page_size: Annotated[int, Query(ge=1, le=100)] = 20) -> ProjectList:
    conditions = [VideoProject.owner_id == user.id]
    exported_video = select(VideoVersion.id).where(
        VideoVersion.project_id == VideoProject.id,
        VideoVersion.owner_id == user.id,
        VideoVersion.status == 'succeeded',
        VideoVersion.media_key.is_not(None),
        VideoVersion.media_key != '',
    ).exists()
    if scope == 'drafts':
        conditions.append(~exported_video)
    elif scope == 'completed':
        conditions.append(exported_video)
    total = await db.scalar(select(func.count()).select_from(VideoProject).where(*conditions))
    items = (await db.execute(select(VideoProject).where(*conditions).order_by(VideoProject.updated_at.desc(), VideoProject.id).offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return ProjectList(items=[ProjectView.model_validate(p) for p in items], total=total or 0)


@router.get('/{project_id}')
async def read_project(project_id: UUID, db: DB, user: CurrentTeacher) -> ProjectView:
    return ProjectView.model_validate(await get_owned_project(db, user.id, project_id))


@router.patch('/{project_id}')
async def update_project(project_id: UUID, body: ProjectUpdate, db: DB, user: CurrentTeacher, box: Box) -> ProjectView:
    project = await get_owned_project(db, user.id, project_id, lock=True)
    check_revision(project, body.revision)
    await require_idle(db, project)
    values=await resolve_submission(db,box,body)
    related=('subject','grade','textbook_edition','duration_seconds','web_search')
    if project.outline and (body.prompt!=project.prompt or any(values.get(k)!=project.form_values.get(k) for k in related)):
        project.needs_regeneration=True
        project.status='outline_ready'
    project.prompt, project.title, project.form_values = body.prompt, body.title.strip() or body.prompt[:60], values
    project.revision += 1
    await db.commit()
    await db.refresh(project)
    return ProjectView.model_validate(project)


@router.delete('/{project_id}', status_code=204)
async def delete_project(project_id: UUID, db: DB, user: CurrentTeacher, revision: Annotated[int, Query(ge=1)]) -> Response:
    project = await get_owned_project(db, user.id, project_id, lock=True)
    check_revision(project, revision)
    await require_idle(db, project)
    keys = list((await db.scalars(select(Material.object_key).where(Material.project_id==project_id, Material.owner_id==user.id))).all())
    keys += list((await db.scalars(select(MaterialChunk.image_key).where(MaterialChunk.project_id==project_id, MaterialChunk.owner_id==user.id, MaterialChunk.image_key.is_not(None)))).all())
    versions=(await db.scalars(select(VideoVersion).where(VideoVersion.project_id==project_id,VideoVersion.owner_id==user.id))).all()
    for version in versions:
        keys.extend(version.asset_keys)
        if version.media_key: keys.append(version.media_key)
        segments=(await db.scalars(select(VideoSegment).where(VideoSegment.version_id==version.id))).all()
        for segment in segments: keys.extend(v for k,v in segment.assets.items() if k!='hashes' and isinstance(v,str))
    for key in set(keys):
        db.add(ObjectCleanup(object_key=key))
    await db.delete(project)
    await db.commit()
    return Response(status_code=204)
