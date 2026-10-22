"""Deterministic scene compositor, separate from model generation policy."""
import json
import math


def _js(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).replace('<', '\u003c').replace('>', '\u003e').replace('&', '\u0026')


def assemble_film(bundle, targets):
    from .film_modules import validate_film,render_key
    bundle = validate_film(bundle, targets)
    timeline = []
    cursor = 0.
    for index, target in enumerate(targets):
        start, end = target['start'], target['end']
        if not all(isinstance(t, (int,float)) and math.isfinite(t) for t in (start,end)) or start != cursor or not start < end <= 7200:
            raise ValueError('动画片段时间范围无效或不连续')
        timeline.append({'id': render_key(target,index), 'start': start, 'end': end})
        cursor = end
    factories = ','.join(_js(item['id'])+':function(root,t,localTime,progress,shared){'+item['code']+chr(10)+'}' for item in bundle['segments'])
    bridge_fns = ','.join(_js(item['from_id']+'>'+item['to_id'])+':function(t,progress,outgoing,incoming){'+item['code']+chr(10)+'}' for item in bundle['transitions'])
    source = '<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;width:1280px;height:720px;overflow:hidden}#edu-film{position:relative;width:1280px;height:720px;overflow:hidden;background:#f6f2e9}</style></head><body><main id="edu-film"></main>'
    source += '<script type="application/json" id="edu-film-bundle">'+_js(bundle)+'</script>'
    source += '<script type="application/json" id="edu-film-timeline">'+_js(timeline)+'</script>'
    source += '<script>(function(){"use strict";const timeline='+_js(timeline)+',specs='+_js(bundle['segments'])+',transitions='+_js(bundle['transitions'])+',sharedHtml='+_js(bundle['shared_html'])+';'
    source += 'const makeShared=function(root){'+bundle['shared_code']+chr(10)+'};const renderers={'+factories+'},bridges={'+bridge_fns+'};'
    source += r"""
const stage=document.getElementById('edu-film'),nodes=new Map(),roots=new Map();
const baseStyle='position:absolute;inset:0;width:1280px;height:720px;overflow:hidden;display:none;opacity:1;transform:none;transform-origin:center;pointer-events:none';
for(const spec of specs){const host=document.createElement('section');host.dataset.eduSegment=spec.id;host.style.cssText=baseStyle;stage.appendChild(host);const root=host.attachShadow({mode:'open'});root.innerHTML='<style>:host{font:24px Microsoft YaHei,Noto Sans CJK SC,sans-serif}svg,canvas{display:block}</style>'+sharedHtml+spec.html;nodes.set(spec.id,host);roots.set(spec.id,root);}
function render(item,t){t=Math.max(item.start,Math.min(item.end,t));const host=nodes.get(item.id),root=roots.get(item.id);host.style.display='block';const shared=makeShared(root)||{};renderers[item.id](root,t,t-item.start,(t-item.start)/(item.end-item.start),shared);return host;}
window.renderFrame=function(t){if(!Number.isFinite(t))throw Error('无效动画时间');for(const node of nodes.values())node.style.cssText=baseStyle;
for(let i=0;i<transitions.length;i++){const tr=transitions[i];if(tr.mode==='continuous')continue;const a=timeline[i],b=timeline[i+1],half=Math.min(tr.duration/2,(a.end-a.start)/3,(b.end-b.start)/3),start=a.end-half,end=a.end+half;if(start<=t&&t<=end){const progress=(t-start)/(end-start),outgoing=render(a,t),incoming=render(b,t);bridges[tr.from_id+'>'+tr.to_id](t,progress,outgoing,incoming);const fade=progress*progress*(3-2*progress);incoming.style.zIndex='0';outgoing.style.zIndex='1';incoming.style.opacity='1';outgoing.style.opacity=String(1-fade);return;}}
const active=timeline.find(item=>item.start<=t&&t<item.end)||timeline[t<0?0:timeline.length-1];render(active,t);};
})();</script></body></html>
"""
    if len(source.encode('utf-8')) > 1_500_000:
        raise ValueError('整片HTML大小超出限制')
    from .direct_html import validate_html
    return validate_html(source)
