"""Original pixel art source. Run with Python/Pillow; no downloaded image layers.

Design: warm rural RPG, 64px transparent cells, 1px clusters, light from upper left.
Pixel Art Studio workflow: explicit palette, parameterized poses, inspect/revise/export.
"""
from pathlib import Path
from io import BytesIO
import argparse
import hashlib
import json
import math
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]

OUTLINE = '#49343d'
CREAM = '#f9dfaa'
SKINS = {
    'peach': ('#bc7968', '#e8aa85', '#ffcea2'),
    'tan': ('#945d52', '#c98c69', '#edb685'),
    'brown': ('#704952', '#a66e59', '#c48d6c'),
}
HAIRS = {
    'black': ('#353442', '#51404b', '#765253'),
    'brown': ('#65404a', '#895247', '#b77955'),
    'auburn': ('#7c4346', '#b1614c', '#db9864'),
    'gold': ('#a77548', '#d3a15b', '#f4ce84'),
    'gray': ('#776a76', '#a59696', '#d4c4b2'),
    'white': ('#a29396', '#d6c6b8', '#f4e5cb'),
}
CLOTHES = {
    'sage': ('#52675b', '#819665', '#b6bd80'),
    'blue': ('#455c78', '#64889c', '#99b6be'),
    'rose': ('#944f64', '#c97a7d', '#eaa28b'),
    'ochre': ('#a47046', '#d7a65c', '#f3ce83'),
    'teal': ('#456d70', '#619897', '#93c2b2'),
    'linen': ('#a6907a', '#ddc4a0', '#f4dfb6'),
    'rust': ('#874e45', '#b97452', '#d8a16c'),
    'plum': ('#654d70', '#95768f', '#b49ba6'),
    'ink': ('#434655', '#626f7b', '#92a0a1'),
}

def character(key, label, age, skin, hair, style, cloth, outfit, accessory=''):
    return dict(key=key, description=label, age=age, skin=skin, hair=hair, hairstyle=style, cloth=cloth, outfit=outfit, accessory=accessory)

CAST = [
    character('farmer_m', '草帽农夫：赭色衬衣、蓝背带裤', 'adult', 'tan', 'brown', 'short', 'ochre', 'overalls', 'strawhat'),
    character('farmer_f', '编辫农妇：绿衣、米色围裙', 'adult', 'peach', 'auburn', 'braid', 'sage', 'apron'),
    character('boy_blue', '蓝衣男孩：短发、短裤', 'child', 'peach', 'brown', 'tousled', 'blue', 'shorts'),
    character('girl_rose', '粉衣女孩：双马尾、背带裙', 'child', 'tan', 'black', 'twintails', 'rose', 'dress'),
    character('boy_sage', '绿衣男孩：深肤色、卷发、短裤', 'child', 'brown', 'black', 'curly', 'sage', 'shorts'),
    character('girl_gold', '金发女孩：波波头、紫裙', 'child', 'peach', 'gold', 'bob', 'plum', 'dress'),
    character('student_m', '少年学生：侧分短发、蓝色校服', 'adult', 'tan', 'black', 'parted', 'blue', 'vest'),
    character('student_f', '少女学生：长发、红棕裙装', 'adult', 'peach', 'brown', 'long', 'rust', 'dress'),
    character('teacher_m', '男教师：眼镜、米色开衫', 'adult', 'peach', 'brown', 'parted', 'linen', 'cardigan', 'glasses'),
    character('teacher_f', '女教师：盘发、紫色长裙', 'adult', 'brown', 'black', 'bun', 'plum', 'dress', 'glasses'),
    character('grandpa', '白胡子爷爷：灰发、青色开衫', 'elder', 'tan', 'white', 'balding', 'teal', 'cardigan', 'beard'),
    character('grandma', '银发奶奶：发髻、玫瑰色围裙', 'elder', 'peach', 'gray', 'bun', 'rose', 'apron'),
    character('doctor', '医生：短卷发、白外套', 'adult', 'brown', 'black', 'curly', 'linen', 'coat', 'stethoscope'),
    character('builder', '工人：安全帽、工作背带裤', 'adult', 'tan', 'black', 'short', 'rust', 'overalls', 'hardhat'),
    character('merchant', '商人：胡须、深蓝马甲', 'adult', 'tan', 'brown', 'parted', 'ink', 'vest', 'mustache'),
    character('scholar', '古风书生：束发、青蓝交领长衣', 'adult', 'peach', 'black', 'topknot', 'teal', 'robe'),
    character('village_girl', '古风少女：长辫、淡紫交领长衣', 'adult', 'tan', 'black', 'braid', 'plum', 'robe'),
    character('traveler', '旅人：红发、绿外套、背包', 'adult', 'peach', 'auburn', 'tousled', 'sage', 'jacket', 'backpack'),
    character('chef', '厨师：白厨师帽、暖色围裙', 'adult', 'brown', 'black', 'short', 'linen', 'apron', 'chefhat'),
    character('elder_scholar', '古风长者：灰髻、长须、米色长袍', 'elder', 'tan', 'gray', 'topknot', 'linen', 'robe', 'beard'),
]

ACTIONS = {}
for i, (name, count, loop, fps) in enumerate([
    ('idle', 3, True, 3), ('walk', 8, True, 9), ('run', 8, True, 12),
    ('pose', 3, False, 1), ('wave', 6, True, 7), ('nod', 4, False, 6),
    ('talk', 4, True, 5), ('pickup', 6, False, 7), ('carry', 8, True, 8),
    ('sit', 4, False, 5), ('jump', 6, False, 8), ('work', 6, True, 7),
]):
    ACTIONS[name] = dict(row=i*4, frames=count, loop=loop, fps=fps)
DIRECTIONS = ['up', 'left', 'down', 'right']


def draw_character(c, action, frame, direction):
    """Draw at native resolution; return sprite and exact visible hand anchors."""
    im = Image.new('RGBA', (64, 64))
    d = ImageDraw.Draw(im)
    child, elder = c['age'] == 'child', c['age'] == 'elder'
    skin0, skin1, skin2 = SKINS[c['skin']]
    hair0, hair1, hair2 = HAIRS[c['hair']]
    cloth0, cloth1, cloth2 = CLOTHES[c['cloth']]
    leg0, leg1 = '#4d5063', '#747b8b'
    shoe0, shoe1 = '#533e42', '#8a6150'
    side, back = direction in ('left', 'right'), direction == 'up'
    count = ACTIONS[action]['frames']
    cycle = [0, 1, 2, 1, 0, -1, -2, -1][frame % 8]
    moving = action in ('walk', 'run', 'carry')
    bob = -1 if moving and frame % 4 in (1, 2) else 0
    crouch, lift = 0, 0
    if action == 'idle': bob = (0, -1, 0)[frame]
    if action == 'nod': bob = (0, 1, 2, 0)[frame]
    if action == 'pickup': crouch = (0, 2, 5, 7, 4, 0)[frame]
    if action == 'sit': crouch = (0, 2, 5, 7)[frame]
    if action == 'jump':
        crouch = (2, 0, 0, 0, 2, 0)[frame]
        lift = (0, 3, 9, 5, 0, 0)[frame]
    feet_y = 59 - lift
    top = (29 if child else 22 if elder else 21) + bob + crouch - lift
    head_w = 13 if child else 14
    hx = 32-head_w//2
    hy = top
    face_bottom = hy+13
    sy = face_bottom+3
    hip = (51 if child else 49) + bob + crouch//2-lift
    body_w = 5 if child else 6
    if side:body_w -= 1
    torso_left,torso_right=32-body_w,32+body_w

    def rect(box, fill, outline=None):
        x0,y0,x1,y1=map(round,box)
        if x1>=x0 and y1>=y0:d.rectangle((x0,y0,x1,y1),fill=fill,outline=outline)
    def poly(points,fill,outline=None):d.polygon([(round(x),round(y)) for x,y in points],fill=fill,outline=outline)
    def line(points,fill,width=1):d.line([(round(x),round(y)) for x,y in points],fill=fill,width=width)
    def limb(points, material, highlight, hand=True):
        line(points,OUTLINE,5 if not child else 4)
        line(points,material,3 if not child else 2)
        ex,ey=points[-1]
        if hand:
            rect((ex-1,ey-1,ex+1,ey+1),skin1)
            d.point((round(ex),round(ey-1)),fill=skin2)
        else:line(points[:-1]+[(ex,ey-1)],highlight,1)
    def leg(x,offset,far=False):
        if side:
            endx=x+offset*(1.7 if action=='run' else 1.2)
            endy=feet_y-(1 if offset<0 else 0)
        else:endx=x;endy=feet_y+(-abs(offset)//2 if offset<0 else 0)
        if action=='sit' and frame>1:endx=x+3;endy=feet_y-2
        line([(x,hip-1),(x+(endx-x)*.3,hip+4),(endx,endy-2)],OUTLINE,5 if not child else 4)
        line([(x,hip),(x+(endx-x)*.3,hip+4),(endx,endy-2)],leg0 if far else leg1,3 if not child else 2)
        rect((endx-2,endy-2,endx+2,endy),shoe0)
        line([(endx-1,endy-2),(endx+1,endy-2)],shoe1)
    if side:
        leg(31,-cycle if moving else 0,True)
        leg(33,cycle if moving else 0)
    else:
        leg(29,-cycle if moving else 0,back)
        leg(35,cycle if moving else 0,not back)
    if c['hairstyle'] in ('long','braid','twintails'):
        poly([(hx,hy+6),(hx+head_w,hy+5),(hx+head_w+1,sy+6),(hx-1,sy+6)],hair0)
        rect((hx+1,hy+9,hx+3,sy+5),hair1)
    poly([(torso_left+2,sy-2),(torso_right-2,sy-2),(torso_right+1,hip),(torso_left-1,hip)],cloth0,OUTLINE)
    poly([(torso_left+2,sy-1),(torso_right-2,sy-1),(torso_right-1,hip-1),(torso_left+1,hip-1)],cloth1)
    rect((torso_left+2,sy,torso_left+3,hip-3),cloth2)
    if c['outfit'] in ('dress','robe'):
        poly([(torso_left+1,sy+4),(torso_right-1,sy+4),(torso_right+3,feet_y-3),(torso_left-3,feet_y-3)],cloth0,OUTLINE)
        poly([(torso_left+2,sy+5),(torso_right-2,sy+5),(torso_right,feet_y-4),(torso_left-1,feet_y-4)],cloth1)
        line([(29,sy+7),(27,feet_y-5)],cloth2)
        line([(torso_left,hip-1),(torso_right,hip-1)],'#b38a5a')
        if c['outfit']=='robe' and not back:
            line([(28,sy-1),(34,sy+6),(36,sy-1)],CREAM)
    elif c['outfit']=='overalls':
        rect((28,sy+4,36,hip),leg0);rect((29,sy+5,35,hip-1),leg1)
        line([(28,sy),(29,sy+6)],leg1,2);line([(36,sy),(35,sy+6)],leg1,2)
        d.point((29,sy+5),fill=CREAM);d.point((35,sy+5),fill=CREAM)
    elif c['outfit']=='apron':
        if back:
            line([(29,sy-1),(35,sy+6)],CREAM)
            line([(35,sy-1),(29,sy+6)],CREAM)
            line([(torso_left,hip-1),(torso_right,hip-1)],'#f4dfb6')
        else:
            rect((29,sy+3,35,hip+3),'#f4dfb6',OUTLINE)
            rect((30,sy+4,34,hip+2),'#f4dfb6')
            line([(30,hip-1),(34,hip-1)],'#c4ab88')
    elif c['outfit'] in ('vest','cardigan','coat','jacket') and not back:
        rect((31,sy-1,33,hip-2),CREAM)
        line([(28,sy-1),(30,sy+4),(29,hip-2)],cloth0)
        for yy in range(sy+3,hip-1,3):d.point((34,yy),fill=OUTLINE)
    if c['outfit']=='shorts':
        rect((27,hip-2,37,hip+3),leg0)
        if not side:
            for xx,step in [(29,-cycle),(35,cycle)]:
                end=feet_y-4-(abs(step)//2 if moving and step<0 else 0)
                if end>=hip+4:line([(xx,hip+4),(xx,end)],skin1,2)
    if c['accessory']=='backpack':
        if back:
            rect((26,sy-1,38,hip),OUTLINE);rect((27,sy,37,hip-1),'#ad784f')
            rect((28,sy+4,36,sy+8),'#d5a66c')
            line([(28,sy+1),(35,sy+1)],'#ecc693')
        elif side:
            rect((23,sy,28,hip),OUTLINE);rect((24,sy+1,27,hip-1),'#ad784f')
            line([(25,sy+3),(25,hip-2)],'#d5a66c')
        else:
            line([(28,sy-1),(28,sy+6)],'#ad784f',2)
            line([(36,sy-1),(36,sy+6)],'#ad784f',2)
    # Shoulders/hand endpoints are also exported for per-frame object contacts.
    left=(torso_left-1,sy+7);right=(torso_right+1,sy+7)
    if moving and action!='carry':
        left=(torso_left-1,sy+7+cycle);right=(torso_right+1,sy+7-cycle)
        if side:left=(30-cycle*2,sy+7);right=(35+cycle*2,sy+7)
    if action in ('carry','talk') or (action=='pose' and frame==1):
        left=(29,sy+5);right=(35+(frame%2 if action=='talk' else 0),sy+5)
        if side:left=(39,sy+5);right=(40,sy+5)
    if action=='wave':
        right=(43+(0,1,2,1,0,-1)[frame],sy-7+(0,-1,0,1,0,-1)[frame])
    if action=='pose' and frame==2:left=(22,sy-6);right=(42,sy-6)
    if action=='pickup':
        left=(28,sy+7+(0,0,1,2,1,0)[frame]);right=(37,sy+7+(0,0,1,2,1,0)[frame])
    if action=='work':
        reach=(0,2,5,7,4,1)[frame]
        left=(29,sy+3+reach//2);right=(38+reach//2,sy+2+reach)
    if action=='jump':left=(24,sy+4-lift//2);right=(40,sy+4-lift//2)
    if side:
        limb([(30,sy),(31,sy+3),left],cloth0,cloth1)
        limb([(35,sy),(36,sy+3),right],cloth1,cloth2)
    else:
        limb([(torso_left+1,sy),(torso_left-1,sy+3),left],cloth1,cloth2)
        limb([(torso_right-1,sy),(torso_right+1,sy+3),right],cloth0,cloth1)
    # Warm face clusters, with distinct profile/back constructions.
    poly([(hx+3,hy),(hx+head_w-3,hy),(hx+head_w,hy+3),(hx+head_w,hy+10),(hx+head_w-3,hy+14),(hx+3,hy+14),(hx,hy+10),(hx,hy+3)],hair0,OUTLINE)
    if back:
        poly([(hx+2,hy+3),(hx+head_w-2,hy+3),(hx+head_w-1,hy+10),(hx+head_w-4,hy+13),(hx+3,hy+12)],hair1)
        line([(hx+3,hy+4),(hx+5,hy+2),(hx+9,hy+2)],hair2)
        rect((30,hy+13,34,hy+15),skin0)
    elif side:
        poly([(hx+5,hy+4),(hx+head_w-1,hy+4),(hx+head_w,hy+8),(hx+head_w+2,hy+9),(hx+head_w,hy+11),(hx+head_w-1,hy+13),(hx+6,hy+13)],skin1,skin0)
        rect((hx+7,hy+5,hx+head_w-2,hy+8),skin2)
        rect((hx+head_w-2,hy+7,hx+head_w-2,hy+9),OUTLINE)
        rect((hx+4,hy+9,hx+6,hy+11),skin0)
        d.point((hx+head_w,hy+12),fill=skin0)
    else:
        poly([(hx+2,hy+4),(hx+head_w-2,hy+4),(hx+head_w-1,hy+10),(hx+head_w-4,hy+13),(hx+4,hy+13),(hx+1,hy+10)],skin1)
        rect((hx+3,hy+5,hx+head_w-4,hy+9),skin2)
        blink=action=='idle' and frame==2
        for ex in (hx+4,hx+head_w-4):
            rect((ex,hy+8,ex+1,hy+8+(0 if blink else 1)),OUTLINE)
        d.point((32,hy+11),fill=skin0)
        if action=='talk' and frame%2:rect((31,hy+12,32,hy+12),OUTLINE)
    # Hair volume and identifiable silhouettes; no external image layers.
    style=c['hairstyle']
    if style!='balding':
        poly([(hx+1,hy+5),(hx,hy+2),(hx+3,hy-1),(hx+head_w-4,hy-1),(hx+head_w,hy+2),(hx+head_w,hy+5),(hx+9,hy+3),(hx+6,hy+5),(hx+4,hy+3)],hair0,OUTLINE)
        line([(hx+2,hy+2),(hx+4,hy),(hx+9,hy)],hair2)
        rect((hx+2,hy+2,hx+5,hy+3),hair1)
    if style in ('tousled','curly'):
        for xx,yy in ((hx+1,hy-1),(hx+5,hy-2),(hx+10,hy-1)):
            rect((xx,yy,xx+3,yy+3),hair0)
            d.point((xx+1,yy),fill=hair2)
    if style=='bob':
        rect((hx-1,hy+4,hx+2,hy+13),hair0);rect((hx+head_w-2,hy+4,hx+head_w+1,hy+13),hair0)
        line([(hx,hy+5),(hx,hy+10)],hair2)
    if style in ('bun','topknot'):
        rect((29,hy-5,35,hy),OUTLINE);rect((30,hy-4,34,hy-1),hair1)
        line([(30,hy-4),(33,hy-4)],hair2)
        if style=='topknot':line([(28,hy+1),(36,hy+1)],'#ad784f')
    if style=='twintails':
        for xx in (hx-3,hx+head_w):
            poly([(xx,hy+5),(xx+3,hy+4),(xx+4,hy+10),(xx+2,hy+15),(xx,hy+13)],hair0,OUTLINE)
            rect((xx+1,hy+5,xx+3,hy+6),cloth2)
    if style=='long':
        line([(hx,hy+7),(hx-1,sy+7)],hair1,2)
        line([(hx+head_w,hy+7),(hx+head_w+1,sy+7)],hair0,2)
    if style=='braid':
        xx=hx+head_w+1
        for yy in range(hy+8,sy+9,3):
            rect((xx,yy,xx+2,yy+2),hair1 if yy%2 else hair0)
        line([(xx,sy+9),(xx+2,sy+9)],cloth2)
    if style=='balding':
        rect((hx+3,hy+1,hx+head_w-3,hy+5),skin2)
        line([(hx+1,hy+5),(hx+2,hy+9)],hair2,2)
        line([(hx+head_w-1,hy+5),(hx+head_w-2,hy+9)],hair1,2)
    accessory=c['accessory']
    if accessory in ('strawhat','hardhat','chefhat'):
        hat0,hat1,hat2=('#a77b46','#dbb56b','#f3d893') if accessory!='chefhat' else ('#b4a5a1','#e8dbbe','#fff0d0')
        rect((hx-3,hy+1,hx+head_w+3,hy+3),OUTLINE)
        rect((hx-2,hy+1,hx+head_w+2,hy+2),hat1)
        poly([(hx+1,hy+1),(hx+2,hy-5),(hx+head_w-2,hy-5),(hx+head_w,hy+1)],hat0,OUTLINE)
        rect((hx+3,hy-4,hx+head_w-3,hy-1),hat1)
        line([(hx+3,hy-4),(hx+head_w-3,hy-4)],hat2)
        if accessory=='strawhat':line([(hx+1,hy),(hx+head_w,hy)],'#a85f48')
        if accessory=='hardhat':
            # Rounded protective helmet, visibly different from the farmer hat.
            d.rectangle((hx-3,hy-8,hx+head_w+3,hy+3),fill=(0,0,0,0))
            d.rounded_rectangle((hx,hy-6,hx+head_w,hy+2),radius=5,fill='#d7a65c',outline=OUTLINE)
            line([(32,hy-5),(32,hy)],'#f3ce83',2)
            rect((hx-2,hy+1,hx+head_w+2,hy+3),'#a47046',OUTLINE)
        if accessory=='chefhat':
            for xx in (hx+1,hx+5,hx+9):d.ellipse((xx,hy-8,xx+6,hy-2),fill=hat2,outline=hat0)
    if accessory=='glasses' and not back:
        if side:rect((hx+head_w-4,hy+7,hx+head_w,hy+10),None,OUTLINE)
        else:
            rect((hx+2,hy+7,hx+6,hy+10),None,OUTLINE);rect((hx+8,hy+7,hx+12,hy+10),None,OUTLINE)
            line([(hx+6,hy+8),(hx+8,hy+8)],OUTLINE)
    if accessory in ('beard','mustache') and not back:
        if accessory=='beard':
            poly([(28,hy+11),(36,hy+11),(35,hy+16),(32,hy+18),(29,hy+15)],hair0)
            poly([(29,hy+12),(35,hy+12),(32,hy+16)],hair2)
        else:line([(29,hy+11),(32,hy+10),(35,hy+11)],hair0,2)
    if accessory=='stethoscope' and not back:
        line([(29,sy),(29,sy+5),(34,sy+5),(35,sy)],'#626f7b')
        rect((34,sy+5,35,sy+6),OUTLINE)
    if direction=='left':
        im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        left=(63-left[0],left[1]);right=(63-right[0],right[1])
    # Hands are restored last so attachment points coincide with visible skin pixels.
    for x,y in (left,right):
        if im.getpixel((round(x),round(y)))[3]==0:
            ImageDraw.Draw(im).rectangle((round(x)-1,round(y)-1,round(x)+1,round(y)+1),fill=skin1)
    return im, [[round(x),round(y)] for x,y in (left,right)]


def draw_objects():
    result={}
    def canvas(key,w,h):
        im=Image.new('RGBA',(w,h));result[key]=im;return ImageDraw.Draw(im)
    d=canvas('tree',64,96)
    d.polygon([(26,47),(39,47),(38,86),(45,91),(22,91),(28,84)],fill='#765348',outline=OUTLINE)
    d.polygon([(29,49),(34,48),(34,86),(29,88)],fill='#bc885e')
    for box,col in [((7,23,57,68),'#4d6b51'),((1,17,49,57),'#658557'),((15,3,62,49),'#76915d'),((12,6,49,43),'#94a866')]:d.ellipse(box,fill=col,outline='#4d6b51')
    for x,y in [(13,25),(24,12),(35,17),(44,34)]:d.rectangle((x,y,x+8,y+3),fill='#bdc27b')
    d=canvas('grass',48,16)
    for x,y in [(3,9),(15,5),(27,10),(39,7)]:
        d.line([(x,y+5),(x-2,y),(x+1,y+3),(x+3,y-3),(x+3,y+5)],fill='#77965b',width=2)
        d.point((x+2,y-2),fill='#bfca80')
    d=canvas('dirt',32,32);d.rectangle((0,0,31,31),fill='#c5a277')
    for x,y in [(4,7),(15,20),(25,4),(29,26),(9,28)]:d.line([(x,y),(x+2,y)],fill='#ac8766')
    d=canvas('rock',32,32)
    d.polygon([(4,25),(2,18),(9,8),(23,6),(29,16),(27,26)],fill='#807d80',outline=OUTLINE)
    d.polygon([(6,17),(11,10),(21,9),(26,16),(17,19)],fill='#b4b0a4')
    d=canvas('barrel',32,40)
    d.rounded_rectangle((5,3,27,37),radius=5,fill='#b58157',outline=OUTLINE)
    for x in [9,16,23]:d.line([(x,5),(x,35)],fill='#7e5949')
    for y in [9,28]:d.rectangle((5,y,27,y+3),fill='#777d83',outline=OUTLINE)
    d=canvas('bucket',24,28);d.arc((4,1,20,19),180,360,fill=OUTLINE,width=2)
    d.polygon([(3,10),(21,10),(18,26),(6,26)],fill='#9c9a97',outline=OUTLINE);d.line([(6,12),(8,23)],fill='#ddd3bb',width=2)
    d=canvas('bridge',96,48)
    for x in range(5,94,9):d.polygon([(x,13),(x+8,13),(x+8,38),(x,38)],fill='#c29b69',outline='#856248')
    for y in (8,34):d.rectangle((2,y,94,y+4),fill='#8f694f',outline=OUTLINE)
    for x in (4,88):d.rectangle((x,2,x+4,44),fill='#bb8e5b',outline=OUTLINE)
    d=canvas('water_ripple',48,16)
    for x,y in [(2,4),(15,9),(32,3)]:d.line([(x,y),(x+6,y),(x+8,y-1),(x+12,y-1)],fill='#98c3b7')
    d=canvas('house',96,96)
    d.rectangle((13,38,83,89),fill='#ddc49b',outline=OUTLINE)
    d.polygon([(5,43),(46,9),(91,43)],fill='#975c50',outline=OUTLINE)
    for y in (24,32,40):d.line([(49-(y-9)*1.2,y),(45+(y-9)*1.3,y)],fill='#c78760',width=2)
    d.rectangle((41,59,60,89),fill='#8f6652',outline=OUTLINE);d.point((55,76),fill=CREAM)
    for x in (21,67):
        d.rectangle((x,54,x+11,68),fill='#68929a',outline=OUTLINE);d.line([(x,61),(x+11,61)],fill=CREAM);d.line([(x+5,54),(x+5,68)],fill=CREAM)
    d=canvas('book',20,16);d.polygon([(2,2),(9,4),(17,2),(17,13),(9,15),(2,13)],fill=CREAM,outline=OUTLINE);d.line([(9,4),(9,14)],fill='#c5a277')
    d=canvas('basket',24,24);d.arc((4,0,20,20),180,360,fill='#8f6652',width=2);d.polygon([(2,10),(22,10),(19,22),(5,22)],fill='#c99c63',outline=OUTLINE)
    for y in (14,18):d.line([(4,y),(20,y)],fill='#956c4d')
    d=canvas('flower',16,24);d.line([(8,7),(8,23)],fill='#6c8956',width=2);d.ellipse((3,2,12,11),fill='#d78a81',outline='#a85f67');d.rectangle((6,5,9,8),fill='#f6d386')
    return result


def font(size):
    p=Path('C:/Windows/Fonts/msyh.ttc')
    return ImageFont.truetype(BytesIO(p.read_bytes()),size) if p.exists() else ImageFont.load_default(size=size)


def build(destination):
    destination.mkdir(parents=True,exist_ok=True)
    manifest=dict(schema_version=1,art_origin='original-local-pixel-art',version='original-cast-1',license='Original project assets; no third-party image layers',cell=64,foot_origin=[32,60],directions=DIRECTIONS,actions=ACTIONS,characters={},aliases={'ochre':'farmer_m','teal':'scholar','linen':'grandpa'},contacts={},catalog={},files={})
    previews=[]
    for c in CAST:
        sheet=Image.new('RGBA',(512,64*4*len(ACTIONS)))
        contacts={}
        for action,spec in ACTIONS.items():
            contacts[action]=[]
            for direction_index,direction in enumerate(DIRECTIONS):
                row=[]
                for frame in range(spec['frames']):
                    im,hands=draw_character(c,action,frame,direction)
                    sheet.alpha_composite(im,(frame*64,(spec['row']+direction_index)*64))
                    row.append(hands)
                contacts[action].append(row)
        # Geometry is identical within each age; clothing and hair are independent.
        manifest['contacts'].setdefault(c['age'],contacts)
        path=destination/(c['key']+'.png')
        # Lossless indexed PNG keeps all exact colors/alpha with smaller offline payloads.
        sheet.quantize(method=Image.Quantize.FASTOCTREE,colors=64,dither=Image.Dither.NONE).save(path,optimize=True)
        manifest['characters'][c['key']]={**c,'file':path.name,'cell':64,'foot_origin':[32,60],'directions':DIRECTIONS}
        manifest['catalog'][c['key']]=dict(file=path.name,width=sheet.width,height=sheet.height,kind='character')
        previews.append(draw_character(c,'idle',0,'down')[0])
    for key,im in draw_objects().items():
        p=destination/(key+'.png');im.save(p,optimize=True)
        manifest['catalog'][key]=dict(file=p.name,width=im.width,height=im.height,kind='object')
    credits=('Original local pixel art - Edu Video - 2026-10-20\n'
        'All character and object pixels were newly authored by a deterministic Python/Pillow build.\n'
        'Art origin: original-local-pixel-art. No Stardew Valley or LPC image assets used.\n'
        'Visual direction: warm rural RPG palette, compact proportions, clean native pixel clusters.\n'
        'Source: pixel-art/original-cast/build.py; Skill workflow: Gamezxz/pixel-art-studio (MIT).\n'
        'This record describes provenance and does not assert exclusive copyright in AI-assisted output.\n')
    (destination/'CREDITS.txt').write_text(credits,encoding='utf-8')
    for p in sorted(destination.iterdir()):
        if p.is_file() and p.name!='manifest.json':manifest['files'][p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
    (destination/'manifest.json').write_text(json.dumps(manifest,separators=(',',':'),ensure_ascii=False),encoding='utf-8')
    preview=Image.new('RGB',(1280,920),'#f4eddd');d=ImageDraw.Draw(preview)
    d.text((30,20),'原创像素人物 · 暖色乡村 RPG',font=font(29),fill=OUTLINE)
    d.text((32,63),'20 种角色 / 四方向 / 11 种动态动作 / 透明图集 / 本地可重新绘制',font=font(17),fill='#7b7063')
    for index,(c,tile) in enumerate(zip(CAST,previews)):
        x=24+(index%5)*252;y=111+(index//5)*197
        d.rounded_rectangle((x,y,x+238,y+181),radius=10,fill='#e1e4cd')
        tile=tile.resize((192,192),Image.Resampling.NEAREST)
        preview.paste(tile,(x+22,y-36),tile)
        d.text((x+12,y+147),c['description'].split('：')[0],font=font(19),fill=OUTLINE)
    preview.save(destination.parent/'cast-preview.png')
    gifs=[]
    labels=[('walk','行走'),('run','跑步'),('wave','挥手'),('nod','点头'),('talk','说话'),('pickup','拾取'),('carry','端物走'),('sit','坐下'),('jump','跳跃'),('work','劳动')]
    for f in range(48):
        im=Image.new('RGB',(1280,600),'#f4eddd');d=ImageDraw.Draw(im)
        d.text((25,16),'原创动作检查 · 蓝衣男孩 / 草帽农夫',font=font(25),fill=OUTLINE)
        for row,c in enumerate([CAST[2],CAST[0]]):
            for col,(action,label) in enumerate(labels):
                x=13+col*126;y=83+row*244
                d.rounded_rectangle((x,y,x+119,y+212),radius=8,fill='#e1e4cd')
                spec=ACTIONS[action];idx=(f//2)%spec['frames'] if spec['loop'] else min(f%24//3,spec['frames']-1)
                tile=draw_character(c,action,idx,'down')[0].resize((192,192),Image.Resampling.NEAREST)
                im.paste(tile,(x-35,y-16),tile)
                d.text((x+15,y+179),label,font=font(16),fill=OUTLINE)
        gifs.append(im)
    gifs[0].save(destination.parent/'actions-preview.gif',save_all=True,append_images=gifs[1:],duration=100,loop=0,disposal=2)
    gifs[6].save(destination.parent/'actions-preview.png')
    report={'characters':len(CAST),'actions':len(ACTIONS)-1,'directions':4,'files':len(manifest['files']),'png_bytes':sum(p.stat().st_size for p in destination.glob('*.png')),'manifest_bytes':(destination/'manifest.json').stat().st_size}
    (destination.parent/'build-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=Path(__file__).with_name('generated'))
    build(parser.parse_args().out)
