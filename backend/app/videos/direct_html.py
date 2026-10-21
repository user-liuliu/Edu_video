"""Whole-film HTML contract. Isolation, not static filtering, is the boundary."""
import hashlib
import io
import json
import math
import re
import wave
from html.parser import HTMLParser
from pathlib import Path

DIRECT_PROTOCOL = 'direct-html-film-1'
MAX_HTML_BYTES = 1_500_000
MAX_AUDIO_BYTES = 140 * 1024 * 1024
POLICY = "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; font-src 'none'; connect-src 'none'; media-src 'none'; object-src 'none'; frame-src 'none'; base-uri 'none'; form-action 'none'"


def validate_html(value):
    if not isinstance(value, str) or not 80 < len(value.encode()) <= MAX_HTML_BYTES:
        raise ValueError('整片HTML大小无效')
    if not re.search(r'<html\b', value, re.I) or not re.search(r'\brenderFrame\b', value):
        raise ValueError('动画缺少完整HTML或renderFrame接口')
    class Check(HTMLParser):
        def handle_starttag(self, tag, attrs):
            if tag in ('iframe','object','embed','base','form','link','audio','video'):
                raise ValueError('动画包含不支持的外部或嵌入内容')
            for key, content in attrs:
                content = content or ''
                if key.startswith('on') or key in ('srcdoc','action','formaction') or (key in ('src','href','xlink:href') and not content.startswith(('#','data:image/'))):
                    raise ValueError('动画包含外部资源或不支持的事件')
                if key == 'http-equiv':
                    raise ValueError('动画不能修改页面策略或导航')
        handle_startendtag = handle_starttag
    Check().feed(value)
    forbidden = (r'\b(?:fetch|XMLHttpRequest|WebSocket|EventSource|eval|setInterval|setTimeout|requestAnimationFrame)\s*\(',
                 r'\bnew\s+Function\b', r'\b(?:window\s*\.\s*)?(?:parent|top|opener)\s*\.\s*(?:location|document|postMessage|frames|eval)\b',
                 r'\b(?:localStorage|sessionStorage|indexedDB|serviceWorker)\b',
                 r'\bimport\s*(?:\(|["\'])', r'@import\b', r'url\(\s*["\']?(?!#|data:image/)',
                 r'\b(?:Date|performance)\s*\.\s*now\s*\(', r'\bMath\s*\.\s*random\s*\(')
    if any(re.search(pattern, value, re.I) for pattern in forbidden):
        raise ValueError('动画包含外联、自主时钟或动态执行代码')
    return value


def direct_digest():
    root = Path(__file__).parent
    from .sprite_assets import load_bundle
    _,_,sprite_digest=load_bundle()
    return hashlib.sha256(b''.join((root / name).read_bytes() for name in ('direct_html.py','direct_runtime.js','direct_prompt.txt','direct_render.py','sprite_assets.py','sprite_motion.js'))+sprite_digest.encode()).hexdigest()


def validate_manifest(manifest):
    duration, source = manifest['duration'], manifest['source_duration']
    if not all(isinstance(x,(int,float)) and math.isfinite(x) and 0 < x <= 7200 for x in (duration,source)):
        raise ValueError('整片时长无效')
    clock = manifest['clock']
    if not 2 <= len(clock) <= 40000 or clock[0] != {'t':0.,'source':0.} or clock[-1] != {'t':duration,'source':source}:
        raise ValueError('整片时钟端点无效')
    if any(not all(isinstance(v,(int,float)) and math.isfinite(v) for v in (p['t'],p['source'])) for p in clock):
        raise ValueError('整片时钟无效')
    if any(a['t'] >= b['t'] or a['source'] > b['source'] for a,b in zip(clock,clock[1:])):
        raise ValueError('整片时钟必须连续单调')
    previous = 0.
    if len(manifest['captions']) > 10000: raise ValueError('字幕过多')
    for caption in manifest['captions']:
        a,b = caption['start'],caption['end']
        if not all(isinstance(x,(int,float)) and math.isfinite(x) for x in (a,b)) or not previous <= a < b <= duration+.00001 or not isinstance(caption['text'],str) or not caption['text'].strip() or len(caption['text'])>2000:
            raise ValueError('整片字幕无效')
        previous = b


def seal_html(html, manifest, dimensions):
    validate_html(html); validate_manifest(manifest)
    width,height = dimensions
    if not all(isinstance(x,int) and 240<=x<=1920 and x%2==0 for x in dimensions): raise ValueError('画布尺寸无效')
    meta = '<meta http-equiv="Content-Security-Policy" content="'+POLICY+'">'
    if re.search(r'<head\b[^>]*>',html,re.I):
        inner = re.sub(r'(<head\b[^>]*>)',lambda m:m[0]+meta,html,count=1,flags=re.I)
    else:
        inner = re.sub(r'(<html\b[^>]*>)',lambda m:m[0]+'<head>'+meta+'</head>',html,count=1,flags=re.I)
    payload = json.dumps({'html':inner,**manifest,'width':width,'height':height,'protocol':DIRECT_PROTOCOL},ensure_ascii=False,separators=(',',':'),sort_keys=True)
    payload = payload.replace('&','\\u0026').replace('<','\\u003c').replace('>','\\u003e')
    runtime = Path(__file__).with_name('direct_runtime.js').read_text(encoding='utf-8')
    return '<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; script-src \'unsafe-inline\'; style-src \'unsafe-inline\'; frame-src about:; connect-src \'none\'; img-src data:;"><style>html,body{margin:0;width:100%;height:100%;overflow:hidden;background:#f6f2e9}#stage{position:absolute;left:50%;top:50%;transform-origin:center}#film{width:1280px;height:720px;border:0}#caption{position:absolute;left:40px;right:40px;bottom:24px;padding:12px 20px;border-radius:9px;background:rgba(45,38,32,.88);color:white;text-align:center;font:23px/1.4 "Noto Sans CJK SC","Microsoft YaHei",sans-serif;pointer-events:none;box-sizing:border-box}#caption:empty{display:none}</style></head><body><div id="stage"><iframe id="film" sandbox="allow-scripts" referrerpolicy="no-referrer"></iframe><div id="caption"></div></div><script id="payload" type="application/json">'+payload+'</script><script>'+runtime+'</script></body></html>'


def align_clock(cues, captions, source_duration, duration):
    from .timing import spoken
    if not cues or not captions or spoken(''.join(c['text'] for c in cues)) != spoken(''.join(c['text'] for c in captions)):
        raise ValueError('配音与动画讲稿不一致，不能校准时间')
    def spans(items, maximum):
        result=[];offset=0;last=0.
        for item in items:
            a,b=item['start'],item['end'];n=len(spoken(item['text']))
            if not n or not all(math.isfinite(t) for t in (a,b)) or not last<=a<b<=maximum+.05:
                raise ValueError('讲稿时间轴无效')
            b=min(b,maximum)
            if a>=b: raise ValueError('字幕超出音轨')
            result.append((offset,offset+n,a,b));offset+=n;last=b
        return result
    source=spans(cues,source_duration); actual=spans(captions,duration)
    def at(offset,side):
        for a,b,start,end in source:
            if a<offset<b:return start+(end-start)*(offset-a)/(b-a)
            if offset==a and side=='start':return start
            if offset==b and side=='end':return end
        return source[0][2] if offset==0 else source[-1][3]
    pairs=[(0.,0.),(duration,source_duration)]
    for a,b,start,end in actual:pairs.extend(((start,at(a,'start')),(end,at(b,'end'))))
    groups=[]
    for t,x in sorted(pairs):
        if groups and groups[-1][0]==t:groups[-1][1].append(x)
        else:groups.append([t,[x]])
    points=[]
    for i,(t,values) in enumerate(groups):
        lo,hi=min(values),max(values)
        if lo==hi:points.append({'t':t,'source':lo});continue
        before=min(1/60,(t-groups[i-1][0])/4) if i else 0
        after=min(1/60,(groups[i+1][0]-t)/4) if i+1<len(groups) else 0
        points.extend(({'t':t-before,'source':lo},{'t':t+after,'source':hi}))
    validate_manifest({'duration':duration,'source_duration':source_duration,'clock':points,'captions':captions})
    return points


def join_audio(parts):
    output=io.BytesIO();expected=None;total=0
    with wave.open(output,'wb') as target:
        for data in parts:
            with wave.open(io.BytesIO(data),'rb') as source:
                signature=(source.getnchannels(),source.getsampwidth(),source.getframerate(),source.getcomptype())
                if signature[3]!='NONE' or not source.getnframes():raise ValueError('配音不是有效PCM')
                if expected is None:
                    expected=signature;target.setparams(source.getparams())
                if signature!=expected:raise ValueError('片段配音格式不一致，请重新生成配音')
                pcm=source.readframes(source.getnframes());total+=len(pcm)
                if total>MAX_AUDIO_BYTES:raise ValueError('整片配音过大，请缩短大纲')
                target.writeframesraw(pcm)
        if expected is None:raise ValueError('整片缺少配音')
    return output.getvalue()


async def generate_html(config, request, http, *, feedback=''):
    import httpx
    from .model_stream import animation_response
    from app.outline.model_client import ModelCallError
    if request.get('previous_html'):
        from .sprite_assets import model_source
        request={**request,'previous_html':model_source(request['previous_html'])}
    messages=[{'role':'system','content':Path(__file__).with_name('direct_prompt.txt').read_text(encoding='utf-8')},
              {'role':'user','content':json.dumps(request,ensure_ascii=False)}]
    if feedback:messages.append({'role':'user','content':'技术运行检查未通过，仅修复代码，保留讲稿和教学内容：'+feedback[:800]})
    url=config.base_url.rstrip('/')
    if not url.endswith('/chat/completions'):url+='/chat/completions'
    for attempt in range(2):
        try:
            response=await animation_response(http,url,{'Authorization':'Bearer '+config.api_key},
                {'model':config.model,'messages':messages,'response_format':{'type':'json_object'},'stream':True,'max_tokens':18000})
            if not response.is_success:
                from app.outline.model_client import _http_failure
                raise _http_failure(response)
            from .sprite_assets import assemble_sprites
            source=validate_html(json.loads(response.json()['choices'][0]['message']['content'])['html'])
            library=request.get('sprite_library') or {}
            return validate_html(assemble_sprites(source,enabled=bool(library),
                required=bool(library.get('character_policy',{}).get('required'))))
        except ModelCallError:
            raise
        except (ValueError,KeyError,IndexError,TypeError) as error:
            if attempt:raise ValueError('整片HTML结构不完整或包含不支持的接口，请重试') from None
            messages.append({'role':'user','content':'上一结果无效：'+str(error)[:300]+'。请返回完整闭合的html字段，保留renderFrame同步接口，禁止外联与自主时钟。'})
        except httpx.HTTPError:
            raise ModelCallError('整片动画模型连接失败，请稍后重试',category='transport') from None
