"""Server-owned SVG objects and bounded, baked translations (no client SVG)."""
import math
import re
import xml.etree.ElementTree as ET
from . import master_runtime as master

NS='{http://www.w3.org/2000/svg}'

def number(value):
    return format(float(value),'.8g')

def inverse_delta(matrix,dx,dy):
    a,b,c,d,_,_=matrix;det=a*d-b*c
    if abs(det)<1e-8:raise ValueError('对象坐标不可移动')
    return ((d*dx-c*dy)/det,(-b*dx+a*dy)/det)

def object_records(root):
    from .text_editing import records,measure
    geometry=master.geometry_api();_,texts=records(ET.tostring(root,encoding='unicode'))
    text_by_index=iter(texts);text_map={}
    def map_text(node):
        if node.tag in (NS+'defs',NS+'marker'):return
        if node.tag==NS+'text':
            row=next(text_by_index,None)
            if row:text_map[id(node)]=row
        else:
            for child in node:map_text(child)
    map_text(root)
    def bbox(node,matrix,paint):
        attrs={**paint,**node.attrib};m=matrix
        if node.get('transform'):m=geometry.matrix_multiply(m,geometry.parse_transform_matrix(node.get('transform')))
        tag=node.tag.removeprefix(NS)
        if tag in ('defs','marker') or float(attrs.get('opacity','1'))==0:return None
        boxes=[]
        if tag in ('g','svg'):
            if node.get('data-pptx-bounds'):
                x,y,w,h=map(float,node.get('data-pptx-bounds').split());boxes.append(geometry._apply_matrix_bbox((x,y,x+w,y+h),m))
            boxes.extend(box for child in node if (box:=bbox(child,m,attrs)) is not None)
        elif tag=='text':
            r=text_map.get(id(node))
            if r:
                size=r['font_size'];w=r['width'] or max((measure(line,size,r['bold']) for line in r['text'].split('\n')),default=size)
                frame=node.get('data-pptx-frame')
                if frame:
                    fx,fy,fw,fh=map(float,frame.split());return geometry._apply_matrix_bbox((fx,fy,fx+fw,fy+fh),m)
                x=r['x']-(w if r['anchor']=='end' else w/2 if r['anchor']=='middle' else 0);y=r['y']-size
                boxes.append(geometry._apply_matrix_bbox((x,y,x+w,r['y']+(len(r['text'].split('\n'))-1)*size*1.35+size*.45),m))
        else:
            box=geometry._element_local_bbox(node)
            if box:boxes.append(geometry._apply_matrix_bbox(box,m))
        if not boxes:return None
        return min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)
    result=[]
    def visit(node,path,matrix,paint,ancestors):
        tag=node.tag.removeprefix(NS)
        if tag in ('defs','marker'):return
        attrs={**paint,**node.attrib};m=matrix
        if node.get('transform'):m=geometry.matrix_multiply(m,geometry.parse_transform_matrix(node.get('transform')))
        background=node.get('data-pptx-role')=='background' or (node.get('id') or '').lower() in ('background','bg','page-background') or tag=='rect' and float(node.get('width',0))>=1279 and float(node.get('height',0))>=719
        if path and not background and (box:=bbox(node,matrix,paint)) is not None:
            kind='text' if tag=='text' else 'image' if tag=='image' else 'group' if tag=='g' else 'shape'
            r=text_map.get(id(node));label=r['text'][:30] if r else node.get('id') or {'image':'图片','group':'组合图形','shape':'图形'}[kind]
            result.append({'key':'object-'+str(len(result)+1),'path':path,'kind':kind,'label':label,'text_key':r['key'] if r else None,'bounds':[box[0],box[1],box[2]-box[0],box[3]-box[1]],'node':node,'matrix':m,'ancestors':ancestors})
        if background:return
        for i,child in enumerate(node):visit(child,path+[i],m,attrs,ancestors+[node])
    visit(root,[],geometry.IDENTITY_MATRIX,{},[])
    return result

def movable_objects(svg):
    from .text_editing import records
    root,_=records(svg)
    return [{k:v for k,v in row.items() if k not in ('node','matrix','ancestors')} for row in object_records(root)]

def translate_node(node,dx,dy):
    geometry=master.geometry_api();tag=node.tag.removeprefix(NS)
    if node.get('transform') and tag=='g':
        # Move the group's existing coordinate system, keeping its local metadata valid.
        value=node.get('transform');parts=list(re.finditer(r'(translate|scale|rotate)\(([^)]*)\)',value))
        matrix=geometry.IDENTITY_MATRIX
        for part in parts:
            if part.group(1)=='translate':
                local_dx,local_dy=inverse_delta(matrix,dx,dy)
                nums=[float(v) for v in re.split(r'[, ]+',part.group(2).strip())]
                replacement='translate('+number(nums[0]+local_dx)+' '+number((nums[1] if len(nums)>1 else 0)+local_dy)+')'
                node.set('transform',value[:part.start()]+replacement+value[part.end():]);return
            matrix=geometry.matrix_multiply(matrix,geometry.parse_transform_matrix(part.group(0)))
        if len(parts)<3:
            node.set('transform','translate('+number(dx)+' '+number(dy)+') '+value);return
        # Three scale/rotate operations can include identity operations; remove these.
        reduced=[part.group(0) for part in parts if geometry.parse_transform_matrix(part.group(0))!=geometry.IDENTITY_MATRIX]
        if len(reduced)<3:node.set('transform','translate('+number(dx)+' '+number(dy)+') '+' '.join(reduced));return
        raise ValueError('此复杂变换组合请先选择内部对象移动')
    if node.get('transform'):dx,dy=inverse_delta(geometry.parse_transform_matrix(node.get('transform')),dx,dy)
    for metadata in ('data-pptx-bounds','data-pptx-frame'):
        if node.get(metadata):
            x,y,w,h=map(float,node.get(metadata).split());node.set(metadata,' '.join(map(number,(x+dx,y+dy,w,h))))
    pairs={'rect':('x','y'),'image':('x','y'),'circle':('cx','cy'),'ellipse':('cx','cy'),'text':('x','y'),'tspan':('x','y')}
    if tag in pairs:
        for key,delta in zip(pairs[tag],(dx,dy)):
            supplied_by_span=tag=='text' and any(child.get(key) is not None for child in node)
            if key in node.attrib or tag not in ('text','tspan') or tag=='text' and not supplied_by_span:node.set(key,number(float(node.get(key,'0'))+delta))
    elif tag=='line':
        for key,delta in [('x1',dx),('x2',dx),('y1',dy),('y2',dy)]:node.set(key,number(float(node.get(key,'0'))+delta))
    elif tag in ('polygon','polyline'):
        points=geometry.parse_svg_points(node.get('points',''),min_points=2)
        node.set('points',' '.join(number(x+dx)+','+number(y+dy) for x,y in points))
    elif tag=='path':
        commands=geometry.svg_path_to_absolute(geometry.parse_svg_path(node.get('d','')))
        values=[]
        for command in commands:
            args=list(command.args)
            if command.cmd=='A':args[-2]+=dx;args[-1]+=dy
            else:
                for i in range(len(args)):args[i]+=dx if i%2==0 else dy
            values.append(command.cmd+' '+' '.join(map(number,args)))
        node.set('d',' '.join(values))
    for child in node:
        if child.tag not in (NS+'defs',NS+'marker'):translate_node(child,dx,dy)

def apply_moves(svg,moves,*,validate=True):
    from .text_editing import records,TextEditError
    root,_=records(svg);rows=object_records(root);lookup={r['key']:r for r in rows};seen=set();changed=False
    if len(moves)>200:raise TextEditError('一次移动的对象过多')
    for patch in moves:
        key=patch.get('key');dx=patch.get('dx');dy=patch.get('dy')
        if key not in lookup or key in seen:raise TextEditError('移动对象已变化，请重新进入编辑')
        if any(not isinstance(v,(int,float)) or isinstance(v,bool) or not math.isfinite(v) or abs(v)>1280 for v in (dx,dy)):raise TextEditError('移动坐标无效')
        seen.add(key)
        if dx==dy==0:continue
        row=lookup[key]
        # Convert page movement into the parent's local coordinate system.
        parent_matrix=master.geometry_api().IDENTITY_MATRIX
        for ancestor in row['ancestors']:
            if ancestor.get('transform'):parent_matrix=master.geometry_api().matrix_multiply(parent_matrix,master.geometry_api().parse_transform_matrix(ancestor.get('transform')))
        try:translate_node(row['node'],*inverse_delta(parent_matrix,dx,dy))
        except (ValueError,TypeError,OverflowError) as exc:raise TextEditError('此对象暂时无法移动：'+str(exc)) from None
        changed=True
    if not changed:return svg
    if not validate:return ET.tostring(root,encoding='unicode')
    return validate_moved_svg(ET.tostring(root,encoding='unicode'),seen)

def validate_moved_svg(svg,seen):
    from .text_editing import records,TextEditError
    root,_=records(svg)
    for row in object_records(root):
        if row['key'] in seen:
            x,y,w,h=row['bounds']
            if min(x,y)<-.1 or x+w>1280.1 or y+h>720.1:raise TextEditError('对象超出页面，请移回画面后保存')
    # Expand existing module metadata after moving a child beyond its previous footprint.
    for row in reversed(object_records(root)):
        node=row['node']
        if node.get('data-pptx-bounds') and node.tag==NS+'g':
            x,y,w,h=row['bounds']
            if min(x,y)<-.1 or x+w>1280.1 or y+h>720.1:raise TextEditError('组合图形超出页面，请调整后保存')
            a,b,c,d,tx,ty=row['matrix']
            if (a,b,c,d)==(1,0,0,1):node.set('data-pptx-bounds',' '.join(map(number,(x-tx,y-ty,w,h))))
    return ET.tostring(root,encoding='unicode')
