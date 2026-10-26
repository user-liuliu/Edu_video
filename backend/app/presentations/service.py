from copy import deepcopy
from .versions import summaries
from . import styles
from sqlalchemy import select
from app.errors import api_error
from .models import PptProject,PptJob

async def owned(db,owner_id,project_id,*,lock=False):
    stmt=select(PptProject).where(PptProject.id==project_id,PptProject.owner_id==owner_id).execution_options(populate_existing=True)
    if lock:stmt=stmt.with_for_update()
    project=await db.scalar(stmt)
    if not project:raise api_error(404,'ppt_not_found','课件不存在')
    return project

async def idle(db,project,revision):
    if revision!=project.revision:raise api_error(409,'revision_conflict','课件已更新，请刷新后重试')
    if await db.scalar(select(PptJob.id).where(PptJob.project_id==project.id,PptJob.status.in_(['pending','running'])).limit(1)):
        raise api_error(409,'project_busy','课件正在处理中，请等待任务完成')

def invalidate(project):
    if project.pages:
        snapshot={'revision':project.rendered_revision,'pages':deepcopy(project.pages),'outline':deepcopy(project.outline),
            'title':project.title,'style':getattr(project,'style','auto'),'template_id':getattr(project,'template_id',styles.DEFAULT),'template_version':getattr(project,'template_version','1.0.0'),'warnings':deepcopy(project.warnings or []),'created_at':project.updated_at.isoformat() if project.updated_at else None}
        project.history=[*[h for h in project.history or [] if h.get('revision')!=project.rendered_revision],snapshot][-10:]
    project.pages=[];project.rendered_revision=None;project.confirmed_revision=None

def project_view(p,job=None):
    return {k:getattr(p,k) for k in ['id','title','prompt','style','web_search','template_id','template_version','status','revision','confirmed_revision','rendered_revision','outline','pages','warnings','created_at','updated_at']} | {'template_name':styles.NAMES.get(p.template_id,styles.NAMES[styles.DEFAULT]),'job':job_view(job) if job else None,'versions':summaries(p)}

def job_view(job):
    return {k:getattr(job,k) for k in ['id','project_id','kind','status','stage','progress','error_message','created_at','updated_at']}

async def view(db,p):
    await db.refresh(p)
    job=await db.scalar(select(PptJob).where(PptJob.project_id==p.id).order_by(PptJob.created_at.desc()).limit(1))
    return project_view(p,job)
