"""Deterministic exact-content fallback; exported pages still require visual review."""
from copy import deepcopy
from html import escape
from uuid import UUID, uuid5
from . import master_runtime as master
from .knowledge import outline_digest, require_reviewed_outline
from .schemas import Outline
from .text_layout import wrap_text
from . import styles

VERSION='ppt-readable-fallback-1'
SLIDE_KEYS=('id','layout','title','content','slots')

def make_pages(slide,*,style=None):
    theme=styles.identity(style);palette=styles.colors(theme)
    # Full-width glyph assumption leaves generous export margins.
    if any(ord(c)<32 and c not in (chr(9),chr(10),chr(13)) or 0xD800<=ord(c)<=0xDFFF for c in slide['title']+slide['content']):
        raise ValueError('课件内容含不支持的字符，请检查大纲')
    titles=wrap_text(' '.join(slide['title'].split()),22)
    start=96+60*(len(titles)-1)+64
    capacity=max(1,(624-start)//40+1)
    lines=[];prefix=''
    for paragraph in slide['content'].splitlines(keepends=True):
        text=paragraph.rstrip(chr(10)+chr(13)+chr(0x85)+chr(0x2028)+chr(0x2029))
        ending=paragraph[len(text):]
        if chr(9) in text:
            parts=[];part='';width=0
            for char in text:
                cost=4 if char==chr(9) else 1
                if width+cost>36:parts.append(part);part='';width=0
                part+=char;width+=cost
            if part:parts.append(part)
        else:parts=wrap_text(text,36) or ['']
        for n,part in enumerate(parts):
            raw=part+(ending if n==len(parts)-1 else '')
            if not part.strip():
                if lines:lines[-1]=(lines[-1][0],lines[-1][1]+raw)
                else:prefix+=raw
                continue
            lines.append((part.expandtabs(4),prefix+raw));prefix=''
    if not lines:raise ValueError('课件内容为空')
    chunks=[lines[n:n+capacity] for n in range(0,len(lines),capacity)]
    pages=[]
    for index,chunk in enumerate(chunks):
        content=''.join(raw for _,raw in chunk)
        sid=slide['id'] if index==0 else str(uuid5(UUID(slide['id']),VERSION+':'+outline_digest({'slides':[slide]})+':'+str(index)))
        heading=''.join(f'<text x="64" y="{96+n*60}" font-size="48" font-weight="bold" fill="{palette['title']}">{escape(line)}</text>' for n,line in enumerate(titles))
        body=''.join(f'<text x="64" y="{start+n*40}" font-size="28" xml:space="preserve" fill="{palette['body']}">{escape(line)}</text>' for n,(line,_) in enumerate(chunk))
        footer=f'续页 {index+1} / {len(chunks)}' if len(chunks)>1 else '课堂知识'
        svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720" font-family="Microsoft YaHei, Arial" data-pptx-page-role="content"><rect id="background" data-pptx-role="background" x="0" y="0" width="1280" height="720" fill="{palette['bg']}"/><g id="title" data-pptx-bounds="64 40 1152 {start-64}">{heading}</g><g id="body" data-pptx-bounds="64 {start-32} 1152 {664-start}">{body}</g><g id="footer" data-pptx-bounds="64 656 1152 40"><text x="64" y="684" font-size="22" fill="{palette['muted']}">{footer}</text></g></svg>'
        master.validate_svg(svg,{},require_visual=False)
        pages.append({**deepcopy(slide),'id':sid,'content':content,'slots':{},'renderer':master.VERSION,'svg':svg,
            'design':{'id':sid,'visual_kind':'text','visual_brief':'完整保留已确认内容','composition':'清晰标题与宽松正文，内容过长自动续页'},
            'fallback':{'version':VERSION,'source_slide_id':slide['id'],'source_sha256':outline_digest({'slides':[slide]}),'part':index+1,'parts':len(chunks)}})
    if theme['id']!=styles.DEFAULT:
        for page in pages:page['design']['template']=deepcopy(theme)
    return pages

def paginated_outline(source,groups,*,style=None):
    """Derive approval only for a proven exact partition of reviewed source text."""
    require_reviewed_outline(source)
    known={s['id'] for s in source['slides']}
    if not set(groups)<=known:raise ValueError('自动续页来源无效')
    slides=[]
    for slide in source['slides']:
        if slide['id'] not in groups:
            slides.append(deepcopy(slide));continue
        pages=groups[slide['id']]
        expected=make_pages(slide,style=style)
        # Reject stale/tampered SVGs, IDs, labels or provenance in checkpoints.
        if [{k:v for k,v in p.items() if k!='review'} for p in pages]!=expected:
            raise ValueError('自动续页内容与已确认大纲不一致')
        if ''.join(p['content'] for p in pages)!=slide['content']:raise ValueError('自动续页内容不完整')
        slides.extend({k:deepcopy(p[k]) for k in SLIDE_KEYS} for p in pages)
    if len(slides)>40:raise ValueError('完整保留内容需要超过 40 页，请精简大纲后重新制作；原课件已保留')
    # Validate limits without normalizing whitespace at partition boundaries.
    Outline.model_validate({'slides':slides})
    result={**deepcopy(source),'slides':slides}
    if slides!=source['slides']:
        result['review']={**deepcopy(source['review']),'content_sha256':outline_digest(result),
            'pagination':{'version':VERSION,'source_sha256':outline_digest(source),
                'groups':{sid:[p['id'] for p in pages] for sid,pages in groups.items()}}}
    return result
