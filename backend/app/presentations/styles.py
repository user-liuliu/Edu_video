"""Approved teaching templates packaged with the server; legacy defaults stay clear blue."""
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
import json

DEFAULT='clear-blue-teaching'
IDS=(DEFAULT,'lively-illustration','academic-formal')
NAMES={DEFAULT:'简洁教学 · 清蓝','lively-illustration':'活泼插画 · 橙光','academic-formal':'学术正式 · 墨红'}
LAYOUTS={'cover':'01_cover.svg','concept':'02a_content_concept.svg','image-text':'02b_content_image_text.svg','compare':'02c_content_compare.svg','process':'02d_content_process.svg','practice':'02e_content_practice.svg','summary':'03_ending.svg'}
LEGACY_COLORS={'bg':'#FFFFFF','title':'#173359','body':'#273B53','accent':'#2465D9','secondary':'#2B9578','muted':'#61738A','surface':'#F4F7FC','surface2':'#F4F7FC','rule':'#DCE5F1'}

def identity(value=None):
    if isinstance(value,dict):
        if value.get('version','1.0.0')!='1.0.0':raise ValueError('课件模板版本不受支持')
        value=value.get('id')
    value=DEFAULT if value in (None,'auto') else value
    if value not in IDS:raise ValueError('课件风格不受支持')
    return {'id':value,'version':'1.0.0'}

def page_identity(page):
    return identity((page.get('design') or {}).get('template'))

def selected(project):
    return identity(getattr(project,'style','auto'))

def catalog():
    return [{'id':s,'version':'1.0.0','name':NAMES[s]} for s in IDS]

@lru_cache(maxsize=2)
def _assets(style):
    base=Path(__file__).parent/'templates'/style
    tokens=json.loads((base/'tokens.json').read_text(encoding='utf-8-sig'))
    return tokens,(base/'style_prompt.md').read_text(encoding='utf-8-sig'),{k:(base/v).read_text(encoding='utf-8-sig') for k,v in LAYOUTS.items()}

def colors(value=None):
    style=identity(value)['id']
    return deepcopy(LEGACY_COLORS if style==DEFAULT else _assets(style)[0]['colors'])

def behavior(value=None):
    style=identity(value)['id']
    if style=='lively-illustration':return '奶油底、橙绿强调、大圆角区域和可编辑情境插图；以观察、探究和操作组织内容，保持开放留白。'
    if style=='academic-formal':return '纸白底、深墨文字、酒红强调；开放分栏、细分隔线与编号，以定义、图像证据和方法验证组织正式讲授。'
    return '白底、深蓝文字和清蓝强调；以教学图解、示例和练习清晰组织内容。'

def contract(value=None,layout=None):
    info=identity(value);style=info['id'];result={**info,'name':NAMES[style],'colors':colors(style),'behavior':behavior(style)}
    if style!=DEFAULT:
        tokens,prompt,svgs=_assets(style)
        result.update(typography=tokens['typography_px'],guidance=prompt.replace('当前为待审阅prototype，尚未接入网站','当前已通过用户样张审阅并发布到应用'))
        if layout is not None:
            if layout not in LAYOUTS:raise ValueError('课件版式不受支持')
            result['layout_svg']=svgs[layout]
            result['reference_rules']='layout_svg是已确认的只读版式参考，不是本页内容。替换全部占位符和学科示意图，使用本次大纲，不照抄篮球或抛物线。输出必须遵守应用SVG白名单：去除模板专用data-pptx-layer/placeholder等属性、虚线属性与xml:space，改为应用要求的根级g分组与bounds。延续版式空间语法，可随内容调整，不机械换色。'
    return result

def generation_rule(value=None):
    c=contract(value);p=c['colors']
    sizes='64（封面）、44（页标题）、32（小标题）、28（正文）、22（图注），页脚可18' if c['id']!=DEFAULT else '48（标题）、32（小标题）、28（正文）、22（图注）'
    return f"{c['name']}：背景{p['bg']}、标题{p['title']}、正文{p['body']}、强调{p['accent']}、辅助{p['secondary']}。{c['behavior']}字号使用{sizes}。保留教学语义所需颜色；不溢出、不重叠，不靠缩小字号塞内容。"
