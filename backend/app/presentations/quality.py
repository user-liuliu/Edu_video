"""Review actual exported pages, with explicit verdicts and bounded page repairs."""
import asyncio
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, ValidationError

VERSION='ppt-practical-review-2'
MAX_REPAIRS=2

class QualityError(ValueError): pass

class Issue(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    category: Literal['teaching','readability','visual','file','generation','service']
    severity: Literal['blocking','suggestion'] | None=None
    message: str=Field(min_length=1,max_length=300)
    repair: str=Field(min_length=1,max_length=500)

class Verdict(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    status: Literal['passed','needs_attention']
    issues: list[Issue]=Field(max_length=8)

def blocking_issues(issues):
    return [i for i in issues if i.get('category')!='visual' and (i.get('category') in ('teaching','readability','file','generation','service') or i.get('severity','blocking')=='blocking')]

def parse_review(data):
    try:
        verdict=Verdict.model_validate(data)
        issues=[i.model_dump(exclude_none=True) for i in verdict.issues]
        if verdict.status=='passed' and blocking_issues(issues) or verdict.status=='needs_attention' and not issues:raise ValueError('contradictory verdict')
        if any(not i.message.strip() or not i.repair.strip() for i in verdict.issues):raise ValueError('empty issue')
        return [{**i,'severity':'blocking' if i.get('category') in ('teaching','readability','file','generation','service') or i in blocking_issues(issues) else 'suggestion'} for i in issues]
    except (ValidationError,ValueError,TypeError) as exc:
        raise QualityError('视觉审核返回格式无效，请重试或联系管理员检查看图模型') from exc

def content_digest(page):
    source={k:v for k,v in page.items() if k not in ('review','delivery')}
    return sha256(json.dumps(source,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def render_review_images(pptx,count):
    """Convert the native deck, not its SVG preview, in a network-denied process."""
    from app.materials.parsers import _restrict_converter
    import fitz
    if os.name!='posix':raise QualityError('页面审核需要部署环境中的 LibreOffice 转换服务')
    if not 1<=count<=40 or not pptx.startswith(b'PK') or len(pptx)>40*1024**2:raise QualityError('页面审核的课件数据无效')
    try:
        with tempfile.TemporaryDirectory(prefix='ppt-review-') as folder:
            root=Path(folder);source=root/'deck.pptx';source.write_bytes(pptx)
            profile=root/'profile'/'user';profile.mkdir(parents=True)
            (profile/'registrymodifications.xcu').write_text(
                '<?xml version="1.0"?><oor:items xmlns:oor="http://openoffice.org/2001/registry">'
                '<item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop></item></oor:items>',encoding='utf-8')
            process=subprocess.Popen(['libreoffice','-env:UserInstallation='+(root/'profile').as_uri(),
                '--headless','--convert-to','pdf','--outdir',str(root),str(source)],
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,preexec_fn=_restrict_converter,start_new_session=True)
            try: process.wait(timeout=70)
            finally:
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                process.wait()
            pdf=root/'deck.pdf'
            if process.returncode or not pdf.is_file() or pdf.stat().st_size>80*1024**2:raise QualityError('导出页面转换失败，请联系管理员检查 LibreOffice')
            with fitz.open(pdf) as doc:
                if len(doc)!=count:raise QualityError('导出课件页数与大纲不一致')
                images=[]
                for page in doc:
                    if page.rect.width<=0 or abs(page.rect.width/page.rect.height-16/9)>.02:raise QualityError('导出页面比例异常')
                    pix=page.get_pixmap(matrix=fitz.Matrix(1280/page.rect.width,720/page.rect.height),alpha=False)
                    data=pix.tobytes('png')
                    if len(data)>3*1024**2:raise QualityError('审核页面图片过大')
                    images.append(data)
                return images
    except QualityError:raise
    except (OSError,subprocess.SubprocessError,RuntimeError,ValueError) as exc:
        raise QualityError('导出页面审核渲染失败或超时，请联系管理员检查转换服务') from exc

def require_approved_pages(pages):
    if not pages:raise QualityError('课件尚未通过自动审核，暂不开放预览，请重新生成并审核')
    failed=[]
    for n,page in enumerate(pages,1):
        verdict=page.get('review') or {}
        if (verdict.get('status')!='passed' or not isinstance(verdict.get('issues'),list) or blocking_issues(verdict.get('issues',[])) or verdict.get('version') not in (VERSION,'ppt-visual-review-1')
            or verdict.get('version')=='ppt-visual-review-1' and verdict.get('issues')!=[]
            or verdict.get('content_sha256')!=content_digest(page) or not verdict.get('image_sha256')):
            failed.append(str(n))
    if failed:raise QualityError('第 '+ '、'.join(failed)+' 页未通过自动审核，暂不开放预览。自动修改已达到本次上限，请重试或调整大纲；上一版课件已保留。')


def approved_pages(pages):
    approved=[]
    for page in pages:
        try:require_approved_pages([page])
        except QualityError:continue
        approved.append(page)
    return approved


async def audit_pages(pages,*,selected_ids,render,review,repair,on_update=None,rebuild=None,allow_partial=False,render_errors=()):
    """Review each replacement; checkpoint budgets before requesting model repair."""
    result=[deepcopy(p) if p['id'] in selected_ids else p for p in pages]
    pending={p['id'] for p in result if p['id'] in selected_ids}
    if pending!=set(selected_ids):raise QualityError('审核页面选择无效')
    async def save(page):
        if on_update:await on_update(deepcopy(page))
    def budget(value,limit):return value if type(value) is int and 0<=value<=limit else limit
    while pending:
        technical=None
        try:images=await render(result)
        except render_errors as exc:
            images=[b'']*len(result)
            technical=[{'category':'file','severity':'blocking','message':'导出检查失败：'+str(exc)[:250],'repair':'根据导出校验意见修复图形和版式后重新导出审核'}]
        if len(images)!=len(result):raise QualityError('导出课件页数与审核页数不一致')
        again=set()
        for n,page in enumerate(result):
            if page['id'] not in pending:continue
            found=technical if technical is not None else await review(deepcopy(page),images[n])
            issues=parse_review({'status':'needs_attention' if found else 'passed','issues':found})
            blockers=blocking_issues(issues)
            previous=page.get('review') or {}
            repairs=budget(previous.get('repairs',0),MAX_REPAIRS)
            rebuilds=budget(previous.get('rebuilds',0),1)
            page['review']={'version':VERSION,'status':'needs_attention' if blockers else 'passed','issues':issues,
                'repairs':repairs,'rebuilds':rebuilds,'content_sha256':content_digest(page),'image_sha256':sha256(images[n]).hexdigest()}
            await save(page)
            if not blockers:continue
            operation=None
            if repair and repairs<MAX_REPAIRS:
                page['review']['repairs']=repairs+1;operation=repair
            elif rebuild and rebuilds<1:
                page['review']['rebuilds']=rebuilds+1;operation=rebuild
            if operation is None:continue
            await save(page)
            try:
                replacement=await operation(deepcopy(page),blockers)
            except (ValueError,RuntimeError) as exc:
                if not allow_partial:raise
                # A failed repair consumes its budget. Continue with the independent
                # simplified rebuild instead of aborting every other page.
                page['review']['repairs']=MAX_REPAIRS
                page['review']['issues']=[*issues,{'category':'generation','severity':'blocking','message':'自动修改未完成：'+str(exc)[:200],'repair':'改用简化版式重建后重新审核'}][:8]
                await save(page)
                if operation is repair and rebuild and rebuilds<1:again.add(page['id'])
                continue
            if replacement.get('id')!=page['id']:raise QualityError('修复页面 ID 已变化，原课件已保留')
            replacement=deepcopy(replacement);replacement['review']={**page['review'],'status':'pending'}
            result[n]=replacement
            await save(replacement)
            again.add(page['id'])
        pending=again
    warnings=[{'slide_id':p['id'],'page':n+1,'message':f'第 {n+1} 页仍需检查：'+ '；'.join(i['message'] for i in p.get('review',{}).get('issues',[]))}
        for n,p in enumerate(result) if p.get('review',{}).get('status')=='needs_attention']
    if not allow_partial:require_approved_pages([p for p in result if p['id'] in selected_ids])
    return result,warnings
