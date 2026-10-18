from uuid import UUID
from fastapi import APIRouter,Depends,Request
from sqlalchemy import select
from app.auth import require_active_user
from app.db import get_session
from app.models import User,Evidence
from app.security import get_secret_box
from app.errors import api_error
from app.projects.service import get_owned_project
from app.jobs.service import JobView
from .schemas import JobRequest,OutlineSave,RevisionBody,OutlineView
from . import service

router=APIRouter(prefix='/api/projects/{project_id}',tags=['outline'])

@router.get('/outline')
async def get_outline(project_id:UUID,db=Depends(get_session),user:User=Depends(require_active_user))->OutlineView:
    return await service.view(db,await get_owned_project(db,user.id,project_id))

@router.put('/outline')
async def save_outline(project_id:UUID,body:OutlineSave,db=Depends(get_session),user:User=Depends(require_active_user))->OutlineView:
    return await service.save_outline(db,user.id,project_id,body)

@router.post('/outline/generate',status_code=202)
async def generate(project_id:UUID,body:JobRequest,db=Depends(get_session),user:User=Depends(require_active_user),box=Depends(get_secret_box))->JobView:
    return JobView.model_validate(await service.start_outline(db,user,project_id,body,'generate',box))

@router.post('/outline/rewrite',status_code=202)
async def rewrite(project_id:UUID,body:JobRequest,db=Depends(get_session),user:User=Depends(require_active_user),box=Depends(get_secret_box))->JobView:
    return JobView.model_validate(await service.start_outline(db,user,project_id,body,'rewrite',box))

@router.post('/outline/review',status_code=202)
async def review(project_id:UUID,body:JobRequest,db=Depends(get_session),user:User=Depends(require_active_user),box=Depends(get_secret_box))->JobView:
    return JobView.model_validate(await service.start_outline(db,user,project_id,body,'review',box))

@router.post('/outline/confirm')
async def confirm(project_id:UUID,body:RevisionBody,request:Request,db=Depends(get_session),user:User=Depends(require_active_user))->OutlineView:
    return await service.confirm_outline(db,user.id,project_id,body.revision,request.app.state.settings)

@router.get('/evidence/{evidence_id}')
async def get_evidence(project_id:UUID,evidence_id:UUID,db=Depends(get_session),user:User=Depends(require_active_user)):
    await get_owned_project(db,user.id,project_id)
    e=await db.scalar(select(Evidence).where(Evidence.id==evidence_id,Evidence.owner_id==user.id,Evidence.project_id==project_id))
    if not e: raise api_error(404,'evidence_not_found','依据不存在')
    return {k:getattr(e,k) for k in ('id','claim','source_type','source_ref','location','excerpt','source_grade','verification_status')}
