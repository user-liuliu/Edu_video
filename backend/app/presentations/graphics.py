"""Deterministic trusted graphics; only JSON crosses the browser boundary."""
import asyncio
import base64
from hashlib import sha256
from io import BytesIO
import json
import time
from xml.sax.saxutils import escape
import httpx
from PIL import Image
from .graphic_contract import GraphicSpec,VERSION,LEGACY_VERSION,WIDTH,HEIGHT,MAX_PNG
from .master_runtime import MasterError
from app.http_client import create_http


def canonical(source):return json.dumps(GraphicSpec.model_validate(source).model_dump(),ensure_ascii=False,sort_keys=True,separators=(',',':'))


def graphic_descriptor(source,data,labels,*,version=VERSION):
    source=json.loads(canonical(source))
    with Image.open(BytesIO(data)) as image:
        if image.format!='PNG' or image.width*image.height>WIDTH*HEIGHT*4:raise MasterError('信息图图片格式或大小无效')
    if len(data)>MAX_PNG:raise MasterError('信息图图片过大')
    if not isinstance(labels,list) or not 2<=len(labels)<=60:raise MasterError('信息图标签无效')
    import math
    for label in labels:
        if set(label)!= {'text','x','y','size','color','anchor'}:raise MasterError('信息图标签格式无效')
        if not isinstance(label['text'],str) or len(label['text'])>36:raise MasterError('信息图标签文字无效')
        for key,upper in [('x',WIDTH),('y',HEIGHT)]:
            if type(label[key]) not in (int,float) or not math.isfinite(label[key]) or not 0<=label[key]<=upper:raise MasterError('信息图标签越界')
        if label['size'] not in (22,28,32) or label['color'] not in ('#173359','#61738A','#2465D9','#2B9578') or label['anchor'] not in ('start','middle'):raise MasterError('信息图标签样式无效')
    name=sha256((version+canonical(source)).encode()).hexdigest()[:24]+'.png'
    return {'version':version,'source':source,'sha256':sha256(data).hexdigest(),'name':name,'width':WIDTH,'height':HEIGHT,'labels':labels}


async def materialize(source,settings,*,version=VERSION):
    source=json.loads(canonical(source))
    url=(getattr(settings,'ppt_renderer_url','') or settings.renderer_url).rstrip('/')
    if not url:raise MasterError('信息图渲染服务未配置，请联系管理员')
    async with create_http() as http:
        deadline=time.monotonic()+120
        while True:
            try:
                async with http.stream('POST',url+'/ppt-graphic',json={'version':version,'source':source},timeout=45,follow_redirects=False) as response:
                    if response.status_code in (429,503):
                        if time.monotonic()>=deadline:raise MasterError('信息图渲染服务忙，请稍后重试')
                    elif response.is_success:
                        body=bytearray()
                        async for chunk in response.aiter_bytes():
                            body.extend(chunk)
                            if len(body)>MAX_PNG*1.4+30000:raise MasterError('信息图渲染输出过大')
                        value=json.loads(body)
                        if value.get('version')!=version:raise MasterError('信息图渲染版本不一致，请更新服务')
                        data=base64.b64decode(value['png_base64'],validate=True)
                        descriptor=graphic_descriptor(source,data,value['labels'],version=version)
                        with Image.open(BytesIO(data)) as image:
                            if image.size!=(WIDTH*2,HEIGHT*2):raise MasterError('信息图渲染分辨率无效')
                        return data,descriptor
                    else:raise MasterError('信息图渲染失败，请联系管理员检查渲染服务版本')
            except (httpx.HTTPError,ValueError,KeyError,TypeError,OSError) as exc:
                if isinstance(exc,MasterError):raise
                raise MasterError('信息图渲染服务连接失败或返回无效数据，请重试') from exc
            await asyncio.sleep(2)


def text(x,y,value,size=28,color='#173359',anchor='start'):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" text-anchor="{anchor}">{escape(value)}</text>'


def compose_page(slide,design,graphic):
    # Server-authored layout reserves a stable rectangle for trusted graphics.
    from .text_layout import wrap_text
    title=slide['title'];lines=wrap_text(title,22)
    if len(lines)>2:raise MasterError('信息图页面标题过长，请缩短到44字以内')
    headings=''.join(text(64,88+i*58,line,48) for i,line in enumerate(lines))
    content_lines=wrap_text(''.join(slide['content'].splitlines()),50)
    if len(content_lines)>2:raise MasterError('信息图页面说明过长，请精简至两行可读内容后重试')
    subtitle=''.join(text(64,190+i*32,line,22,'#61738A') for i,line in enumerate(content_lines))
    labels=''.join(text(round(90+l['x'],2),round(240+l['y'],2),l['text'],l['size'],l['color'],l['anchor']) for l in graphic['labels'])
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720" font-family="Microsoft YaHei, Arial" data-pptx-page-role="content"><rect id="background" data-pptx-role="background" width="1280" height="720" fill="#FFFFFF"/><g id="heading" data-pptx-bounds="64 36 1152 124">{headings}</g><g id="explanation" data-pptx-bounds="64 164 1152 72">{subtitle}</g><g id="teaching-visual" data-pptx-bounds="90 240 1100 400"><image href="../images/{graphic["name"]}" x="90" y="240" width="1100" height="400"/>{labels}</g></svg>'
    from .master_runtime import VERSION as MASTER_VERSION
    return {**slide,'slots':{},'renderer':MASTER_VERSION,'svg':svg,'design':design,'graphics':[graphic]}


async def generated_assets(pages,settings,needed=None):
    assets={}
    for page in pages:
        for descriptor in page.get('graphics',[]):
            if needed is not None and descriptor.get('name') not in needed:continue
            if descriptor.get('version') not in (VERSION,LEGACY_VERSION):raise MasterError('信息图版本不一致，请重新生成课件')
            name=descriptor['name']
            if name in assets:continue
            data,actual=await materialize(descriptor['source'],settings,version=descriptor['version'])
            if actual!=descriptor:raise MasterError('信息图内容已变化，请重新生成课件')
            assets[name]=data
            if len(assets)>20 or sum(map(len,assets.values()))>16*1024**2:raise MasterError('信息图最多20张，累计不能超过16MiB')
    return assets
