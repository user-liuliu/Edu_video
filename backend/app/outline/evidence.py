import re
from uuid import uuid4
from urllib.parse import urlsplit
from sqlalchemy import select
from app.models import MaterialChunk, Material
from app.search.service import search_cached

def source_grade(url):
    host=(urlsplit(url).hostname or '').lower()
    if host.endswith(('.gov.cn','.edu.cn','.gov','.edu')): return 'institution'
    if host=='wikipedia.org' or host.endswith('.wikipedia.org') or host=='baike.baidu.com': return 'secondary'
    if any(host==h or host.endswith('.'+h) for h in ('zhihu.com','reddit.com','tieba.baidu.com','douban.com')): return 'discussion'
    return 'general'

async def collect_evidence(db,project,search_config,http,redis,*,allow_web_search,allow_materials=True):
    rows=(await db.execute(select(MaterialChunk,Material.filename).join(Material,Material.id==MaterialChunk.material_id).where(
        MaterialChunk.owner_id==project.owner_id,MaterialChunk.project_id==project.id,Material.owner_id==project.owner_id,Material.status=='ready'
    ).order_by(MaterialChunk.material_id,MaterialChunk.position))).all() if allow_materials else []
    tokens=set(re.findall(r'[a-zA-Z]{2,}|[一-鿿]{2}',project.prompt))
    rows=sorted(rows,key=lambda row:-sum(t in row[0].text for t in tokens))[:30]
    result=[{'id':str(uuid4()),'claim':filename,'source_type':'material','source_ref':str(chunk.material_id),
             'location':chunk.location,'excerpt':chunk.text[:4000],'source_grade':'uploaded','verification_status':'unverified'} for chunk,filename in rows]
    await db.commit()
    if allow_web_search:
        if not search_config: raise ValueError('联网搜索尚未配置，请关闭联网或联系管理员')
        hits=await search_cached(project.prompt[:500],search_config,http,redis,allow_web_search=True)
        for hit in hits:
            result.append({'id':str(uuid4()),'claim':hit['title'],'source_type':'web','source_ref':hit['url'],'location':'搜索摘要',
                           'excerpt':hit['excerpt'],'source_grade':source_grade(hit['url']),'verification_status':'unverified'})
    return result

def enforce_evidence(outline,evidence):
    known={str(e['id']):e for e in evidence}
    for segment in outline['segments']:
        if any(str(i) not in known for i in segment['evidence_ids']): raise ValueError('模型引用了不存在的依据，请重新生成')
        notes=list(segment.get('review_notes',[]))
        if not segment['evidence_ids']: notes.append('未核实出处：请教师核对教材和事实')
        elif all(known[str(i)]['source_grade']=='discussion' for i in segment['evidence_ids']): notes.append('论坛内容不能独立佐证史实，请补充可靠依据')
        else: notes.append('依据来自上传材料或搜索摘要，仍需人工核实；来源冲突时请以可靠教材为准')
        if segment['content_kind']=='reenactment': notes.append('本段包含情景演绎，不应当作真实历史影像或原话')
        segment['review_notes']=list(dict.fromkeys(notes))[:30]
    return outline
