"""Allowlisted teacher edits to existing SVG text; never accept replacement SVG."""
from copy import deepcopy
import re
import math
import unicodedata
import xml.etree.ElementTree as ET
from . import master_runtime as master

NS='{http://www.w3.org/2000/svg}'
ET.register_namespace('',NS[1:-1])
class TextEditError(ValueError):pass

def plain_text(node):
    result=node.text or ''
    last_y=node.get('y') or next((c.get('y') for c in node if c.get('y') is not None),None)
    for child in node:
        if child.tag==NS+'tspan':
            new_line=child.get('dy') not in (None,'0','0.0') or (child.get('y') is not None and last_y is not None and child.get('y')!=last_y)
            if new_line and result:result+='\n'
            result+=''.join(child.itertext())
            last_y=child.get('y',last_y)
        result+=child.tail or ''
    return result

def records(svg):
    if '<!' in svg or '<?' in svg:raise TextEditError('页面格式不支持直接编辑')
    try:root=ET.fromstring(svg)
    except ET.ParseError:raise TextEditError('页面数据无法读取') from None
    rows=[]
    def visit(node,inherited,transformed=False,hidden=False,parent=None):
        attrs={**inherited,**node.attrib};transformed=transformed or bool(node.get('transform'));hidden=hidden or node.tag in (NS+'defs',NS+'marker')
        if node.tag==NS+'text' and not hidden:
            index=len(rows);size=float(attrs.get('font-size','28'));children=list(node)
            first=children[0] if children else node
            x=float(first.get('x',node.get('x',attrs.get('x','0'))));y=float(first.get('y',node.get('y',attrs.get('y','0'))))
            editable=not transformed and all(n.tag==NS+'tspan' and not list(n) and not n.get('rotate') and not n.get('dx') and float(n.get('font-size',size))==size and (not n.get('dy') or abs(float(n.get('dy')))==0 or float(n.get('dy'))>=size*.8) and float(n.get('x',x))==x for n in children)
            editable=editable and not node.get('dx') and not node.get('dy')
            bounds=attrs.get('data-pptx-bounds','').split() if parent is not None and (parent.get('id') or '').startswith('teacher-new-') else []
            frame=node.get('data-pptx-frame','').split();extent=frame if len(frame)==4 else bounds
            width=float(extent[2]) if len(extent)==4 else None;height=float(extent[3]) if len(extent)==4 else None
            rows.append({'bounds_node':parent if bounds else None,'width':width,'height':height,'node':node,'key':f'text-{index}','text':plain_text(node),'font_size':size,'color':attrs.get('fill','#173359'),'bold':attrs.get('font-weight','normal') in ('bold','600','700','800','900'),'x':x,'y':y,'anchor':attrs.get('text-anchor','start'),'editable':editable})
        else:
            for child in node:visit(child,attrs,transformed,hidden,node)
    visit(root,{})
    return root,rows

def text_blocks(svg):
    _,rows=records(svg)
    return [{k:v for k,v in r.items() if k not in ('node','bounds_node')} for r in rows]

def measure(text,size,bold):
    # Fixed conservative metrics shared with the web editor, so line breaks match export.
    return sum(size*(1 if unicodedata.east_asian_width(c) in ('W','F') else .62) for c in text)

def wrap(value,width,size,bold):
    lines=[]
    for paragraph in value.split('\n'):
        current=''
        for char in paragraph:
            if current and measure(current+char,size,bold)>width:lines.append(current);current=''
            current+=char
        lines.append(current)
    return lines

def apply_text_edits(page,edits,*,additions=None,moves=None):
    result=deepcopy(page);additions=additions or [];moves=moves or []
    source_svg=page['svg']
    if moves:
        from .object_moving import apply_moves
        source_svg=apply_moves(source_svg,moves,validate=False)
    root,rows=records(source_svg);lookup={r['key']:r for r in rows};seen=set();changed_text=False
    if (not edits and not additions and not moves) or len(edits)>100 or len(additions)>20:raise TextEditError('请选择文字或添加文本框')
    title=result['title'];changed_any=source_svg!=page['svg']
    for patch in edits:
        key=patch.get('key')
        if key not in lookup or key in seen:raise TextEditError('所选文字已变化，请重新进入编辑')
        seen.add(key);r=lookup[key];node=r['node']
        if not r['editable']:raise TextEditError('旋转或组合变换的文字暂不支持直接编辑，可使用 AI 修改')
        layout=(result.get('text_layout') or {}).get(key,{})
        stored=layout.get('text',r['text']) if layout.get('rendered')==r['text'] else r['text']
        value=patch.get('text',stored);size=patch.get('font_size',r['font_size']);color=patch.get('color',r['color']);bold=patch.get('bold',r['bold'])
        if not isinstance(value,str) or not value.strip() or len(value)>2000 or any(ord(c)<32 and c not in '\n\t' for c in value):raise TextEditError('文字不能为空，且不能超过 2000 字')
        if not isinstance(size,(int,float)) or isinstance(size,bool) or not 18<=size<=72:raise TextEditError('字号请设为 18 到 72')
        if not re.fullmatch(r'#[0-9a-fA-F]{6}',color):raise TextEditError('请选择有效颜色')
        if not isinstance(bold,bool):raise TextEditError('加粗设置无效')
        for field in ('x','y','width','height'):
            if field in patch:
                v=patch[field]
                if not isinstance(v,(int,float)) or isinstance(v,bool) or not math.isfinite(v):raise TextEditError('文本框位置和大小无效')
                low,high=(80,1200) if field=='width' else (24,720) if field=='height' else (0,1280) if field=='x' else (0,720)
                if not low<=v<=high:raise TextEditError('文本框位置或大小超出范围')
        text_changed=value!=stored;style_changed=any(k in patch and patch[k]!=r[k] for k in ('font_size','color','bold'))
        geometry_changed=any(k in patch and patch[k]!=r.get(k) for k in ('x','y','width','height'))
        if not text_changed and not style_changed and not geometry_changed:continue
        changed_any=True
        if text_changed or size!=r['font_size'] or bold!=r['bold'] or geometry_changed:
            # Keep the original text footprint unless the available space to the page edge is smaller.
            widths=[measure(line,r['font_size'],r['bold']) for line in r['text'].split('\n')]
            original=max(widths or [size]);x=patch.get('x',r['x']);y=patch.get('y',r['y']);anchor=r['anchor']
            edge=1280-x-24 if anchor=='start' else x-24 if anchor=='end' else 2*min(x-24,1280-x-24)
            width=patch.get('width',r['width']) or min(max(original*1.05,size*5),edge)
            if width<size:raise TextEditError('文字位置超出页面，请使用 AI 调整布局')
            lines=wrap(value,width,size,bold)
            bottom=y+(len(lines)-1)*size*1.35+size*.45
            limit=696
            left=x if anchor=='start' else x-width if anchor=='end' else x-width/2
            explicit=any(k in patch for k in ('width','height','x','y')) or node.get('data-pptx-frame') is not None
            height=patch.get('height',r.get('height')) if explicit else None
            height=height or max(24,bottom-y+size)
            if left<0 or left+width>1280 or y-size<0 or y-size+height>720 or (not explicit and bottom>limit):raise TextEditError('文本框超出页面边界，请调整后保存；输入已保留')
            if explicit:node.set('data-pptx-frame',' '.join(format(v,'.8g') for v in (left,y-size,width,height)))
            if geometry_changed:node.set('x',str(x));node.set('y',str(y))
            if r['bounds_node'] is not None:r['bounds_node'].set('data-pptx-bounds',f'{left} {y-size} {width} {max(height,bottom-y+size)}')
            for child in list(node):node.remove(child)
            node.text=None
            for i,line in enumerate(lines):
                attrs={'x':str(x),'dy':str(size*1.35 if i else 0)} if explicit else {'x':str(x),'y':str(y+i*size*1.35)}
                span=ET.SubElement(node,NS+'tspan',attrs)
                span.text=line
            if explicit and len(lines)==1:
                for child in list(node):node.remove(child)
                node.text=lines[0]
            result.setdefault('text_layout',{})[key]={'text':value,'rendered':plain_text(node)}
        for name,key2 in [('font-size','font_size'),('fill','color'),('font-weight','bold')]:
            if key2 in patch or text_changed:
                value2=str(size) if key2=='font_size' else color if key2=='color' else '700' if bold else '400'
                node.set(name,value2)
                for child in node.iter(NS+'tspan'):child.set(name,value2)
        if text_changed:
            changed_text=True
            if re.sub(r'\s+','',stored)==re.sub(r'\s+','',title):
                if len(value.replace('\n',' '))>80:raise TextEditError('页面标题不能超过 80 字')
                result['title']=value.replace('\n',' ')
    added_keys=set()
    existing_ids={n.get('id') for n in root.iter()}
    for added in additions:
        key=added.get('key','');value=added.get('text','');x=added.get('x');y=added.get('y');width=added.get('width');height=added.get('height');size=added.get('font_size',28);color=added.get('color','#173359');bold=added.get('bold',False)
        if not re.fullmatch(r'new-[0-9]{1,8}',key) or key in added_keys:raise TextEditError('新增文本框标识无效或重复')
        added_keys.add(key)
        if not isinstance(value,str) or not value.strip() or len(value)>2000 or any(ord(c)<32 and c not in '\n\t' for c in value):raise TextEditError('新增文本框不能为空，且不能超过 2000 字')
        if any(not isinstance(v,(int,float)) or isinstance(v,bool) or not math.isfinite(v) for v in (x,y,width,size)) or not 18<=size<=72 or not 80<=width<=1200 or not 0<=x or x+width>1280 or y-size<0:raise TextEditError('文本框位置或宽度超出页面，请调整后再保存')
        if not re.fullmatch(r'#[0-9a-fA-F]{6}',color) or not isinstance(bold,bool):raise TextEditError('文本框样式无效')
        lines=wrap(value,width,size,bold);bottom=y+(len(lines)-1)*size*1.35+size*.45
        if height is None and bottom>720:raise TextEditError('新增文本框超出页面，请上移或减少内容')
        if height is not None and (not isinstance(height,(int,float)) or isinstance(height,bool) or not math.isfinite(height) or height<24 or y-size+height>720):raise TextEditError('文本框高度超出页面')
        ident='teacher-'+key
        suffix=1
        while ident in existing_ids:ident='teacher-'+key+'-'+str(suffix);suffix+=1
        existing_ids.add(ident)
        group=ET.SubElement(root,NS+'g',{'id':ident,'data-pptx-bounds':f'{x} {y-size} {width} {bottom-y+size}'})
        node=ET.SubElement(group,NS+'text',{'x':str(x),'y':str(y),'font-family':'Microsoft YaHei, Arial','font-size':str(size),'fill':color,'font-weight':'700' if bold else '400'})
        height=height or bottom-y+size
        node.set('data-pptx-frame',' '.join(format(v,'.8g') for v in (x,y-size,width,height)))
        for i,line in enumerate(lines):ET.SubElement(node,NS+'tspan',{'x':str(x),'dy':str(size*1.35 if i else 0)}).text=line
        if len(lines)==1:
            for child in list(node):node.remove(child)
            node.text=lines[0]
        result.setdefault('text_layout',{})[f'text-{len(rows)+len(added_keys)-1}']={'text':value,'rendered':plain_text(node)}
        changed_any=changed_text=True
    if not changed_any:return result
    result['svg']=ET.tostring(root,encoding='unicode')
    if moves:
        from .object_moving import validate_moved_svg
        result['svg']=validate_moved_svg(result['svg'],{m['key'] for m in moves})
    if changed_text:
        content='\n'.join((result.get('text_layout',{}).get(r['key'],{}).get('text',r['text']) if result.get('text_layout',{}).get(r['key'],{}).get('rendered')==r['text'] else r['text']) for r in text_blocks(result['svg']))
        if len(content)>3000:raise TextEditError('页面文字总量超过 3000 字，请精简后再保存')
        result['content']=content
        result['slots']={}
    result.pop('review',None);result.pop('delivery',None)
    return result


from .object_moving import movable_objects
