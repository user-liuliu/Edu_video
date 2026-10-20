from uuid import UUID
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from app.auth import require_active_user
from app.db import get_session
from app.security import get_secret_box
from app.models import VideoVersion
from app.projects.service import get_owned_project
from .schemas import VideoRequest, VisualRevisionRequest, VersionView
from .service import start_video, owned_version, version_view

router=APIRouter(prefix='/api/projects/{project_id}/videos',tags=['videos'])
from .media import video_media
router.add_api_route('/{version_id}/media/{asset}',video_media,methods=['GET','HEAD'])

@router.post('',status_code=202)
async def generate(project_id:UUID,body:VideoRequest,db=Depends(get_session),user=Depends(require_active_user),box=Depends(get_secret_box))->VersionView:
    return await version_view(db,await start_video(db,user,project_id,body,box))

@router.get('')
async def versions(project_id:UUID,db=Depends(get_session),user=Depends(require_active_user))->list[VersionView]:
    await get_owned_project(db,user.id,project_id)
    rows=(await db.scalars(select(VideoVersion).where(VideoVersion.project_id==project_id,VideoVersion.owner_id==user.id).order_by(VideoVersion.number.desc()))).all()
    return [await version_view(db,v) for v in rows]

@router.get('/{version_id}')
async def detail(project_id:UUID,version_id:UUID,db=Depends(get_session),user=Depends(require_active_user))->VersionView:
    return await version_view(db,await owned_version(db,user.id,project_id,version_id))

@router.post('/{version_id}/revisions',status_code=202)
async def revise(project_id:UUID,version_id:UUID,body:VisualRevisionRequest,db=Depends(get_session),user=Depends(require_active_user),box=Depends(get_secret_box))->VersionView:
    return await version_view(db,await start_video(db,user,project_id,body,box,source_version_id=version_id))


from .schemas import ExportRequest
from .service import start_export
from app.jobs.service import JobView
from .media import film_asset
router.add_api_route('/{version_id}/film/{asset}',film_asset,methods=['GET','HEAD'])

@router.post('/{version_id}/export',status_code=202)
async def export(project_id:UUID,version_id:UUID,body:ExportRequest,request:Request,db=Depends(get_session),user=Depends(require_active_user))->JobView:
    return JobView.model_validate(await start_export(db,user,project_id,version_id,body,request.app.state.settings))
