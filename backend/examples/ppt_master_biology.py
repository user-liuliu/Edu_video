"""No-provider illustrated fixture: exercise the same authoring and export runtime."""
import json
import sys
from pathlib import Path
from uuid import uuid4
from xml.etree.ElementTree import Element,SubElement,tostring,register_namespace
from app.presentations.master_runtime import compile_deck,preview,NS

register_namespace('',NS)
OUT=Path(sys.argv[1] if len(sys.argv)>1 else 'ppt-master-biology');OUT.mkdir(parents=True,exist_ok=True)
COL={'navy':'#173359','blue':'#2465D9','green':'#2B9578','mint':'#DDEFE4','yellow':'#F9CD53','body':'#273B53','muted':'#61738A','line':'#DCE5F1','paper':'#F4F7FC'}
def el(parent,tag,**attrs):return SubElement(parent,'{'+NS+'}'+tag,{k.replace('_','-'):str(v) for k,v in attrs.items()})
def text(parent,x,y,value,size=28,color='body',**attrs):
    size={20:22,23:22,24:22,25:22,26:28,30:32,36:32,44:48}.get(size,size)
    node=el(parent,'text',x=x,y=y,font_size=size,fill=COL.get(color,color),**attrs);node.text=value;return node
def path(parent,d,fill='none',stroke='green',width=3):return el(parent,'path',d=d,fill=COL.get(fill,fill),stroke=COL.get(stroke,stroke),stroke_width=width)
def line(parent,x1,y1,x2,y2,color='blue',width=3):return el(parent,'line',x1=x1,y1=y1,x2=x2,y2=y2,stroke=COL[color],stroke_width=width)
def arrow(parent,x1,y1,x2,y2,color='blue'):
    import math
    line(parent,x1,y1,x2,y2,color,4);a=math.atan2(y2-y1,x2-x1);d=14
    pts=[(x2,y2),(x2-d*math.cos(a-.5),y2-d*math.sin(a-.5)),(x2-d*math.cos(a+.5),y2-d*math.sin(a+.5))]
    el(parent,'polygon',points=' '.join(str(round(x,1))+','+str(round(y,1)) for x,y in pts),fill=COL[color])
def leaf(parent,cx,cy,w=250,h=170,fill='mint'):
    path(parent,f'M {cx-w/2} {cy+h/2} C {cx-w/2} {cy-h} {cx+w/2} {cy-h} {cx+w/2} {cy-h/2} C {cx+w/2} {cy+h/2} {cx} {cy+h} {cx-w/2} {cy+h/2} Z',fill)
    path(parent,f'M {cx-w/2-20} {cy+h/2+20} L {cx+w/2-25} {cy-h/2+25}',width=4)
    for dx,dy in [(-50,-28),(5,-50),(55,-55)]:
        line(parent,cx+dx-25,cy-dx*.45+15,cx+dx-55,cy-dx*.45+dy,'green',2)
        line(parent,cx+dx-25,cy-dx*.45+15,cx+dx+28,cy-dx*.45+50,'green',2)
def sun(parent,cx,cy,r=35):
    import math
    el(parent,'circle',cx=cx,cy=cy,r=r,fill=COL['yellow'])
    for i in range(8):
        a=i*math.pi/4;line(parent,round(cx+(r+9)*math.cos(a),1),round(cy+(r+9)*math.sin(a),1),round(cx+(r+22)*math.cos(a),1),round(cy+(r+22)*math.sin(a),1),'yellow',4)
def page(number,title,subtitle,takeaway):
    root=Element('{'+NS+'}svg',{'width':'1280','height':'720','viewBox':'0 0 1280 720','font-family':'Microsoft YaHei, Arial','data-pptx-page-role':'cover' if number==1 else 'ending' if number==7 else 'content'})
    el(root,'rect',id='background',data_pptx_role='background',width=1280,height=720,fill='#FFFFFF')
    head=el(root,'g',id='heading',data_pptx_bounds='64 42 1152 125')
    text(head,64,64,'自然科学 / 生物课堂',20,'blue',font_weight='bold')
    text(head,64,122,title,44,'navy',font_weight='bold')
    text(head,64,163,subtitle,24,'muted')
    visual=el(root,'g',id='teaching-visual',data_pptx_bounds='64 190 1152 420')
    foot=el(root,'g',id='takeaway',data_pptx_bounds='64 634 1152 52')
    el(foot,'rect',x=64,y=634,width=1152,height=52,rx=10,fill=COL['paper'])
    text(foot,84,669,takeaway,24,'navy');text(foot,1180,669,f'{number:02}',22,'blue')
    return root,visual

PAGES=[]
def save(root,title,content,brief,composition,layout='image-text'):
    sid=str(uuid4());svg=tostring(root,encoding='unicode')
    page={'id':sid,'title':title,'content':content,'layout':layout,'slots':{},'renderer':'ppt-master-6.7.0','svg':svg,'design':{'id':sid,'visual_kind':'diagram','visual_brief':brief,'composition':composition}}
    PAGES.append(page);(OUT/f'P{len(PAGES):02}.svg').write_bytes(preview(svg,{}))

r,g=page(1,'一片叶子的能量之旅','从一片叶子出发，追踪光能和物质的去向','课堂任务：用图解解释植物如何制造有机物。')
sun(g,820,260,42);leaf(g,900,440,330,200);arrow(g,840,325,880,365)
text(g,100,290,'阳光去了哪里？',36,'navy',font_weight='bold')
text(g,100,353,'植物的生长，需要原料，也需要能量。',28)
text(g,100,415,'观察 → 提问 → 实验 → 解释',28,'blue')
text(g,750,600,'光能转化为储存在有机物中的化学能',24,'green')
save(r,'一片叶子的能量之旅','以叶片为线索认识光合作用','太阳、叶片、光能输入箭头','左侧提问，右侧大幅叶片与太阳', 'cover')

r,g=page(2,'光合作用：原料、条件与产物','把反应关系画出来，区分“物质”和“能量”','二氧化碳和水是原料；光提供能量，叶绿体是主要场所。')
leaf(g,640,425,250,150);sun(g,640,240,30);arrow(g,640,285,640,325)
text(g,390,235,'光',26,'green');text(g,515,575,'叶片（含叶绿体）',28,'green')
for x,y,label in [(105,340,'二氧化碳'),(105,480,'水'),(1010,340,'有机物'),(1010,480,'氧气')]:
    text(g,x,y,label,30,'navy',font_weight='bold')
arrow(g,260,335,470,375);arrow(g,185,475,470,450);arrow(g,795,375,975,335);arrow(g,795,450,975,475)
text(g,85,555,'原料进入',24,'muted');text(g,1020,555,'产物形成',24,'muted')
save(r,'光合作用：原料、条件与产物','二氧化碳、水、光与叶绿体，有机物和氧气','叶片中心与四条输入输出箭头','中心叶片，左原料右产物，上方光能','concept')

r,g=page(3,'从叶片出发，追踪物质的流动','沿着箭头说明：物质从哪里来，又到哪里去？','水经根和导管到达叶片，二氧化碳通过气孔进入。')
path(g,'M 820 550 L 820 315',stroke='green',width=10);leaf(g,905,355,180,110);leaf(g,730,420,155,100)
for dx in [-75,-40,0,40,75]:path(g,f'M 820 550 Q {820+dx/2} 575 {820+dx} 600',stroke='green',width=4)
line(g,590,550,1110,550,'line',3);arrow(g,790,530,790,350);text(g,635,520,'水向上运输',24,'blue')
arrow(g,1140,320,1035,350);text(g,1040,280,'二氧化碳',24,'blue')
arrow(g,1020,390,1140,420);text(g,1080,465,'氧气',24,'green')
for y,a,b in [(270,'根吸收水','水经导管运到叶片'),(390,'气孔交换气体','二氧化碳进入，氧气释放'),(510,'有机物被利用','支持植物生长与呼吸')]:
    text(g,95,y,a,30,'navy',font_weight='bold');text(g,95,y+45,b,25)
save(r,'从叶片出发，追踪物质的流动','根、导管和气孔参与物质运输','带根系的植物、导管和气体流向','左侧解释，右侧整株植物示意图')

r,g=page(4,'光合作用与呼吸作用：能量如何变化？','同一株植物同时需要制造有机物和释放能量','植物既进行光合作用，也进行呼吸作用。')
line(g,640,230,640,585,'line',2)
text(g,100,235,'光合作用 · 储存能量',32,'navy',font_weight='bold');leaf(g,330,405,190,120);sun(g,185,310,24);arrow(g,225,330,275,355)
text(g,100,565,'主要在叶绿体中进行，需要光。',25)
text(g,700,235,'呼吸作用 · 释放能量',32,'navy',font_weight='bold')
path(g,'M 835 325 C 1010 275 1110 375 1065 460 C 1000 525 830 490 820 410 C 815 375 815 345 835 325 Z','mint')
for i in range(4):path(g,f'M {855+i*40} 350 Q {830+i*40} 385 {865+i*40} 410 Q {890+i*40} 440 {860+i*40} 465',stroke='green',width=4)
arrow(g,1090,380,1170,380);text(g,1110,440,'能量',24,'blue')
text(g,700,565,'白天和夜晚都能进行。',25)
save(r,'光合作用与呼吸作用：能量如何变化？','光合作用储存能量，呼吸作用释放能量','叶绿体/叶片与线粒体轮廓，对比能量方向','左右对比图，两侧均有实物结构示意','compare')

r,g=page(5,'怎样验证叶片在光下产生淀粉？','设置同一叶片的见光与遮光区域，比较实验现象','酒精脱色由教师采用水浴处理；用碘液比较叶片颜色。')
for x,n,label in [(100,'01','暗处理、遮光'),(490,'02','光照、脱色'),(880,'03','滴碘液、比较')]:
    text(g,x,245,n,28,'blue',font_weight='bold');text(g,x+55,245,label,28,'navy',font_weight='bold')
leaf(g,250,405,180,120);path(g,'M 215 335 L 270 312 L 295 440 L 240 465 Z','navy','navy',1)
sun(g,590,330,23);path(g,'M 690 330 L 690 475 Q 690 500 715 500 L 755 500 Q 780 500 780 475 L 780 330',stroke='blue',width=4)
path(g,'M 665 405 L 665 520 L 805 520 L 805 405',stroke='navy',width=4);line(g,670,465,800,465,'blue',3)
leaf(g,1020,410,165,100,'navy');path(g,'M 990 350 L 1035 330 L 1065 445 L 1020 465 Z','paper','paper',1)
arrow(g,355,400,465,400);arrow(g,795,400,875,400)
text(g,100,575,'消耗原有淀粉，设置对照。',23);text(g,490,575,'教师操作，漂洗后滴碘液。',23);text(g,880,575,'见光区蓝黑；遮光区不变蓝。',23)
save(r,'怎样验证叶片在光下产生淀粉？','暗处理遮光，光照后教师酒精水浴脱色，漂洗滴碘液比较','遮光叶片、水浴装置与碘液检验叶片','三段实验顺序，使用真实装置轮廓','process')

r,g=page(6,'轮到你：遮光区域为什么不变蓝？','先描述现象，再把现象和光合作用联系起来','尝试用“控制条件 → 观察现象 → 得出结论”组织回答。')
sun(g,380,280,32);leaf(g,330,445,270,170);path(g,'M 290 340 L 350 320 L 410 510 L 350 540 Z','navy','navy',1)
arrow(g,260,545,160,590);text(g,78,600,'见光区域',24,'blue');arrow(g,360,445,535,490);text(g,520,535,'遮光区域',24,'navy')
text(g,740,280,'请回答',32,'navy',font_weight='bold')
for y,label in [(355,'① 实验中改变的条件是什么？'),(430,'② 哪个区域产生了淀粉？'),(505,'③ 这个结果支持什么结论？')]:text(g,740,y,label,26)
save(r,'轮到你：遮光区域为什么不变蓝？','观察见光与遮光区域，解释淀粉实验','同一叶片遮光带与区域引线','左侧大图，右侧三道思考问题','practice')

r,g=page(7,'用一张图，讲清一片叶子的能量之旅','用原料、条件、产物和用途四个线索复述今天的内容','用自己的话解释：光能怎样变成植物生长所需的物质和能量？')
leaf(g,640,400,250,160);sun(g,640,240,26);arrow(g,640,285,640,310)
text(g,90,310,'原料',30,'navy',font_weight='bold');text(g,90,360,'二氧化碳 + 水',28);arrow(g,300,370,475,395)
text(g,965,310,'产物',30,'navy',font_weight='bold');text(g,940,360,'有机物 + 氧气',28);arrow(g,805,395,930,375)
arrow(g,640,510,640,570);text(g,450,600,'生长 · 储存物质 · 呼吸供能',28,'green')
text(g,760,245,'光与叶绿体',26,'green')
save(r,'用一张图，讲清一片叶子的能量之旅','总结光合作用的原料条件产物和用途','植物光合作用的闭合知识图解','中心叶片、左输入右输出、下方用途','summary')

(OUT/'pages.json').write_text(json.dumps(PAGES,ensure_ascii=False,indent=2),encoding='utf-8')
data=compile_deck(PAGES,'一片叶子的能量之旅',{},output_workspace=OUT/'project')
(OUT/'illustrated-biology.pptx').write_bytes(data)
print(json.dumps({'pages':len(PAGES),'bytes':len(data),'output':str(OUT)},ensure_ascii=False))
