"""Trusted HTML/AntV rendering. The model supplies data, never executable markup."""
import asyncio
from hashlib import sha256
import json
import os
import tempfile
from pathlib import Path
from app.presentations.graphic_contract import GraphicSpec,VERSION,LEGACY_VERSION,WIDTH,HEIGHT,MAX_PNG
from .resources import limit_cpu_affinity

VENDOR=Path(__file__).parent/'vendor'/'antv'


def motif(kind,cx,cy,index,*,version=VERSION):
    """Small curated SVG vocabulary for clear school science diagrams."""
    if kind in ('leaf','leaf-shade','leaf-result'):
        color='url(#leaf)' if kind!='leaf-result' else 'url(#starch)'
        band='<path d="M-23-93 L17-96 L48 78 L8 88 Z" fill="#223C59"/>' if kind=='leaf-shade' else '<path d="M-23-93 L17-96 L48 78 L8 88 Z" fill="#F2E7CA"/>' if kind=='leaf-result' else ''
        if kind=='leaf-result' and version!=LEGACY_VERSION:
            leaf='M-88 80 C-117-55 -5-125 88-91 C117 24 11 116-88 80Z'
            band=f'<defs><clipPath id="result-clip-{index}"><path d="{leaf}"/></clipPath></defs><g clip-path="url(#result-clip-{index})">{band}</g>'
        body=f'<path d="M-88 80 C-117-55 -5-125 88-91 C117 24 11 116-88 80Z" fill="{color}" stroke="#2D8D77" stroke-width="2.5"/><path d="M-108 103 L66-68 M-60 58 L-65-2 M-27 28 L-35-40 M7-4 L-2-65 M-60 58 L1 67 M-26 28 L41 36 M7-4 L66 0" fill="none" stroke="#7BC5A6" stroke-width="2"/>{band}'
    elif kind=='beaker':
        body='<path d="M-95-25 V82 Q-95 95-82 95 H82 Q95 95 95 82 V-25" fill="#E4F3FC" stroke="#4B7B9B" stroke-width="3"/><path d="M-91 25 H91 V82 Q91 91 78 91 H-78 Q-91 91-91 78Z" fill="#AEDCEF"/><path d="M-48-93 V44 Q-48 65-27 65 H27 Q48 65 48 44 V-93" fill="#F9FCFF" stroke="#3468B0" stroke-width="3"/><path d="M-44-2 H44 V43 Q44 61 26 61 H-26 Q-44 61-44 43Z" fill="#CEE4A4"/><path d="M-31 14 Q-13-38 4-50 Q43-5 28 39 Q-5 53-31 14Z" fill="#B8CE87" stroke="#93AC64" stroke-width="2"/><path d="M-68-52 Q-85-65-68-78 M0 112 Q12 102 23 112" stroke="#8BAABE" stroke-width="2" fill="none"/><circle cx="-68" cy="55" r="4" fill="#DBF3FC"/><circle cx="69" cy="42" r="5" fill="#DBF3FC"/>'
    elif kind=='sun':
        body='<circle r="57" fill="url(#sun)"/>'+''.join(f'<path d="M0-72 V-91" transform="rotate({a})" stroke="#F3BF49" stroke-width="4" stroke-linecap="round"/>' for a in range(0,360,45))
    elif kind=='cell':
        body='<path d="M-98-20 Q-100-91-18-92 Q94-97 99-6 Q104 85 15 89 Q-102 99-98-20Z" fill="#E5F5EC" stroke="#279979" stroke-width="3"/><ellipse cx="13" cy="-5" rx="34" ry="30" fill="#D7D9F4" stroke="#9494C8" stroke-width="2"/><circle cx="21" cy="-5" r="11" fill="#AFB4DC"/><ellipse cx="-53" cy="-39" rx="23" ry="12" fill="#90CEAB" transform="rotate(-25)"/><ellipse cx="48" cy="48" rx="23" ry="12" fill="#90CEAB" transform="rotate(-25)"/>'
    elif kind=='none':
        body=''
    else:
        body='<circle r="67" fill="#EAF1FF"/><circle r="49" fill="#D7E5FF"/><path d="M12-67 L-34 5 H-2 L-12 68 L37-10 H5Z" fill="#E7B84D" stroke="#D4A237" stroke-width="2"/>'
    return f'<g transform="translate({cx} {cy})">{body}</g>'


def document(source,*,version=VERSION):
    spec=GraphicSpec.model_validate(source)
    count=len(spec.items);gap=WIDTH/count
    labels=[];drawings=[]
    for n,item in enumerate(spec.items):
        cx=gap*(n+.5)
        drawings.append(motif(item.motif,cx,122,n,version=version))
        labels.append({'text':item.label,'x':cx,'y':291,'size':28,'color':'#173359','anchor':'middle'})
        # Wrap in native text using conservative CJK widths, no browser text rasterization.
        width=max(10,int((gap-38)/22))
        if version==LEGACY_VERSION:
            lines=[item.desc[line:line+width] for line in range(0,len(item.desc),width)]
        else:
            from app.presentations.text_layout import wrap_text
            lines=wrap_text(item.desc,width)
        first_y,line_gap=(315,26) if len(lines)>3 else (335,29)
        for nline,line in enumerate(lines):
            labels.append({'text':line,'x':cx,'y':first_y+nline*line_gap,'size':22,'color':'#61738A','anchor':'middle'})
    options={'container':'#flow','width':WIDTH,'height':80,'padding':0,'editable':False,
        'template':'list-row-simple-horizontal-arrow' if spec.kind=='process' else 'compare-binary-horizontal-simple-vs',
        'data':{'items':[{'label':' ','desc':' '} for _ in spec.items]},
        'themeConfig':{'colorPrimary':'#3276C8','colorBg':'#FFFFFF','palette':['#C7DDF2','#B8DDCF','#D8DAED','#EEDFAE']},'svg':{'background':False}}
    options_json=json.dumps(options,ensure_ascii=True).replace('<','\\u003c')
    svg='<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="400"><defs><linearGradient id="leaf" x1="0" x2="1" y1="0" y2="1"><stop stop-color="#DBF2D7"/><stop offset="1" stop-color="#66B591"/></linearGradient><linearGradient id="starch" x1="0" x2="1" y1="0" y2="1"><stop stop-color="#28495D"/><stop offset="1" stop-color="#17364C"/></linearGradient><radialGradient id="sun"><stop stop-color="#FFE6A0"/><stop offset="1" stop-color="#F6C954"/></radialGradient></defs>'+''.join(drawings)+'</svg>'
    html='<!doctype html><meta charset="utf-8"><style>*{box-sizing:border-box}html,body{margin:0;background:transparent;width:1100px;height:400px;overflow:hidden}#flow{position:absolute;top:210px;left:0;width:1100px;height:80px}#motifs{position:absolute;inset:0;pointer-events:none}#flow text{visibility:hidden}</style><div id="flow"></div><div id="motifs">'+svg+'</div><script>window.GRAPHIC_OPTIONS='+options_json+';</script>'
    if spec.kind=='compare' and version!=LEGACY_VERSION:html=html.replace('</style>','#flow{display:none}</style>')
    return html,labels


async def render_graphic(source,*,version=VERSION):
    limit_cpu_affinity()
    source=GraphicSpec.model_validate(source).model_dump()
    manifest=json.loads((VENDOR/'manifest.json').read_text())
    bundle=(VENDOR/'infographic.min.js').read_bytes()
    if sha256(bundle).hexdigest()!=manifest['bundle_sha256']:raise ValueError('graphic runtime integrity failure')
    html,labels=document(source,version=version)
    with tempfile.TemporaryDirectory(prefix='edu-graphic-home-') as home_dir:
        return await _render(html,labels,bundle,home_dir)

async def _render(html,labels,bundle,home_dir):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser=await p.chromium.launch(executable_path=os.environ.get('EV_RENDER_EXECUTABLE','/usr/bin/chromium'),headless=True,env={**os.environ,'HOME':home_dir,'XDG_CONFIG_HOME':home_dir,'XDG_CACHE_HOME':home_dir},args=['--no-sandbox','--disable-dev-shm-usage','--disable-background-networking','--disable-extensions'])
        try:
            context=await browser.new_context(viewport={'width':WIDTH,'height':HEIGHT},device_scale_factor=2,service_workers='block')
            await context.route('**/*',lambda route:route.abort())
            page=await context.new_page();errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            await page.set_content(html,wait_until='domcontentloaded')
            await page.add_script_tag(content=bundle.decode('utf-8'))
            await page.evaluate('''() => {const graphic = new AntVInfographic.Infographic(window.GRAPHIC_OPTIONS); graphic.render(); window.eduGraphic=graphic;}''')
            await page.wait_for_selector('#flow svg',state='attached',timeout=10000)
            await page.evaluate('document.fonts.ready')
            await page.evaluate('''() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))''')
            if errors:raise ValueError('graphic runtime failed')
            if await page.locator('#flow svg path,#flow svg rect,#flow svg circle').count()<1:raise ValueError('empty infographic')
            data=await page.screenshot(type='png',omit_background=True,animations='disabled')
            if len(data)>MAX_PNG:raise ValueError('graphic too large')
            return data,labels
        finally:await browser.close()
