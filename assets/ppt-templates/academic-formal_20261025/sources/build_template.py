from pathlib import Path
import html,json,re,xml.etree.ElementTree as ET,yaml
R=Path(__file__).resolve().parents[1]; STYLE=R.name.rsplit('_',1)[0]; PLAY=STYLE=='lively-illustration'
NAME='活泼插画 · 橙光' if PLAY else '学术正式 · 墨红'
C=({'bg':'#FFF9ED','title':'#243C36','body':'#344841','accent':'#B84A26','secondary':'#23756A','muted':'#63736C','surface':'#F9E6CE','surface2':'#E0EEE6','rule':'#D5DED5','white':'#FFFFFF'} if PLAY else {'bg':'#FAFAF7','title':'#202D3A','body':'#34414B','accent':'#8B3547','secondary':'#3E6179','muted':'#63717A','surface':'#F0E6E7','surface2':'#EAF0F3','rule':'#CFD4D7','white':'#FFFFFF'})
T=R/'templates';S=R/'svg_output'
for d in (T,S,R/'exports',R/'validation'):d.mkdir(exist_ok=True)
fixtures=json.loads((R/'sources/sample_fixture.json').read_text(encoding='utf-8-sig'))['slides'];P=[];idx=2
def e(v):return html.escape(str(v),quote=True)
def col(v):return C.get(v,v)
def layer(v):return f' data-pptx-layer="{v}" data-pptx-editable="false"' if v else ''
def rect(id,x,y,w,h,c,rx=0,own='layout'):return f'<rect id="{id}"{layer(own)} x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{col(c)}"/>'
def circle(id,x,y,r,c,own='layout',stroke=None,sw=1):return f'<circle id="{id}"{layer(own)} cx="{x}" cy="{y}" r="{r}" fill="{col(c)}"'+(f' stroke="{col(stroke)}" stroke-width="{sw}"' if stroke else '')+'/>'
def line(id,x1,y1,x2,y2,c='rule',sw=2,own='layout',dash=False):return f'<line id="{id}"{layer(own)} x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{col(c)}" stroke-width="{sw}"'+(' stroke-dasharray="6,3"' if dash else '')+'/>'
def text(id,s,x,y,size=26,c='body',bold=False,own=None,center=False):return f'<text id="{id}"{layer(own)} x="{x}" y="{y}" font-size="{size}" fill="{col(c)}" font-weight="'+('bold' if bold else 'normal')+'"'+(' text-anchor="middle"' if center else '')+'>'+e(s)+'</text>'
def path(id,d,c='accent',sw=3):return f'<path id="{id}" d="{d}" fill="none" stroke="{col(c)}" stroke-width="{sw}" stroke-linecap="round"/>'
def slot(id,key,box,size=28,c='body',bold=False,lines=1,kind='body',center=False):
 global idx
 n=0 if kind=='title' else idx
 if kind!='title':idx+=1
 x,y,w,h=box;xx=x+w/2 if center else x;value=''
 for j in range(lines):
  k=key if lines==1 else f'{key}_{j+1}';marker=e('{{'+k+'}}')
  value+=marker if j==0 else f'<tspan x="{xx}" dy="{round(size*1.42,2)}">{marker}</tspan>'
 return f'<g id="{id}" data-pptx-placeholder="{kind}" data-pptx-idx="{n}" data-pptx-bounds="{x} {y} {w} {h}"><text id="{id}-text" data-pptx-carrier="true" x="{xx}" y="{y+size}" font-size="{size}" fill="{col(c)}" font-weight="'+('bold' if bold else 'normal')+'"'+(' text-anchor="middle"' if center else '')+'>'+value+'</text></g>'
def proxy(id,box,content):
 global idx
 n=idx;idx+=1
 return f'<g id="{id}" data-pptx-placeholder="object" data-pptx-binding="proxy" data-pptx-idx="{n}" data-pptx-bounds="'+ ' '.join(map(str,box))+'">'+content+'</g>'
def heading(section):
 a=(rect('section-pill',64,40,214,34,'surface',17)+text('section-label',section,82,64,18,'accent',True,'layout') if PLAY else text('section-label',section,64,62,18,'accent',True,'layout')+line('title-rule',64,176,1216,176,'rule',1))
 return a+slot('page-title','PAGE_TITLE',(64,94 if PLAY else 87,1152,70),44,'title',True,kind='title')
def graph(id,box,up=False,labels=False,basket=False):
 x,y,w,h=box;left=x+42;right=x+w-28;bottom=y+h-44;top=y+25;mid=(left+right)/2
 vertex=bottom-25 if up else top+30;start=top+44 if up else bottom
 a=line(id+'-x',left,bottom,right,bottom,'muted',1.5,None)+line(id+'-y',left,bottom,left,top,'muted',1.5,None)+line(id+'-sym',mid,top,mid,bottom,'rule',1.5,None,True)
 a+=path(id+'-curve',f'M {left} {start} Q {mid} {round(2*vertex-start,2)} {right} {start}','secondary' if PLAY else 'accent',5)+circle(id+'-vertex',mid,vertex,5,'accent',None)
 if labels:a+=text(id+'-zero','0',left-20,bottom+25,18,'muted')+text(id+'-x-label','x',right+10,bottom-8,20,'muted')+text(id+'-y-label','y',left-25,top+16,20,'muted')+text(id+'-point','(2, 4)',mid+12,vertex-10,22,'accent')+text(id+'-four','4',right,bottom+25,18,'muted',center=True)
 if basket:a+=circle(id+'-ball',mid-55,vertex+28,25,'accent',None,'title',2)+path(id+'-seam1',f'M {mid-80} {vertex+28} L {mid-30} {vertex+28}','title',1.5)+path(id+'-seam2',f'M {mid-55} {vertex+3} Q {mid-40} {vertex+28} {mid-55} {vertex+53}','title',1.5)
 return a
def add(i,a,changes=None):
 global idx
 f=json.loads(json.dumps(fixtures[i]));filename=f['file'];layout=f['layout'];sample=f['sample'];sample.update(changes or {})
 master=rect('master-background',0,0,1280,720,'bg',own='master')+line('master-footer-rule',64,660,1216,660,'rule',1,'master')
 master+=circle('master-mark',69,687,5,'accent','master') if PLAY else rect('master-mark',64,678,3,18,'accent',own='master')
 footer=slot('course-footer','COURSE_NAME',(84,673,970,34),18,'muted',kind='footer')+slot('slide-number','PAGE_NUM',(1140,673,76,34),18,'muted',kind='slide-number',center=True)
 root=f'<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720" font-family="Arial, Microsoft YaHei" data-pptx-master="{STYLE}" data-pptx-master-name="{NAME}" data-pptx-layout="{STYLE}-{layout}" data-pptx-layout-name="{f["name"]}">'+master+a+footer+'</svg>'
 ET.register_namespace('','http://www.w3.org/2000/svg');tree=ET.fromstring(root);tree[:]=sorted(list(tree),key=lambda c:{'master':0,'layout':1}.get(c.get('data-pptx-layer'),2));root=ET.tostring(tree,encoding='unicode');(T/filename).write_text(root,encoding='utf-8');actual=root
 for key,value in sample.items():actual=actual.replace('{{'+key+'}}',e(value))
 assert '{{' not in actual,filename
 (S/filename).write_text(actual,encoding='utf-8');f['sample']=sample;f['markers']=re.findall(r'\{\{[A-Z0-9_]+\}\}',root);P.append(f);idx=2
def lively():
 a=rect('cover-panel',706,64,510,574,'surface2',40)+circle('cover-sun',1117,143,50,'surface')
 a+=slot('eyebrow','EYEBROW',(64,108,620,44),22,'secondary',True)+slot('title','TITLE',(64,204,620,180),64,'title',True,2,'title')+slot('subtitle','SUBTITLE',(64,419,620,108),28,'muted',lines=2)+slot('author','AUTHOR',(64,571,620,46),22,'secondary')
 a+=proxy('cover-visual',(732,196,456,344),graph('cover',(732,196,456,344),basket=True))+slot('caption','CAPTION',(744,564,434,46),22,'secondary',center=True);add(0,a)
 a=heading('01 / 概念探究')+rect('formula-field',64,196,1152,112,'surface2',24)+slot('formula','FORMULA',(104,218,1072,74),48,'secondary',True,center=True)
 for j,x in enumerate((64,460,856),1):a+=circle(f'coefficient-dot-{j}',x+20,361,20,'accent' if j==1 else 'secondary')+text(f'coefficient-number-{j}',str(j),x+20,370,23,'white',True,'layout',center=True)+slot(f'param-{j}',f'PARAM_{j}',(x+56,337,298,55),29,'title',True)+slot(f'explain-{j}',f'EXPLAIN_{j}',(x+18,420,338,160),28,lines=3)
 add(1,a)
 a=heading('02 / 看图发现')+rect('figure-field',64,196,532,408,'surface2',28)+proxy('teaching-visual',(86,228,490,322),graph('observation',(86,228,490,322),labels=True))+slot('figure-caption','FIGURE_CAPTION',(82,605,1116,42),22,'secondary')
 for j,y in enumerate((202,338,474),1):a+=circle(f'observe-dot-{j}',646,y+23,18,'accent')+text(f'observe-number-{j}',str(j),646,y+31,21,'white',True,'layout',center=True)+slot(f'observe-title-{j}',f'OBS_TITLE_{j}',(686,y,530,48),30,'title',True)+slot(f'observe-body-{j}',f'OBS_BODY_{j}',(686,y+61,530,52),26,'muted')
 add(2,a,{'OBS_BODY_3':'y = −(x − 2)² + 4 对应此示意图'})
 a=heading('03 / 比一比')+rect('up-field',64,198,552,362,'surface2',28)+rect('down-field',664,198,552,362,'surface',28)+slot('left-label','LEFT_LABEL',(92,218,496,52),30,'secondary',True)+slot('right-label','RIGHT_LABEL',(692,218,496,52),30,'accent',True)
 a+=proxy('left-visual',(106,280,468,208),graph('up',(106,280,468,208),up=True))+proxy('right-visual',(706,280,468,208),graph('down',(706,280,468,208)))+slot('left-description','LEFT_DESCRIPTION',(90,504,500,48),26)+slot('right-description','RIGHT_DESCRIPTION',(690,504,500,48),26)+slot('conclusion','CONCLUSION',(84,592,1112,55),26,'secondary',True,center=True);add(3,a)
 a=heading('04 / 动手画图')+slot('intro','INTRO',(64,188,1152,54),28,'muted')+line('process-track',122,307,1118,307,'secondary',4)
 for j,x in enumerate((64,460,856),1):a+=circle(f'step-circle-{j}',x+32,307,28,'accent' if j==1 else 'secondary')+text(f'step-number-{j}',f'0{j}',x+32,316,23,'white',True,'layout',center=True)+slot(f'step-title-{j}',f'STEP_TITLE_{j}',(x,373,352,55),32,'title',True)+slot(f'step-body-{j}',f'STEP_BODY_{j}',(x,447,352,145),28,lines=3)
 a+=slot('hint','HINT',(64,602,1152,42),23,'secondary');add(4,a)
 a=heading('05 / 轮到你了')+rect('question-field',64,191,1152,122,'surface',22)+slot('question','QUESTION',(90,205,1100,100),31,'title',True,2)+rect('hint-field',896,338,320,239,'surface2',24)
 for j,y in enumerate((346,426,506),1):a+=slot(f'task-{j}',f'TASK_{j}',(64,y,804,58),29)
 a+=slot('hint-title','HINT_TITLE',(924,351,264,48),26,'secondary',True)+slot('hint-body','HINT_BODY',(924,414,264,155),25,'muted',lines=4)+slot('practice-footer','PRACTICE_FOOTER',(64,600,1152,42),22,'secondary');add(5,a)
 a=heading('06 / 带走三个发现')+rect('summary-field',64,198,1152,102,'surface2',26)+slot('summary-lead','SUMMARY_LEAD',(92,223,1096,68),42,'secondary',True)
 for j,y in enumerate((332,420,508),1):a+=circle(f'takeaway-dot-{j}',86,y+23,22,'accent')+text(f'takeaway-num-{j}',str(j),86,y+31,23,'white',True,'layout',center=True)+slot(f'takeaway-title-{j}',f'TAKEAWAY_{j}',(132,y,252,49),30,'title',True)+slot(f'takeaway-detail-{j}',f'TAKEAWAY_DETAIL_{j}',(420,y,796,49),28)
 a+=slot('ending-question','ENDING_QUESTION',(64,605,1152,43),25,'muted');add(6,a)
def academic():
 a=line('cover-top-rule',64,111,1216,111,'accent',4)+slot('eyebrow','EYEBROW',(64,60,1000,38),20,'accent',True)+slot('title','TITLE',(64,209,690,184),64,'title',True,2,'title')+slot('subtitle','SUBTITLE',(64,428,690,108),28,'muted',lines=2)+slot('author','AUTHOR',(64,585,690,44),22,'muted')+line('cover-vertical',794,194,794,590,'rule',1)+rect('cover-formula-field',840,197,376,356,'surface2')
 a+=proxy('cover-visual',(860,225,336,274),graph('cover',(860,225,336,274)))+slot('caption','CAPTION',(840,575,376,68),22,'secondary',lines=2);add(0,a,{'CAPTION_1':'从生活情境出发','CAPTION_2':'建立函数模型'})
 a=heading('01 / 定义与参数')+rect('formula-field',64,206,1152,110,'surface')+slot('formula','FORMULA',(96,226,1088,74),48,'accent',True,center=True)
 for j,x in enumerate((64,460,856),1):a+=line(f'param-rule-{j}',x,358,x+348,358,'accent',3)+slot(f'param-{j}',f'PARAM_{j}',(x,382,348,57),30,'title',True)+slot(f'explain-{j}',f'EXPLAIN_{j}',(x,463,348,146),28,lines=3)
 add(1,a)
 a=heading('02 / 图像与解释')+proxy('teaching-visual',(64,227,542,350),graph('observation',(64,227,542,350),labels=True))+line('image-divider',642,214,642,580,'rule',1)
 for j,y in enumerate((224,350,476),1):a+=text(f'observation-number-{j}',f'0{j}',680,y+29,22,'accent',True,'layout')+slot(f'observe-title-{j}',f'OBS_TITLE_{j}',(736,y,480,47),30,'title',True)+slot(f'observe-body-{j}',f'OBS_BODY_{j}',(680,y+63,536,51),26,'muted')
 a+=slot('figure-caption','FIGURE_CAPTION',(64,605,1152,42),22,'muted');add(2,a,{'OBS_BODY_3':'y = −(x − 2)² + 4 对应此示意图'})
 a=heading('03 / 性质比较')+line('compare-midline',640,214,640,571,'rule',1)+slot('left-label','LEFT_LABEL',(64,213,544,54),30,'title',True)+slot('right-label','RIGHT_LABEL',(674,213,542,54),30,'title',True)
 a+=proxy('left-visual',(96,290,464,218),graph('up',(96,290,464,218),up=True))+proxy('right-visual',(706,290,464,218),graph('down',(706,290,464,218)))+slot('left-description','LEFT_DESCRIPTION',(64,535,544,49),26)+slot('right-description','RIGHT_DESCRIPTION',(674,535,542,49),26)+rect('conclusion-field',64,599,1152,49,'surface')+slot('conclusion','CONCLUSION',(82,602,1116,42),25,'accent',center=True);add(3,a)
 a=heading('04 / 方法与验证')+slot('intro','INTRO',(64,201,1152,54),28,'muted')
 for j,x in enumerate((64,460,856),1):a+=text(f'step-number-{j}',f'0{j}',x,329,48,'accent',True,'layout')+line(f'step-rule-{j}',x,354,x+346,354,'rule',1)+slot(f'step-title-{j}',f'STEP_TITLE_{j}',(x,384,352,54),32,'title',True)+slot(f'step-body-{j}',f'STEP_BODY_{j}',(x,458,352,144),28,lines=3)
 a+=slot('hint','HINT',(64,610,1152,40),23,'muted');add(4,a)
 a=heading('05 / 应用练习')+slot('question','QUESTION',(64,204,1152,105),31,'title',True,2)+line('exercise-rule',64,333,1216,333,'rule',1)
 for j,y in enumerate((360,442,524),1):a+=slot(f'task-{j}',f'TASK_{j}',(64,y,788,58),29)
 a+=line('hint-divider',884,361,884,580,'accent',3)+slot('hint-title','HINT_TITLE',(922,360,294,48),26,'accent',True)+slot('hint-body','HINT_BODY',(922,424,294,156),25,'muted',lines=4)+slot('practice-footer','PRACTICE_FOOTER',(64,609,1152,40),22,'muted');add(5,a)
 a=heading('06 / 结论与延伸')+slot('summary-lead','SUMMARY_LEAD',(64,222,1152,84),42,'accent',True)
 for j,y in enumerate((343,432,521),1):a+=line(f'summary-rule-{j}',64,y-17,1216,y-17,'rule',1)+text(f'takeaway-number-{j}',f'0{j}',64,y+30,23,'accent',True,'layout')+slot(f'takeaway-title-{j}',f'TAKEAWAY_{j}',(130,y,265,50),30,'title',True)+slot(f'takeaway-detail-{j}',f'TAKEAWAY_DETAIL_{j}',(421,y,795,50),28)
 a+=slot('ending-question','ENDING_QUESTION',(64,609,1152,40),25,'muted');add(6,a)
if PLAY:lively()
else:academic()
summary='以生活情境与图像探究组织课堂讲授、练习和复习' if PLAY else '以定义、图像证据和方法验证组织正式课堂讲授与教学汇报'
fm={'deck_id':STYLE,'kind':'deck','category':'scenario','summary':summary,'keywords':['教学','插画','情境'] if PLAY else ['教学','学术','正式'],'primary_color':C['accent'],'canvas_format':'ppt169','canvas_width':1280,'canvas_height':720,'canvas_viewbox':'0 0 1280 720','replication_mode':'standard','native_structure_mode':'structured','page_count':7,'placeholders':{Path(p['file']).stem:p['markers'] for p in P}}
spec='---\n'+yaml.safe_dump(fm,allow_unicode=True,sort_keys=False)+'---\n\n'+f'# {NAME} — Design Specification\n\n## I. Template Overview\n'
spec+=f'- 课件家族：{summary}。面向教师课堂投影与课后复习，示例为初三数学“二次函数”。\n- 代表角色包括情境封面、概念公式、图像解释、性质比较、方法步骤、课堂练习和总结延伸；不限定未来课件页数和顺序。\n- 配色、字体与版式为本轮设计师选择，用户已授权生成两套项目级模板供审阅。未提供机构标志，不加入虚构品牌。\n\n## II. Color Scheme\n| Role | HEX |\n|---|---|\n'
for k,v in C.items():spec+=f'| {k} | {v} |\n'
spec+='\n## III. Typography\n- 中文Microsoft YaHei，西文与数学记号Arial；封面64px，页标题44px，正文28–32px，图注22px，页脚18px；步骤标题32px，提示与延伸25px。\n\n## IV. Signature Design Elements\n'
spec+=('- 奶油底、橙色重点和青绿图线；圆角场景承载生活插图与公式。封面的可编辑篮球和抛物线建立生活情境，图文页左图右解释。\n- 圆编号连接探究任务，方法页连续线表达顺序；右侧青绿提示区承接练习，课堂小结使用共同背景联结结论。\n' if PLAY else '- 纸白底、深墨文字与酒红论点，蓝灰辅助图像；横线和开放列组织逻辑。\n- 封面采用独立图像窄栏，概念由公式引出参数，方法用编号和细线组织验证，结论按条理展开。\n')
spec+='- 一个Master统一背景与页脚，七个Layout的槽位或固定几何各不相同；复合图解使用object代理，文字使用文本槽。\n- 短公式、图注和页码允许居中，其他正文从框左上方书写；主体区止于650px，页脚线660px。\n- 插图为可替换的教学示例；曲线、数学文本可编辑，但不是可自动计算的统计图或公式对象。\n\n## V. Page Roster\n| SVG | Layout / picker | Slot frames |\n|---|---|---|\n'
for p in P:
 tree=ET.fromstring((T/p['file']).read_text(encoding='utf-8'));slots=[(g.get('id'),g.get('data-pptx-bounds')) for g in tree if g.get('data-pptx-placeholder')]
 spec+=f'| `{p["file"]}` | {STYLE}-{p["layout"]} / {p["name"]} | '+('; '.join(i+': '+b for i,b in slots))+' |\n'
spec+='\n## VII. Placeholder Overrides\n- frontmatter按basename声明语义标记，逐行解释与图注对应sample_content的键。\n'
(T/f'design_spec.deck.{STYLE}.md').write_text(spec,encoding='utf-8')
config={'schema_version':'1.0','template_id':STYLE,'template_version':'1.0.0','display_name':NAME,'status':'prototype','scope':'project','aspect_ratio':'16:9','slide_size':{'width_px':1280,'height_px':720,'width_in':13.333333,'height_in':7.5},'colors':C,'fonts':{'latin':'Arial','east_asian':'Microsoft YaHei'},'typography_px':{'cover_title':64,'title':44,'body':28,'caption':22,'footer':18},'layouts':[{'id':p['layout'],'name':p['name'],'source':'templates/'+p['file']} for p in P],'model_policy':{'one_template_per_deck':True,'preserve_unselected_slides':True,'overflow':'summarize_or_split','editable_pptx':True}}
(T/'tokens.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8');(R/'sample_content.json').write_text(json.dumps({'topic':'初三数学：二次函数','slides':P},ensure_ascii=False,indent=2),encoding='utf-8')
prompt=f'''# {NAME}：可复用提示词 v1.0.0

## 固定风格
使用{STYLE}@1.0.0设计16:9、1280×720课件。{summary}。背景{C['bg']}，标题{C['title']}，正文{C['body']}，强调{C['accent']}，辅助{C['secondary']}。
中文Microsoft YaHei、西文Arial；页标题44px、正文28–32px；遵循design_spec的空间语法、图像方向与容量，不只换颜色。
每页一个教学目标，插图服务理解；课堂情境不虚构成实测数据。

## 大纲生成
从需求和参考文件组织逐页教学目标、要点、图像建议及来源；用户可增删、排序与修改。七个版式是可复用角色，不限定页数。

## 单页生成
读取已确认大纲、tokens.json和选定SVG槽位。文字、公式文本和基础图形可编辑；图片仅占局部。内容过多先精简或拆页，不缩字号填塞。更换学科时替换样例图，不固定保留篮球、抛物线。

## 页面修改
只修改选定页，保留稳定页面ID、模板ID和版本，延续全局风格。以当前页面为依据，保留未选中页；教师手动修改直接保存。

## 推荐边界
自动推荐仅从已发布模板选择整份课件的一套风格。当前为待审阅prototype，尚未接入网站；离线样张不触发用户生成任务或积分消费。
'''
(T/'style_prompt.md').write_text(prompt,encoding='utf-8')
lock=f'# {NAME}样张结构锁定\n## typography\n- title: 44\n- body: 28\n- font_family: Arial, Microsoft YaHei\n- cover_title: 64\n- caption: 22\n- footer: 18\n- step_heading: 32\n- note: 25\n## colors\n'
for k,v in {'bg':C['bg'],'text':C['body'],'text_secondary':C['muted'],'primary':C['accent'],'accent':C['accent'],'secondary_accent':C['secondary'],'secondary_bg':C['surface'],'border':C['rule']}.items():lock+=f'- {k}: {v}\n'
lock+=f'## pptx_structure\n- mode: structured\n- template_adherence: strict\n- template_reuse_scope: layout\n## pptx_masters\n- {STYLE}: {NAME}\n## pptx_layouts\n'
for p in P:lock+=f'- {STYLE}-{p["layout"]}: {STYLE} | {p["name"]} | template:{Path(p["file"]).stem}\n'
lock+='## page_pptx_layouts\n'
for i,p in enumerate(P,1):lock+=f'- P{i:02d}: {STYLE}-{p["layout"]}\n'
lock+='## page_layouts\n'
for i,p in enumerate(P,1):lock+=f'- P{i:02d}: {Path(p["file"]).stem}\n'
(R/'spec_lock.md').write_text(lock,encoding='utf-8');print(json.dumps({'style':STYLE,'templates':len(P),'samples':len(P)},ensure_ascii=False))
