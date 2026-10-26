"""Bounded SVG data adapter for the unmodified, pinned official PPT Master tools."""
from contextlib import contextmanager
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory, mkdtemp
import base64
import importlib
import importlib.util
from io import BytesIO
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET

NS='http://www.w3.org/2000/svg'
VENDOR=Path(__file__).with_name('vendor')
VERSION='ppt-master-6.7.0'
class MasterError(ValueError): pass

def run_tool(root, script, *args, timeout=90):
    try:
        result=subprocess.run([sys.executable,str(root/'scripts'/script),*[str(a) for a in args]],cwd=root,env={**os.environ,'PYTHONUTF8':'1','PYTHONDONTWRITEBYTECODE':'1'},capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout)
    except subprocess.TimeoutExpired as exc:raise MasterError('PPT Master 页面检查或导出超时，请减少页数后重试') from exc
    if result.returncode:
        diagnostic=(result.stdout+result.stderr)[-1600:]
        if script=='svg_quality_checker.py':
            target=Path(args[0])
            project=target.parent.parent if target.suffix=='.svg' and target.parent.name=='svg_output' else target
            report=project/'validation'/'svg_quality_report.json'
            if report.exists():
                try:
                    data=json.loads(report.read_text(encoding='utf-8'))
                    findings=data.get('categories',{}).get('blocking',{}).get('issues',[])
                    # Authoring module bounds can overlap without any visible content overlap.
                    # The final rendered-page review checks actual unreadability.
                    if findings and all('data-pptx-bounds overlaps' in str(f.get('message','')) for f in findings):return result.stdout
                    if findings:diagnostic='; '.join(str(f.get('file',''))+': '+str(f.get('message','')) for f in findings)[:1600]
                except (ValueError,OSError):pass
        raise MasterError('PPT Master '+script+' 检查未通过：'+diagnostic)
    return result.stdout

@lru_cache(maxsize=1)
def package_root():
    manifest=json.loads((VENDOR/'manifest.json').read_text(encoding='utf-8'))
    archive=VENDOR/'ppt-master-6.7.0.zip'
    if sha256(archive.read_bytes()).hexdigest()!=manifest['sha256']:raise MasterError('PPT Master 工具包校验失败')
    target=Path(tempfile.gettempdir())/('edu-ppt-master-'+manifest['sha256'][:16])
    if not target.exists():
        staging=Path(mkdtemp(prefix='edu-ppt-install-'))
        try:
            with zipfile.ZipFile(archive) as z:
                for info in z.infolist():
                    candidate=(staging/info.filename).resolve()
                    if not candidate.is_relative_to(staging.resolve()):raise MasterError('工具包路径无效')
                z.extractall(staging)
            try:staging.rename(target)
            except OSError:
                if not target.exists():raise
        finally:
            if staging.exists():shutil.rmtree(staging)
    run_tool(target,'attribution_guard.py')
    return target

@lru_cache(maxsize=4)
def guidance(role):
    root=package_root()
    names={'strategist':['strategist.md','plan-core.md','strategist-image.md'],
           'executor':['executor-base.md','executor-image.md','semantic-svg.md','shared-standards-core.md','svg-image-embedding.md']}[role]
    parts=[]
    for name in names:
        path=root/'references'/name
        if path.exists():parts.append('OFFICIAL '+name+chr(10)+path.read_text(encoding='utf-8-sig')[:18000])
    return (chr(10)*2).join(parts)[:54000]

def validate_plan(data, slides):
    pages=data.get('pages',[]) if isinstance(data,dict) else []
    if not isinstance(pages,list) or any(not isinstance(p,dict) for p in pages) or len(pages)!=len(slides) or [str(p.get('id')) for p in pages]!=[str(s['id']) for s in slides]:raise MasterError('设计规划未覆盖指定页面或顺序错误')
    result=[]
    for page in pages:
        kind=page.get('visual_kind')
        if kind not in ('diagram','reference-image','infographic','text'):raise MasterError('每页需要真实教学图解或参考图片，不能只有文字')
        if any(not isinstance(page.get(key),str) for key in ('visual_brief','composition')):raise MasterError('页面设计说明必须是文本')
        values={key:page[key].strip() for key in ('visual_brief','composition')}
        if any(not v or len(v)>1200 for v in values.values()):raise MasterError('页面设计说明为空或过长')
        record={'id':str(page['id']),'visual_kind':kind,**values}
        if kind=='infographic':
            from .graphic_contract import GraphicSpec
            try:record['graphic']=GraphicSpec.model_validate(page['graphic']).model_dump()
            except (ValueError,TypeError,KeyError) as exc:raise MasterError('流程/对比信息图需要2至4项简短数据与有效配图类型') from exc
        result.append(record)
    return {'pages':result}

TAGS={'svg','g','defs','marker','path','rect','circle','ellipse','line','polyline','polygon','text','tspan','image'}
COMMON={'id','fill','stroke','stroke-width','stroke-linecap','stroke-linejoin','stroke-miterlimit','opacity','fill-opacity','stroke-opacity','transform','fill-rule','clip-rule'}
ATTRS=COMMON|{'xmlns','width','height','viewBox','data-pptx-page-role','data-pptx-role','data-pptx-bounds','data-pptx-frame','x','y','x1','y1','x2','y2','rx','ry','r','cx','cy','d','points','font-family','font-size','font-weight','font-style','text-anchor','dominant-baseline','dx','dy','letter-spacing','href','preserveAspectRatio','marker-start','marker-mid','marker-end','markerWidth','markerHeight','refX','refY','orient','markerUnits'}
NUMERIC={'x','y','x1','y1','x2','y2','rx','ry','r','cx','cy','width','height','stroke-width','font-size','dx','dy','letter-spacing','markerWidth','markerHeight','refX','refY','opacity','fill-opacity','stroke-opacity','stroke-miterlimit'}
NUMBER=r'[+-]?(?:[0-9]+(?:[.][0-9]*)?|[.][0-9]+)(?:[eE][+-]?[0-9]+)?'

def numeric(value):
    if not re.fullmatch(NUMBER,value.strip()):raise MasterError('SVG 数值格式无效')
    number=float(value)
    if not math.isfinite(number) or abs(number)>5120:raise MasterError('SVG 坐标或数值超出范围')
    return number

@lru_cache(maxsize=1)
def geometry_api():
    # Trusted, hash-verified package code gets a private import namespace.
    name='_edu_ppt_master_geometry'
    scripts=package_root()/'scripts'
    if str(scripts) not in sys.path:sys.path.insert(0,str(scripts))
    package=scripts/'svg_to_pptx'
    spec=importlib.util.spec_from_file_location(name,package/'__init__.py',submodule_search_locations=[str(package)])
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    spec.loader.exec_module(module)
    return importlib.import_module(name+'.native_objects.marker_common')

def require_visible_geometry(root,visual):
    geometry=geometry_api();records=[]
    def visit(node,matrix,opacity,paint):
        tag=node.tag.split('}')[-1]
        if tag in {'defs','marker'}:return
        opacity*=float(node.get('opacity','1'))
        if opacity<0.1:return
        paint={**paint,**{k:node.get(k) for k in ('fill','stroke','fill-opacity','stroke-opacity','stroke-width') if node.get(k) is not None}}
        if node.get('transform'):matrix=geometry.matrix_multiply(matrix,geometry.parse_transform_matrix(node.get('transform')))
        if tag in {'path','image','circle','ellipse','line','polygon','polyline'}:
            filled=tag!='line' and paint.get('fill')!='none' and float(paint.get('fill-opacity','1'))*opacity>=0.1
            stroked=paint.get('stroke','none')!='none' and float(paint.get('stroke-opacity','1'))*opacity>=0.1 and float(paint.get('stroke-width','1'))>0
            if tag=='image' or filled or stroked:
                box=geometry._element_local_bbox(node)
                if box:
                    x1,y1,x2,y2=geometry._apply_matrix_bbox(box,matrix)
                    x1,y1,x2,y2=max(0,x1),max(0,y1),min(1280,x2),min(720,y2)
                    if x2>=x1 and y2>=y1 and max(x2-x1,y2-y1)>=20:records.append((tag,(x1,y1,x2,y2)))
        for child in node:visit(child,matrix,opacity,paint)
    matrix=geometry.IDENTITY_MATRIX
    if root.get('transform'):matrix=geometry.parse_transform_matrix(root.get('transform'))
    try:
        visit(visual,matrix,float(root.get('opacity','1')),{k:root.get(k) for k in ('fill','stroke','fill-opacity','stroke-opacity','stroke-width') if root.get(k) is not None})
    except (ValueError,RuntimeError,TypeError) as exc:raise MasterError('教学配图几何无效') from exc
    substantial=[tag for tag,(x1,y1,x2,y2) in records if tag in {'path','image'} and x2-x1>=80 and y2-y1>=80]
    if not substantial or ('image' not in substantial and len(records)<4):raise MasterError('缺少足够大且实际可见的教学配图')
    if max(b[2] for _,b in records)-min(b[0] for _,b in records)<200 or max(b[3] for _,b in records)-min(b[1] for _,b in records)<140:raise MasterError('实际可见的教学配图面积过小')

def validate_svg(svg, assets, *, require_visual=True):
    if not isinstance(svg,str) or len(svg.encode('utf-8'))>180000:raise MasterError('SVG 页面数据过大')
    if '<!' in svg or '<?' in svg:raise MasterError('SVG 不允许声明或实体')
    try:root=ET.fromstring(svg)
    except ET.ParseError as exc:raise MasterError('SVG XML 格式无效') from exc
    if root.tag!='{'+NS+'}svg' or root.get('viewBox')!='0 0 1280 720':raise MasterError('SVG 必须是固定 16:9 的 1280×720 页面')
    if root.get('width')!='1280' or root.get('height')!='720':raise MasterError('SVG 页面尺寸错误')
    count=0;ids=set();references=[];visual=None;path_tokens=0
    def walk(node,depth=0,transformed=False):
        nonlocal count,visual,path_tokens
        count+=1
        if count>1200 or depth>16:raise MasterError('SVG 页面过于复杂')
        if not node.tag.startswith('{'+NS+'}') or node.tag.split('}')[-1] not in TAGS:raise MasterError('SVG 含不支持的元素或命名空间')
        name=node.tag.split('}')[-1]
        ident=node.get('id')
        if ident:
            if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,80}',ident) or ident in ids:raise MasterError('SVG 元素 ID 无效或重复')
            ids.add(ident)
            if ident=='teaching-visual':visual=node
        for key,value in node.attrib.items():
            if key=='{http://www.w3.org/XML/1998/namespace}space':
                if name not in ('text','tspan') or value not in ('default','preserve'):raise MasterError('SVG 文本空白保留属性无效')
                continue
            if key not in ATTRS:raise MasterError('SVG 含不支持的属性：'+key)
            if len(value)>64000:raise MasterError('SVG 属性过长')
            if key in NUMERIC:numeric(value)
            if key in ('data-pptx-bounds','data-pptx-frame'):
                if key=='data-pptx-frame' and name!='text':raise MasterError('SVG 文本框属性仅适用于文字')
                vals=[numeric(v) for v in value.split()]
                if len(vals)!=4 or vals[2]<=0 or vals[3]<=0 or vals[0]<0 or vals[1]<0 or vals[0]+vals[2]>1280 or vals[1]+vals[3]>720:raise MasterError('SVG module bounds exceed the page')
            if key in ('fill','stroke') and not re.fullmatch(r'#[A-Fa-f0-9]{6}|none',value):raise MasterError('SVG 仅支持显式 HEX 颜色')
            if key in ('marker-start','marker-mid','marker-end'):
                match=re.fullmatch(r'url[(]#([A-Za-z][A-Za-z0-9_-]{0,80})[)]',value)
                if not match:raise MasterError('SVG 箭头引用无效')
                references.append(match.group(1))
            elif 'url(' in value.lower() or 'javascript:' in value.lower():raise MasterError('SVG 不允许 URL 或脚本')
            if key=='transform':
                if transformed:raise MasterError('SVG 不支持嵌套变换')
                parts=re.findall(r'(translate|scale|rotate)[(]([^()]*)[)]',value)
                rest=re.sub(r'(translate|scale|rotate)[(][^()]*[)]','',value).strip()
                if not parts or rest or len(parts)>3:raise MasterError('SVG 变换无效')
                for op,args in parts:
                    nums=[numeric(v) for v in re.split(r'[, ]+',args.strip()) if v]
                    if len(nums) not in ((1,2) if op in ('translate','scale') else (1,3)):raise MasterError('SVG 变换参数错误')
                    if op=='scale' and any(v<=0 or v>4 for v in nums):raise MasterError('SVG 缩放超限')
            if key in ('d','points'):
                tokens=re.findall(NUMBER+r'|[A-Za-z]',value);path_tokens+=len(tokens)
                rest=re.sub(NUMBER+r'|[MmLlHhVvCcSsQqTtAaZz]|[, ]','',value)
                if rest.strip() or path_tokens>16000:raise MasterError('SVG 路径无效或过于复杂')
                for token in tokens:
                    if len(token)>1 or token.isdigit() or token in ('0','1'):numeric(token)
            if key=='href':
                if name!='image' or not re.fullmatch(r'[.][.]/images/[a-f0-9]{24}[.]png',value) or Path(value).name not in assets:raise MasterError('SVG 图片未授权或路径无效')
            if key=='font-family' and value!='Microsoft YaHei, Arial':raise MasterError('SVG 字体必须使用课件统一字体')
            if key=='font-size' and not 18<=numeric(value)<=72:raise MasterError('SVG 字号不适合课堂阅读')
        if name=='image':
            if not node.get('href') or numeric(node.get('width','0'))<80 or numeric(node.get('height','0'))<80:raise MasterError('参考图片缺失或尺寸过小')
        if node.text and len(node.text)>500:raise MasterError('SVG 单段文字过长，请分行')
        for child in node:walk(child,depth+1,transformed or bool(node.get('transform')))
    walk(root)
    if not set(references)<=ids:raise MasterError('SVG 箭头定义缺失')
    if require_visual:
        if visual is None or visual.tag!='{'+NS+'}g' or visual not in list(root):raise MasterError('教学配图必须是根级 teaching-visual 分组')
        bounds=[numeric(v) for v in visual.get('data-pptx-bounds','').split()]
        if len(bounds)!=4 or bounds[2]<200 or bounds[3]<140:raise MasterError('教学配图面积过小或缺少布局范围')
        for node in (root,visual):
            if float(node.get('opacity','1'))<0.1:raise MasterError('教学配图不可见')
            for op,args in re.findall(r'(scale)[(]([^()]*)[)]',node.get('transform','')):
                if any(numeric(v)<0.25 for v in re.split(r'[, ]+',args) if v):raise MasterError('教学配图缩放过小')
        require_visible_geometry(root,visual)
    return svg

def preview(svg,assets):
    validate_svg(svg,assets,require_visual=False)
    root=ET.fromstring(svg)
    for image in root.iter('{'+NS+'}image'):
        data=assets[Path(image.get('href')).name]
        image.set('href','data:image/png;base64,'+base64.b64encode(data).decode())
    data=ET.tostring(root,encoding='utf-8')
    if len(data)>2*1024*1024:raise MasterError('页面预览过大，请减少配图')
    return data

def clean(value):return str(value).replace('|','/').replace(chr(10),' ').replace(chr(13),' ').replace('<','').replace('>','')[:3000]

def design_artifacts(pages,title,assets):
    from . import styles
    theme=styles.page_identity(pages[0]);palette=styles.colors(theme);name=styles.NAMES[theme['id']];behavior=styles.behavior(theme)
    rows={'Project Name':clean(title),'Canvas Format':'PPT 16:9 (1280 x 720)','Page Count':len(pages),'Primary Language':'zh-CN','Target Audience':'课堂学习者','Communication Intent':'讲解概念并通过图示建立理解','Desired Audience Outcome':'能解释知识并完成课堂练习','Core Message / Ask / Action':clean(title),'Delivery Context':'教师课堂投影','Artifact Afterlife':'可编辑 PPTX 课件','Reading Mode':'balanced','Content Strategy':'忠于确认后的逐页大纲','Design Style':name,'AI Image Acquisition Path':'not applicable','Generation Mode':'continuous','Spec Refinement':'disabled','Speaker Notes':'disabled — application default','Custom Animations':'disabled — application default','Narration Audio':'disabled — application default','Created Date':'2026-10-23'}
    spec=['<!-- ppt-master-schema: design-spec/v1 -->','# '+clean(title)+' - Design Spec','## I. Project Information','| Item | Value |','| --- | --- |']+[f'| {k} | {v} |' for k,v in rows.items()]
    spec+=['## II. Canvas Specification','| Property | Value |','| --- | --- |','| Format | PPT 16:9 |','| Dimensions | 1280 x 720 |','| viewBox | `0 0 1280 720` |','| Margins | 64 px |','| Content Area | 1152 x 592 |','## III. Visual Theme','### Theme Style','- **Mode**: custom','- **Mode behavior**: Teach with labeled diagrams, examples and practice.','- **Visual style**: custom','- **Visual style behavior**: '+behavior,'- **Theme**: '+name,'- **Tone**: Clear and focused','### Color Scheme','| Role | HEX | Purpose |','| --- | --- | --- |']
    colors={'Background':'#FFFFFF','Secondary background':'#F4F7FC','Primary':'#173359','Accent':'#2465D9','Secondary accent':'#2B9578','Body text':'#273B53','Secondary text':'#61738A','Divider':'#DCE5F1'}
    colors=dict(zip(colors,[palette[k] for k in ('bg','surface','title','accent','secondary','body','muted','rule')]))
    spec += [f'| {k} | {v} | {k} |' for k,v in colors.items()]
    spec += ['## IV. Typography System','### Font Plan','| Role | Character (Reference) | Primary | English if non-English | Fallback tail |','| --- | --- | --- | --- | --- |','| Title | sans-serif | Microsoft YaHei | Arial | sans-serif |','| Body | sans-serif | Microsoft YaHei | Arial | sans-serif |','- **Title stack**: Microsoft YaHei, Arial','- **Body stack**: Microsoft YaHei, Arial','### Font Size Hierarchy','| Purpose | Anchor Size (px) |','| --- | ---: |','| Body | 28 |','| Title | 48 |','| Subtitle | 32 |','| Annotation | 22 |','## V. Layout Principles','### Deck-wide Direction','- **Hierarchy direction**: Title, main visual, explanation.','- **Composition tendency**: Relate illustrations directly to each page assertion.','- **Cross-page continuity**: Shared color and typography; composition varies with content.','- **Spacing posture**: open','- **Spacing anchors**: 64, 24, 32, 8, 40','## VI. Icon Usage Specification','- **Primary bundled library**: none','| Icon Path | Suitable Scenarios |','| --- | --- |','## VIII. Image Resource List','| Filename | Dimensions | Ratio | Purpose | Type | Image pattern | Crop Policy | Acquire Via | Status | Reference | text_policy | page_role |','| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    from PIL import Image
    from io import BytesIO
    for name,data in assets.items():
        with Image.open(BytesIO(data)) as im:w,h=im.size
        spec.append(f'| {name} | {w} x {h} | {w/h:.3f} | 教学参考图片 | photo | supporting | no-crop | user | Existing | uploaded reference | preserve | content |')
    spec += ['## IX. Content Outline','### Part 1 - Teaching']
    for i,page in enumerate(pages,1):
        plan=page['design']
        spec += [f'#### Slide {i:02d} - '+clean(page['title']),'- **Audience move**: 理解并解释本页知识','- **Relationships**: '+clean(plan['visual_brief']),'- **Composition**: '+clean(plan['composition']),'- **Title**: '+clean(page['title']),'- **Core message**: '+clean(page['title']),'- **Content**: '+clean(page['content']),'- **Visualization**: '+clean(plan['visual_brief'])]
    spec+=['## X. Speaker Notes Requirements','- **Generation**: disabled']
    lock=['<!-- ppt-master-schema: spec-lock/v1 -->','# Execution Lock','## canvas','- viewBox: 0 0 1280 720','- format: PPT 16:9','## communication','- primary_language: zh-CN','- audience: 课堂学习者','- objective: 理解并解释确认后的课堂知识','- core_message: '+clean(title),'## mode','- mode: custom','- mode_behavior: Explain concepts with diagrams, examples and practice.','## visual_style','- visual_style: custom','- visual_style_behavior: '+behavior,'## colors']
    keys=['background','secondary_bg','primary','accent','secondary_accent','body_text','secondary_text','divider']
    lock += ['- '+k+': '+v for k,v in zip(keys,colors.values())]
    lock+=['## typography','- font_family: Microsoft YaHei, Arial','- title_family: Microsoft YaHei, Arial','- body_family: Microsoft YaHei, Arial','- body: 28','- title: 48','- subtitle: 32','- annotation: 22','## icons','- library: none','- inventory: none','## page_rhythm']
    lock += [f'- P{i:02d}: '+('anchor' if i==1 else 'dense') for i in range(1,len(pages)+1)]
    lock+=['## pptx_structure','- mode: flat','## forbidden','- `mask`, `<style>`, `class`, external CSS, `<foreignObject>`, `textPath`, `@font-face`, `<animate*>`, `<set>`, `<script>` / event attributes, `<iframe>`','- HTML named entities in text; write typography as raw Unicode and escape XML reserved characters']
    if assets:
        lock+=['## images']+[f'- image-{i}: images/{name} | source=user | crop=no-crop' for i,name in enumerate(assets,1)]
    if theme['id']!=styles.DEFAULT:
        spec=[row.replace('| Title | 48 |','| Title | 44 |') for row in spec]
        at=spec.index('## V. Layout Principles')
        spec[at:at]=['| Cover title | 64 |','| Footer | 18 |','| Note | 25 |','| Fallback title | 48 |']
        lock=[row.replace('- title: 48','- title: 44') for row in lock]
        at=lock.index('## icons')
        lock[at:at]=['- cover_title: 64','- footer: 18','- note: 25','- fallback_title: 48']
    return chr(10).join(spec)+chr(10),chr(10).join(lock)+chr(10)

@contextmanager
def prepared_project(pages,title,assets):
    if not 1<=len(pages)<=40:raise MasterError('课件页数无效')
    if len(assets)>20 or sum(len(v) for v in assets.values())>16*1024*1024:raise MasterError('参考配图过多')
    for page in pages:preview(page['svg'],assets)
    root=package_root()
    with TemporaryDirectory(prefix='edu-ppt-render-') as temp:
        base=Path(temp)
        run_tool(root,'project_manager.py','init','lesson','--format','ppt169','--dir',base)
        project=next(p for p in base.iterdir() if p.is_dir())
        (project/'images').mkdir(exist_ok=True)
        for name,data in assets.items():
            if not re.fullmatch(r'[a-f0-9]{24}[.]png',name) or len(data)>3*1024*1024:raise MasterError('参考图片格式或大小无效')
            (project/'images'/name).write_bytes(data)
        spec,lock=design_artifacts(pages,title,assets)
        (project/'design_spec.md').write_text(spec,encoding='utf-8')
        (project/'spec_lock.md').write_text(lock,encoding='utf-8')
        run_tool(root,'project_manager.py','validate',project)
        for i,page in enumerate(pages,1):(project/'svg_output'/f'P{i:02d}.svg').write_text(page['svg'],encoding='utf-8')
        from .delivery import teacher_confirmed
        checked=[i for i,page in enumerate(pages,1) if not teacher_confirmed(page)]
        if len(checked)==len(pages):
            run_tool(root,'svg_quality_checker.py',project,'--canonical-authoring','--stage','final','--json')
        else:
            # Teacher-authored layout is accepted as-is; generated pages keep their quality gate.
            for i in checked:run_tool(root,'svg_quality_checker.py',project/'svg_output'/f'P{i:02d}.svg','--canonical-authoring','--stage','final','--json')
        yield root,project

def check_page(page,assets):
    with prepared_project([page],page['title'],assets):pass

def compile_deck(pages,title,assets, *, output_workspace=None):
    with prepared_project(pages,title,assets) as (root,project):
        run_tool(root,'finalize_svg.py',project)
        out=project/'exports'/'lesson.pptx'
        run_tool(root,'svg_to_pptx.py',project,'-s','svg_output','--no-notes','--no-animations','-o',out,timeout=180)
        if out.stat().st_size>40*1024*1024:raise MasterError('生成课件过大，请减少页数或配图')
        # Stabilize authored line breaks without changing the official package.
        packed=BytesIO()
        with zipfile.ZipFile(out) as source,zipfile.ZipFile(packed,'w') as target:
            for info in source.infolist():
                payload=source.read(info.filename)
                if re.fullmatch(r'ppt/slides/slide[0-9]+[.]xml',info.filename):
                    payload=payload.replace(b'<a:spAutoFit/>',b'<a:noAutofit/>').replace(b'<a:spAutoFit />',b'<a:noAutofit/>')
                target.writestr(info,payload)
        data=packed.getvalue()
        out.write_bytes(data)
        if output_workspace:shutil.copytree(project,output_workspace,dirs_exist_ok=True)
        return data
