"""Compile generated classic scripts before executing the sealed film.

Kept outside the sealed runtime digest: validation does not alter a film or
invalidate previously accepted previews. Chromium compiles without executing.
"""
import os
from html.parser import HTMLParser
from .direct_render import validate_direct as _validate_direct, render_direct as _render_direct
from .render_contract import DirectHtmlRuntimeError


class Scripts(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=False)
        self.scripts=[]
        self.current=None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag!='script':return
        attrs=dict(attrs)
        kind=(attrs.get('type') or '').strip().lower().split(';')[0]
        if kind and kind not in ('text/javascript','application/javascript','text/ecmascript','application/ecmascript'):
            return
        self.current={'parts':[], 'line':self.getpos()[0]+self.get_starttag_text().count('\n')}

    def handle_data(self, data):
        if self.current is not None:self.current['parts'].append(data)

    def handle_endtag(self, tag):
        if tag=='script' and self.current is not None:
            self.scripts.append(self.current)
            self.current=None


async def check_syntax(html):
    from playwright.async_api import async_playwright
    scripts=Scripts(html).scripts
    if not scripts:return
    async with async_playwright() as playwright:
        browser=await playwright.chromium.launch(headless=True,
            channel=os.environ.get('EV_RENDER_BROWSER','msedge') if os.name=='nt' else None,
            executable_path=os.environ.get('EV_RENDER_EXECUTABLE') or None)
        try:
            context=await browser.new_context(service_workers='block')
            await context.route('**/*',lambda route:route.abort())
            page=await context.new_page()
            session=await context.new_cdp_session(page)
            await session.send('Runtime.enable')
            for index,script in enumerate(scripts,1):
                source=''.join(script['parts'])
                result=await session.send('Runtime.compileScript',{'expression':source,
                    'sourceURL':f'animation-script-{index}.js','persistScript':False})
                error=result.get('exceptionDetails')
                if error:
                    description=error.get('exception',{}).get('description') or error.get('text','SyntaxError')
                    description=description.split('\n')[0][:180]
                    line=error.get('lineNumber',0);column=error.get('columnNumber',0)
                    lines=source.split('\n')
                    excerpt=lines[min(line,len(lines)-1)][max(0,column-70):column+100]
                    raise DirectHtmlRuntimeError(
                        f'动画脚本语法错误：JavaScript {description} (script {index}, line {line+1}, column {column+1}; '
                        f'HTML line {script["line"]+line}). Context: {excerpt}'[:500])
        finally:await browser.close()


async def check_visible_frames(request):
    """Reject fully blank scene layers; captions cannot count as scene content."""
    import io
    import numpy as np
    from PIL import Image
    from .direct_render import film_page, inspect
    async with film_page(request) as (page, errors):
        frame=page.frames[1]
        timeline=await frame.evaluate("""()=>{const el=document.getElementById('edu-film-timeline');
            return el?JSON.parse(el.textContent):null;}""")
        ranges=timeline or [{'id':'film','start':0.,'end':request.manifest['duration']}]
        for item in ranges:
            visible=False
            for fraction in (.5,.25,.75):
                t=item['start']+(item['end']-item['start'])*fraction
                if timeline:
                    await frame.evaluate('(t)=>window.renderFrame(t)',t)
                else:
                    await inspect(page,t)
                data=await page.locator('#film').screenshot(type='png',animations='allow')
                image=Image.open(io.BytesIO(data)).convert('RGB')
                # Scene canvas is always 1280x720; the bottom is reserved for captions.
                image=image.crop((0,0,image.width,round(image.height*625/720)))
                rgb=np.asarray(image.resize((640,312))).astype('int16')
                background=np.median(rgb.reshape(-1,3),axis=0)
                detail=(np.abs(rgb-background).max(axis=2)>18).mean()
                if detail>.0001:
                    visible=True
                    break
            if not visible:
                raise DirectHtmlRuntimeError(
                    f"片段 {item['id']} 画面为空或画面被遮挡；请检查背景与 Canvas/SVG 的层级，"
                    '保证实际绘图在背景之上。背景请使用容器背景或明确的底层，绘图层正确定位；字幕不算可见画面。')
        if errors:
            raise DirectHtmlRuntimeError('整片动画运行失败')


async def validate_direct(request):
    await check_syntax(request.html)
    result=await _validate_direct(request)
    await check_visible_frames(request)
    return result


async def render_direct(request, output):
    await check_syntax(request.html)
    await check_visible_frames(request)
    return await _render_direct(request,output)
