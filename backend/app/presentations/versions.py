"""Immutable views of retained PPT revisions, including legacy page-only snapshots."""
from copy import deepcopy
from types import SimpleNamespace
from app.errors import api_error
from . import styles

def summaries(project):
    versions={}
    for h in project.history or []:
        if h.get('pages') and type(h.get('revision')) is int and h['revision']!=project.rendered_revision:
            versions[h['revision']]={'revision':h['revision'],'title':h.get('title',project.title),'page_count':len(h['pages']),'created_at':h.get('created_at')}
    return sorted(versions.values(),key=lambda x:x['revision'],reverse=True)

def snapshot(project,version):
    if version is None:return project
    if project.rendered_revision==version and project.pages and project.revision==version:return project
    stored=next((h for h in reversed(project.history or []) if h.get('revision')==version and h.get('pages')),None)
    if not stored:raise api_error(404,'ppt_version_not_found','此课件版本不存在或已超出保留范围')
    pages=deepcopy(stored['pages'])
    outline=deepcopy(stored.get('outline')) or {'slides':[{k:p.get(k,{} if k=='slots' else '') for k in ('id','layout','title','content','slots')} for p in pages]}
    return SimpleNamespace(id=project.id,owner_id=project.owner_id,title=stored.get('title',project.title),
        prompt=project.prompt,style=stored.get('style','auto'),web_search=project.web_search,template_id=stored.get('template_id',styles.page_identity(pages[0])['id']),template_version=stored.get('template_version','1.0.0'),
        status='ready',revision=version,confirmed_revision=version,rendered_revision=version,outline=outline,pages=pages,
        warnings=deepcopy(stored.get('warnings',[])),created_at=stored.get('created_at',project.created_at),updated_at=stored.get('created_at',project.updated_at),history=[])

def referenced_images(project):
    from .master_assets import page_images
    pages=list(project.pages or [])
    for stored in project.history or []:pages.extend(stored.get('pages') or [])
    return page_images([p for p in pages if p.get('svg')])

async def prune_archived_materials(db,project):
    from sqlalchemy import select
    from .models import PptMaterial
    from app.jobs.dispatcher import enqueue_object_cleanup
    needed=referenced_images(project)
    rows=(await db.scalars(select(PptMaterial).where(PptMaterial.project_id==project.id,PptMaterial.owner_id==project.owner_id,PptMaterial.status=='archived'))).all()
    for material in rows:
        if any(chunk.get('image',{}).get('name') in needed for chunk in material.chunks):continue
        await enqueue_object_cleanup(db,[material.object_key]);await db.delete(material)
