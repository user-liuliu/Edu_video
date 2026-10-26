import asyncio
from hashlib import sha256
from pathlib import Path
from urllib.parse import quote
from uuid import UUID,uuid4
from fastapi import APIRouter,Depends,Request,UploadFile,File,Query,Response
from sqlalchemy import select,func,delete,text
from app.auth import require_active_user
from app.db import get_session
from app.errors import api_error
from app.materials.parsers import validate_document
from app.materials.storage import MaterialStorage
from app.materials.router import check_origin
from app.jobs.dispatcher import enqueue_object_cleanup
from app.jobs.service import require_generation_capacity
from app.model_configs import resolve
from app.purposes import Purpose
from app.settings_store import get_generation_params
from .search_policy import search_policy,effective_search
from .models import PptProject,PptMaterial,PptJob
from .schemas import ProjectInput,OutlineInput,ConfirmInput,JobInput,TextEditInput
from .knowledge import require_reviewed_outline,KnowledgeError,outline_digest
from .service import owned,idle,invalidate,view,job_view
from .rendering import catalog,export_pptx,preview_svg
from . import master_runtime as master
from .delivery import require_deliverable_pages
from .quality import QualityError
from .master_assets import load_assets,page_images
from .versions import snapshot,referenced_images,prune_archived_materials
from .service import project_view

from . import styles

router=APIRouter(prefix='/api/presentations',tags=['presentations'])

@router.get('/config')
async def config(request:Request,db=Depends(get_session),user=Depends(require_active_user)):
    return {'system_available':bool(await resolve(db,request.app.state.secret_box,Purpose.outline_llm)), 'review_available':bool(await resolve(db,request.app.state.secret_box,Purpose.vision_llm)), **await search_policy(db,request.app.state.secret_box), 'templates':styles.catalog(), 'layouts':{k:v['name'] for k,v in catalog().items()}}

@router.get('')
async def projects(scope:str='all',page:int=Query(1,ge=1),db=Depends(get_session),user=Depends(require_active_user)):
    condition=[PptProject.owner_id==user.id]
    # A full successful export is the teacher's explicit acceptance.
    # Keep accepted projects in works even when a later revision is in progress.
    if scope=='completed':condition.append(PptProject.exported_revision.is_not(None))
    if scope=='drafts':condition.append(PptProject.exported_revision.is_(None))
    items=(await db.scalars(select(PptProject).where(*condition).order_by(PptProject.updated_at.desc()).offset((page-1)*20).limit(20))).all()
    return {'items':[await view(db,p) for p in items],'total':await db.scalar(select(func.count()).select_from(PptProject).where(*condition))}

@router.post('')
async def create(body:ProjectInput,request:Request,db=Depends(get_session),user=Depends(require_active_user)):
    data=body.model_dump(exclude={'revision'});data['web_search']=effective_search(await search_policy(db,request.app.state.secret_box),body.web_search if 'web_search' in body.model_fields_set else None)
    theme=styles.identity(body.style);data.update(template_id=theme['id'],template_version=theme['version'])
    p=PptProject(owner_id=user.id,**data);db.add(p);await db.commit();await db.refresh(p);return await view(db,p)

@router.get('/jobs/{job_id}')
async def job(job_id:UUID,db=Depends(get_session),user=Depends(require_active_user)):
    job=await db.scalar(select(PptJob).where(PptJob.id==job_id,PptJob.owner_id==user.id))
    if not job:raise api_error(404,'job_not_found','任务不存在')
    return job_view(job)

@router.get('/{project_id}')
async def get(project_id:UUID,db=Depends(get_session),user=Depends(require_active_user)):
    return await view(db,await owned(db,user.id,project_id))

@router.get('/{project_id}/versions/{version}')
async def get_version(project_id:UUID,version:int,db=Depends(get_session),user=Depends(require_active_user)):
    p=snapshot(await owned(db,user.id,project_id),version)
    return project_view(p)

@router.put('/{project_id}')
async def save(project_id:UUID,body:ProjectInput,request:Request,db=Depends(get_session),user=Depends(require_active_user)):
    p=await owned(db,user.id,project_id,lock=True);await idle(db,p,body.revision)
    data=body.model_dump(exclude={'revision'});data['web_search']=effective_search(await search_policy(db,request.app.state.secret_box),body.web_search if 'web_search' in body.model_fields_set else None)
    invalidate(p)
    theme=styles.identity(body.style);data.update(template_id=theme['id'],template_version=theme['version'])
    for key,value in data.items():setattr(p,key,value)
    p.outline=None;p.status='draft';p.revision+=1;await db.commit();return await view(db,p)

@router.delete('/{project_id}',status_code=204)
async def remove(project_id:UUID,revision:int,db=Depends(get_session),user=Depends(require_active_user)):
    p=await owned(db,user.id,project_id,lock=True);await idle(db,p,revision)
    keys=(await db.scalars(select(PptMaterial.object_key).where(PptMaterial.project_id==p.id))).all()
    await enqueue_object_cleanup(db,keys);await db.delete(p);await db.commit()

@router.put('/{project_id}/outline')
async def save_outline(project_id:UUID,body:OutlineInput,db=Depends(get_session),user=Depends(require_active_user)):
    p=await owned(db,user.id,project_id,lock=True);await idle(db,p,body.revision)
    if not p.outline:raise api_error(409,'outline_missing','请先生成大纲')
    data=body.model_dump(mode='json',exclude={'revision'})
    for slide in data['slides']:slide['slots']={}
    if p.outline.get('review') and outline_digest(p.outline)==outline_digest(data):data['review']=p.outline['review']
    invalidate(p);p.outline=data;p.status='outline_ready';p.revision+=1;await db.commit();return await view(db,p)

@router.post('/{project_id}/confirm')
async def confirm_outline(project_id:UUID,body:ConfirmInput,db=Depends(get_session),user=Depends(require_active_user)):
    p=await owned(db,user.id,project_id,lock=True);await idle(db,p,body.revision)
    if not p.outline:raise api_error(409,'outline_missing','请先生成并保存大纲')
    try:require_reviewed_outline(p.outline)
    except KnowledgeError as exc:raise api_error(409,'outline_review_required',str(exc)) from None
    p.confirmed_revision=p.revision
    if not p.pages or p.rendered_revision!=p.revision:p.status='outline_confirmed'
    await db.commit();return await view(db,p)

@router.post('/{project_id}/jobs/{kind}')
async def submit(project_id:UUID,kind:str,body:JobInput,request:Request,db=Depends(get_session),user=Depends(require_active_user)):
    if kind not in ['outline','rewrite','check','render','revise']:raise api_error(404,'job_not_found','任务类型不存在')
    p=await owned(db,user.id,project_id,lock=True)
    previous=await db.scalar(select(PptJob).where(PptJob.project_id==p.id,PptJob.kind==kind,PptJob.idempotency_key==body.idempotency_key))
    payload=body.model_dump(mode='json',exclude={'revision','idempotency_key'})
    if previous:
        if previous.expected_revision!=body.revision or previous.payload!=payload:raise api_error(409,'idempotency_conflict','此请求标识已用于其他操作')
        return job_view(previous)
    await idle(db,p,body.revision)
    if kind=='revise' and p.pages:
        requested=set(payload['slide_ids'])
        try:require_deliverable_pages([page for page in p.pages if page['id'] not in requested]) if any(page['id'] not in requested for page in p.pages) else None
        except QualityError:raise api_error(409,'ppt_review_migration_required','未选页面尚未完成当前自动审核，请先从大纲重新生成并审核整份课件，或选择全部页面修改；原课件已保留。') from None
    if not await resolve(db,request.app.state.secret_box,Purpose.outline_llm):raise api_error(409,'system_unavailable','大纲模型尚未配置，请联系管理员')
    p.web_search=effective_search(await search_policy(db,request.app.state.secret_box),p.web_search)
    if kind!='outline' and not p.outline:raise api_error(409,'outline_missing','请先生成并保存大纲')
    if kind in ('render','revise'):
        try:require_reviewed_outline(p.outline)
        except KnowledgeError as exc:raise api_error(409,'outline_review_required',str(exc)) from None
    if kind=='render' and p.confirmed_revision!=p.revision:raise api_error(409,'outline_not_confirmed','请先确认当前大纲，再开始生成 PPT')
    if kind in ['rewrite','revise']:
        known={s['id'] for s in p.outline['slides']}
        ids=payload['slide_ids']
        if not ids or len(ids)!=len(set(ids)) or not set(ids)<=known or not body.instruction:raise api_error(422,'invalid_selection','请选择页面并填写修改要求')
    if kind=='revise' and (not p.pages or p.rendered_revision!=p.revision):raise api_error(409,'ppt_not_ready','请先生成完整课件')
    params=await get_generation_params(db);await require_generation_capacity(db,user.id,params.max_concurrent_jobs)
    job=PptJob(owner_id=user.id,project_id=p.id,kind=kind,idempotency_key=body.idempotency_key,expected_revision=p.revision,payload=payload)
    db.add(job);await db.flush()
    if kind in ('render','revise'):
        from app.credits.service import reserve_ppt
        await reserve_ppt(db,job,p.title)
    p.status='generating';await db.commit();await db.refresh(job);return job_view(job)

def material_view(m):return {k:getattr(m,k) for k in ['id','filename','size','status','error_message','parse_warnings']}

@router.get('/{project_id}/materials')
async def materials(project_id:UUID,db=Depends(get_session),user=Depends(require_active_user)):
    await owned(db,user.id,project_id)
    return [material_view(m) for m in (await db.scalars(select(PptMaterial).where(PptMaterial.project_id==project_id,PptMaterial.owner_id==user.id,PptMaterial.status!='archived').order_by(PptMaterial.created_at))).all()]

@router.post('/{project_id}/materials')
async def upload(project_id:UUID,request:Request,revision:int, file:UploadFile=File(...),db=Depends(get_session),user=Depends(require_active_user)):
    check_origin(request);p=await owned(db,user.id,project_id,lock=True);await idle(db,p,revision);settings=request.app.state.settings
    data=bytearray()
    while chunk:=await file.read(1024*1024):
        data.extend(chunk)
        if len(data)>settings.upload_file_bytes:raise api_error(413,'file_too_large','单个文件不能超过 25 MiB')
    filename=Path((file.filename or 'material').replace(chr(92),'/')).name[:255]
    try:mime=await asyncio.to_thread(validate_document,filename,bytes(data))
    except ValueError:raise api_error(422,'invalid_file','不支持或无法读取该文件，请检查格式') from None
    rows=(await db.scalars(select(PptMaterial).where(PptMaterial.project_id==p.id,PptMaterial.status!='archived'))).all()
    if len(rows)>=settings.upload_project_files or sum(m.size for m in rows)+len(data)>settings.upload_project_bytes:raise api_error(413,'upload_limit','每个课件最多 10 个文件，累计 100 MiB')
    key=f'ppt/{user.id}/{p.id}/{uuid4()}'
    storage=MaterialStorage(settings)
    try:
        await asyncio.to_thread(storage.put,key,bytes(data),mime)
        m=PptMaterial(owner_id=user.id,project_id=p.id,filename=filename,object_key=key,content_type=mime,size=len(data));db.add(m)
        invalidate(p);p.outline=None;p.revision+=1;p.status='draft';await db.commit();await db.refresh(m)
    except Exception:
        await db.rollback();await enqueue_object_cleanup(db,[key]);await db.commit()
        raise api_error(503,'upload_failed','素材上传失败，请重试') from None
    return material_view(m)

async def owned_material(db,user,project_id,mid):
    await owned(db,user.id,project_id)
    m=await db.scalar(select(PptMaterial).where(PptMaterial.id==mid,PptMaterial.project_id==project_id,PptMaterial.owner_id==user.id,PptMaterial.status!='archived'))
    if not m:raise api_error(404,'material_not_found','素材不存在')
    return m

@router.get('/{project_id}/materials/{mid}/download')
async def download_material(project_id:UUID,mid:UUID,request:Request,db=Depends(get_session),user=Depends(require_active_user)):
    m=await owned_material(db,user,project_id,mid)
    try:data=await asyncio.to_thread(MaterialStorage(request.app.state.settings).get,m.object_key)
    except Exception:raise api_error(503,'storage_unavailable','素材存储暂时不可用') from None
    return Response(data,media_type=m.content_type,headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(m.filename),'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

@router.delete('/{project_id}/materials/{mid}',status_code=204)
async def delete_material(project_id:UUID,mid:UUID,revision:int,db=Depends(get_session),user=Depends(require_active_user)):
    p=await owned(db,user.id,project_id,lock=True);await idle(db,p,revision);m=await owned_material(db,user,project_id,mid)
    invalidate(p)
    if any(chunk.get('image',{}).get('name') in referenced_images(p) for chunk in m.chunks):m.status='archived'
    else:await enqueue_object_cleanup(db,[m.object_key]);await db.delete(m)
    p.outline=None;p.status='draft';p.revision+=1;await prune_archived_materials(db,p);await db.commit()

@router.post('/{project_id}/materials/{mid}/retry')
async def retry_material(project_id:UUID,mid:UUID,revision:int,db=Depends(get_session),user=Depends(require_active_user)):
    p=await owned(db,user.id,project_id,lock=True);await idle(db,p,revision);m=await owned_material(db,user,project_id,mid)
    m.status='stored';m.error_message=None;m.chunks=[];await db.commit();return material_view(m)

def ready(p,*,partial=False,sid=None):
    if not p.pages or p.rendered_revision!=p.revision or [s['id'] for s in p.pages]!=[s['id'] for s in (p.outline or {}).get('slides',[])]:raise api_error(409,'ppt_not_ready','课件尚未完整生成，或大纲已修改，请重新生成')
    pages=p.pages
    if any(s.get('review') or s.get('delivery') for s in p.pages):
        from .quality import approved_pages
        # Retain the legacy explicit partial export, but new verified delivery is full.
        if partial:
            try:require_deliverable_pages(pages)
            except QualityError:pages=approved_pages(pages)
        if sid:pages=[s for s in p.pages if s['id']==str(sid)]
        if sid and not pages:raise api_error(404,'slide_not_found','页面不存在')
        try:require_deliverable_pages(pages)
        except QualityError as exc:raise api_error(409,'ppt_review_required',str(exc)) from exc
    return pages


@router.get('/{project_id}/slides/{sid}/editor')
async def editor_data(project_id:UUID,sid:UUID,revision:int,request:Request,db=Depends(get_session),user=Depends(require_active_user)):
    from .text_editing import text_blocks,movable_objects
    p=await owned(db,user.id,project_id);await idle(db,p,revision);ready(p)
    page=next((s for s in p.pages if s['id']==str(sid)),None)
    if not page:raise api_error(404,'slide_not_found','页面不存在')
    if page.get('renderer')!=master.VERSION:raise api_error(409,'ppt_editor_unavailable','此旧版页面暂不支持直接编辑，请使用 AI 修改')
    assets=await load_assets(db,p,request.app.state.settings,page_images([page]),pages=p.pages)
    svg=master.preview(page['svg'],assets).decode('utf-8')
    blocks=text_blocks(page['svg'])
    for block in blocks:
        layout=(page.get('text_layout') or {}).get(block['key'],{})
        if layout.get('rendered')==block['text']:block['text']=layout['text']
    return {'revision':p.revision,'svg':svg,'blocks':blocks,'objects':movable_objects(page['svg'])}

@router.patch('/{project_id}/slides/{sid}/text')
async def edit_text(project_id:UUID,sid:UUID,body:TextEditInput,request:Request,db=Depends(get_session),user=Depends(require_active_user)):
    from copy import deepcopy
    from .text_editing import apply_text_edits,TextEditError
    from .delivery import confirm_teacher_page
    p=await owned(db,user.id,project_id,lock=True);await idle(db,p,body.revision);ready(p)
    index=next((i for i,s in enumerate(p.pages) if s['id']==str(sid)),None)
    if index is None:raise api_error(404,'slide_not_found','页面不存在')
    page=p.pages[index]
    if page.get('renderer')!=master.VERSION:raise api_error(409,'ppt_editor_unavailable','此旧版页面暂不支持直接编辑，请使用 AI 修改')
    try:changed=apply_text_edits(page,[e.model_dump(exclude_unset=True) for e in body.edits],additions=[e.model_dump() for e in body.additions],moves=[e.model_dump() for e in body.moves])
    except TextEditError as exc:raise api_error(422,'ppt_text_invalid',str(exc)) from None
    if all(changed.get(k)==page.get(k) for k in ('svg','title','content','slots')):return await view(db,p)
    try:
        assets=await load_assets(db,p,request.app.state.settings,page_images([changed]),pages=p.pages)
        master.validate_svg(changed['svg'],assets,require_visual=False)
    except master.MasterError as exc:raise api_error(422,'ppt_text_invalid','未保存：'+str(exc)) from None
    changed=confirm_teacher_page(changed,user.id)
    pages=deepcopy(p.pages);pages[index]=changed;outline=deepcopy(p.outline)
    for slide in outline['slides']:
        if slide['id']==str(sid):
            for key in ('title','content','slots'):slide[key]=deepcopy(changed[key])
    if outline_digest(outline)!=outline_digest(p.outline):
        outline.pop('review',None)
        outline['teacher_confirmation']={'version':'ppt-teacher-confirmed-1','content_sha256':outline_digest(outline)}
    invalidate(p);p.revision+=1;p.pages=pages;p.outline=outline;p.status='ready';p.confirmed_revision=p.rendered_revision=p.revision
    await db.commit();return await view(db,p)

@router.get('/{project_id}/slides/{sid}/preview')
async def preview(project_id:UUID,sid:UUID,request:Request,version:int|None=Query(None,ge=1),db=Depends(get_session),user=Depends(require_active_user)):
    p=snapshot(await owned(db,user.id,project_id),version);ready(p,sid=sid)
    for n,s in enumerate(p.pages,1):
        if s['id']==str(sid):
            try:
                if s.get('renderer'):
                    if s['renderer']!=master.VERSION:raise master.MasterError('课件渲染版本不可用，请重新生成')
                    assets=await load_assets(db,p,request.app.state.settings,page_images([s]),pages=p.pages)
                    data=master.preview(s['svg'],assets)
                else:data=preview_svg(s,p.title,n)
            except master.MasterError as exc:raise api_error(409,'ppt_asset_unavailable',str(exc)) from exc
            except Exception:raise api_error(503,'ppt_preview_failed','课件预览暂时不可用，请稍后重试') from None
            return Response(data,media_type='image/svg+xml',headers={'Cache-Control':'no-store','Content-Security-Policy':"default-src 'none'; img-src data:; style-src 'unsafe-inline'",'X-Content-Type-Options':'nosniff'})
    raise api_error(404,'slide_not_found','页面不存在')

async def require_export_capacity(db,project_id,revision):
    # Transaction locks cover all API processes; session closure releases them.
    key=int.from_bytes(sha256(f'{project_id}:{revision}'.encode()).digest()[:4],signed=True)
    async def acquire(namespace,key):
        return await db.scalar(text('SELECT pg_try_advisory_xact_lock(:namespace,:key)'),{'namespace':namespace,'key':key})
    if not await acquire(73016424,key):raise api_error(429,'ppt_export_busy','此课件正在导出，请稍后重试')
    for slot in range(2):
        if await acquire(73016425,slot):return
    raise api_error(429,'ppt_export_busy','导出服务繁忙，请稍后重试')

async def compile_with_capacity_held(pages,title,assets):
    task=asyncio.create_task(asyncio.to_thread(master.compile_deck,pages,title,assets))
    try:return await asyncio.shield(task)
    except asyncio.CancelledError:
        # Keep the slot until its thread/subprocess completes after disconnection.
        await task
        raise

@router.get('/{project_id}/export')
async def export(project_id:UUID,request:Request,partial:bool=False,version:int|None=Query(None,ge=1),db=Depends(get_session),user=Depends(require_active_user)):
    project=await owned(db,user.id,project_id)
    p=snapshot(project,version);pages=ready(p,partial=partial)
    title=p.title+('（部分完成 '+str(len(pages))+'/'+str(len(p.pages))+' 页）' if len(pages)!=len(p.pages) else '')
    if any(s.get('renderer') for s in pages):await require_export_capacity(db,p.id,p.revision)
    try:
        if any(s.get('renderer') for s in pages):
            if any(s.get('renderer')!=master.VERSION for s in pages):raise master.MasterError('课件渲染版本不一致，请重新生成')
            assets=await load_assets(db,p,request.app.state.settings,page_images(pages))
            data=await compile_with_capacity_held(pages,title,assets)
        else:data=await asyncio.to_thread(export_pptx,pages,title)
    except master.MasterError as exc:raise api_error(409,'ppt_export_failed',str(exc)) from exc
    except Exception:raise api_error(503,'ppt_export_failed','课件导出暂时不可用，请稍后重试') from None
    if len(pages)==len(p.pages):
        project.exported_revision=p.revision
        await db.commit()
    return Response(data,media_type='application/vnd.openxmlformats-officedocument.presentationml.presentation',headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(title+'.pptx'),'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
