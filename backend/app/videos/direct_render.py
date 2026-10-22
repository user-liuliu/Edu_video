"""Render the same sealed document used by the teacher player."""
import asyncio
import base64
import io
import math
import os
from pathlib import Path
import subprocess
import tempfile
from contextlib import asynccontextmanager
from .direct_html import seal_html
from .export import executable
from .render_contract import DirectHtmlRuntimeError


@asynccontextmanager
async def film_page(request):
    from playwright.async_api import async_playwright
    async with async_playwright() as playwright:
        browser=await playwright.chromium.launch(headless=True,
            channel=os.environ.get('EV_RENDER_BROWSER','msedge') if os.name=='nt' else None,
            executable_path=os.environ.get('EV_RENDER_EXECUTABLE') or None)
        try:
            context=await browser.new_context(viewport={'width':request.width,'height':request.height},service_workers='block')
            await context.route('**/*',lambda route:route.abort())
            page=await context.new_page();errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.set_default_timeout(15000)
            await page.set_content(seal_html(request.html,request.manifest,(request.width,request.height)),wait_until='load')
            await page.evaluate('window.sceneReady')
            yield page,errors
        finally:await browser.close()


async def inspect(page,t):
    await page.evaluate('(t)=>window.seek(t,true)',t)
    return await page.evaluate('window.lastSceneDom')


async def pixels(page):
    import numpy as np
    from PIL import Image
    image=Image.open(io.BytesIO(await page.screenshot(type='png',animations='allow'))).convert('RGB')
    return np.asarray(image.resize((640,360))).astype('int16')


def same_pixels(first,second):
    import numpy as np
    delta=np.abs(first-second)
    # Allow tiny raster/antialias variation, never cumulative drawing changes.
    return float(delta.mean())<=.2 and float((delta.max(axis=2)>24).mean())<=.001


async def check_continuous_boundaries(page):
    """Compare the actual visible source frames, independent of audio retiming.

    Captions live outside the scene iframe and deliberately are not compared.
    This is a technical seam guard, not a semantic/content audit.
    """
    frame=page.frames[1] if len(page.frames)>1 else None
    if frame is None:return
    spec=await frame.evaluate("""()=>{const el=document.getElementById('edu-film-bundle');
        if(!el)return null;const bundle=JSON.parse(el.textContent);
        return bundle.transitions.map((tr,i)=>({mode:tr.mode,from_id:tr.from_id,to_id:tr.to_id}));}""")
    if not spec or not any(item.get('mode')=='continuous' for item in spec):return
    # The compiler publishes immutable time ranges in its JSON metadata.
    timeline=await frame.evaluate("JSON.parse(document.getElementById('edu-film-timeline').textContent)")
    import numpy as np
    from PIL import Image
    async def source_pixels(t):
        await frame.evaluate('(t)=>window.renderFrame(t)',t)
        image=Image.open(io.BytesIO(await page.locator('#film').screenshot(type='png',animations='allow'))).convert('RGB')
        return np.asarray(image.resize((640,360))).astype('int16')
    for index,item in enumerate(spec):
        if item.get('mode')!='continuous':continue
        boundary=timeline[index]['end']
        before=await source_pixels(boundary-0.000001)
        after=await source_pixels(boundary)
        if not same_pixels(before,after):
            delta=np.abs(before-after)
            raise ValueError(f"连续场景 {item['from_id']} → {item['to_id']} 边界画面不一致（平均差异{delta.mean():.2f}）；保持背景、坐标、主体和标注末态，变化放在段内，不要用淡化隐藏跳变")


async def check_page(page,errors,duration):
    await check_continuous_boundaries(page)
    # Sparse whole-film checks plus reverse and frozen-clock checks. Encoding
    # subsequently visits every frame, and never calls a content-review model.
    times=sorted({0.,duration, duration*.25,duration*.5,duration*.75,*[min(duration,float(i)) for i in range(0,math.ceil(duration),max(1,math.ceil(duration/90)))]})
    frozen={};frames={}
    for t in times:
        frozen[t]=await inspect(page,t)
        frames[t]=await pixels(page)
    for t in reversed(times):
        if await inspect(page,t)!=frozen[t]:raise ValueError('动画不能确定性地倒退定位')
        if not same_pixels(frames[t],await pixels(page)):
            raise ValueError('动画画面依赖累计状态，不能确定性地倒退定位')
    t=duration*.5;await inspect(page,t)
    before=await pixels(page)
    await page.wait_for_timeout(120)
    frame=page.frames[1] if len(page.frames)>1 else None
    if frame is None or await frame.evaluate('window.__eduSceneDom()')!=frozen[t]:
        raise ValueError('动画存在未冻结的自主播放状态')
    if not same_pixels(before,await pixels(page)):
        raise ValueError('动画画面存在未冻结的自主播放状态')
    if not await frame.evaluate('!document.querySelector(\'[data-edu-characters-required="true"]\') || (window.EduSprites?.usage().drawnCharacters > 0)'):
        raise ValueError('故事动画未使用提供的人物素材；请使用EduSprites.drawActor绘制完整人物，缺少角色时选择目录中的近似人物，科学图形保持清晰')
    if errors or await page.evaluate('window.filmDiagnostics.length'):raise ValueError('整片动画运行失败')


async def validate_direct(request):
    from playwright.async_api import Error as BrowserError
    try:
        async with film_page(request) as (page,errors):
            await check_page(page,errors,request.manifest['duration'])
    except (BrowserError,ValueError) as error:
        raise DirectHtmlRuntimeError(str(error)[:500]) from None
    return {'validated':True}


async def render_direct(request,output):
    duration=request.manifest['duration'];output=Path(output)
    with tempfile.TemporaryDirectory(prefix='ev-direct-') as folder:
        audio=Path(folder)/'audio.wav';audio.write_bytes(base64.b64decode(request.audio_base64))
        credits=[]
        if '<!-- EDU-SPRITES ' in request.html:
            from .sprite_assets import export_metadata
            for key,value in export_metadata(request.html).items():
                credits.extend(['-metadata',key+'='+value])
        command=[executable('ffmpeg'),'-y','-hide_banner','-loglevel','error','-f','image2pipe','-vcodec','png','-r',str(request.fps),'-i','-','-i',str(audio),'-map','0:v:0','-map','1:a:0','-t',str(duration),'-c:v','libx264','-preset','fast','-crf','21','-pix_fmt','yuv420p','-c:a','aac',*credits,'-movflags','+faststart',str(output)]
        with open(Path(folder)/'encoder.log','wb') as log:
            process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=log)
            try:
                async with film_page(request) as (page,errors):
                    await check_page(page,errors,duration)
                    for frame in range(math.ceil(duration*request.fps)):
                        await page.evaluate('(t)=>window.seek(t)',frame/request.fps)
                        data=await page.screenshot(type='png',animations='allow')
                        if errors or await page.evaluate('window.filmDiagnostics.length'):raise ValueError('动画运行异常，无法导出')
                        await asyncio.to_thread(process.stdin.write,data)
                process.stdin.close()
                if await asyncio.to_thread(process.wait,60):raise ValueError('整片视频编码失败')
            finally:
                if process.poll() is None:process.kill();process.wait()
                if process.stdin and not process.stdin.closed:process.stdin.close()
        from .export import decode_check,probe
        await asyncio.to_thread(decode_check,output)
        return await asyncio.to_thread(probe,output,(request.width,request.height))
