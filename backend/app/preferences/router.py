from typing import Literal
from uuid import UUID
from fastapi import APIRouter,Depends,Response
from pydantic import BaseModel,model_validator
from sqlalchemy import select
from app.auth import require_active_user
from app.db import get_session
from app.models import User,Preference
from app.settings_store import get_generation_params
from app.errors import api_error
from .service import OPTIONS,suggestions

router=APIRouter(prefix='/api/preferences',tags=['preferences'])

class PreferenceBody(BaseModel):
    category: Literal['teaching','expression','visual','settings']
    value: str
    @model_validator(mode='after')
    def allowed(self):
        if self.value not in OPTIONS[self.category]: raise ValueError('请从教学方式、表达、画风或常用设置中选择，不保存讲稿和事实内容')
        return self

async def enabled(db):
    if not (await get_generation_params(db)).long_term_memory_enabled:
        raise api_error(409,'preferences_disabled','管理员已关闭长期偏好，已有数据会保留')

def view(p): return {'id':p.id,'category':p.category,'value':p.value}

async def owned(db,user_id,preference_id):
    p=await db.scalar(select(Preference).where(Preference.id==preference_id,Preference.owner_id==user_id,Preference.accepted.is_(True)))
    if not p: raise api_error(404,'preference_not_found','偏好不存在')
    return p

@router.get('')
async def list_preferences(db=Depends(get_session),user:User=Depends(require_active_user)):
    on=(await get_generation_params(db)).long_term_memory_enabled
    rows=(await db.scalars(select(Preference).where(Preference.owner_id==user.id,Preference.accepted.is_(True)).order_by(Preference.created_at))).all() if on else []
    return {'enabled':on,'options':OPTIONS,'items':[view(p) for p in rows],'suggestions':await suggestions(db,user.id) if on else []}

@router.post('',status_code=201)
async def create_preference(body:PreferenceBody,db=Depends(get_session),user:User=Depends(require_active_user)):
    await enabled(db)
    existing=await db.scalar(select(Preference).where(Preference.owner_id==user.id,Preference.category==body.category,Preference.value==body.value,Preference.accepted.is_(True)))
    if existing: return view(existing)
    p=Preference(owner_id=user.id,category=body.category,value=body.value,accepted=True)
    db.add(p);await db.commit();await db.refresh(p)
    return view(p)

@router.patch('/{preference_id}')
async def update_preference(preference_id:UUID,body:PreferenceBody,db=Depends(get_session),user:User=Depends(require_active_user)):
    p=await owned(db,user.id,preference_id);await enabled(db)
    p.category,p.value=body.category,body.value
    await db.commit();return view(p)

@router.delete('/{preference_id}',status_code=204)
async def delete_preference(preference_id:UUID,db=Depends(get_session),user:User=Depends(require_active_user)):
    p=await owned(db,user.id,preference_id)
    await db.delete(p);await db.commit();return Response(status_code=204)

@router.post('/suggestions/{suggestion_id}/accept',status_code=201)
async def accept_suggestion(suggestion_id:UUID,db=Depends(get_session),user:User=Depends(require_active_user)):
    await enabled(db)
    suggestion=next((s for s in await suggestions(db,user.id) if s['id']==str(suggestion_id)),None)
    if not suggestion: raise api_error(404,'suggestion_not_found','候选偏好不存在')
    return await create_preference(PreferenceBody(category=suggestion['category'],value=suggestion['value']),db,user)
