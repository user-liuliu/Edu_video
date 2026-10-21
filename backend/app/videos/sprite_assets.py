"""Original, reproducible offline pixel cast for model-authored stories."""
import base64
import hashlib
import json
import re
from pathlib import Path, PurePosixPath

ASSET_ROOT = Path(__file__).with_name('sprite_assets')
RUNTIME = Path(__file__).with_name('sprite_motion.js')
MARKER = '/*__EDU_SPRITES__*/'


def load_bundle(*, root=ASSET_ROOT):
    root = Path(root).resolve()
    try:
        raw = (root / 'manifest.json').read_bytes()
        if len(raw) > 64000: raise ValueError('素材清单过大')
        manifest = json.loads(raw)
        files = manifest['files']
        if manifest['schema_version'] != 1 or not 1 <= len(files) <= 64:
            raise ValueError('素材清单无效')
        contents = {}
        for relative, expected in files.items():
            path = PurePosixPath(relative)
            if path.is_absolute() or '..' in path.parts or chr(92) in relative or ':' in relative:
                raise ValueError('素材路径无效')
            target = (root / relative).resolve()
            if not target.is_relative_to(root) or target.stat().st_size > 160000:
                raise ValueError('素材路径或大小无效')
            data = target.read_bytes()
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError('素材完整性校验失败')
            contents[relative] = data
        for item in manifest['catalog'].values():
            data = contents[item['file']]
            if not data.startswith(b'\x89PNG\r\n\x1a\n') or (int.from_bytes(data[16:20]),int.from_bytes(data[20:24])) != (item['width'],item['height']):
                raise ValueError('素材图集尺寸无效')
        if 'CREDITS.txt' not in contents: raise ValueError('素材缺少署名')
        return manifest, contents, hashlib.sha256(raw).hexdigest()
    except (OSError, KeyError, TypeError, UnicodeError, json.JSONDecodeError):
        raise ValueError('素材来源或完整性校验失败') from None


def sprite_guidance():
    manifest, _, digest = load_bundle()
    return {
        'version': manifest['version'], 'digest': digest,
        'characters': {
            key: {k:item[k] for k in ('description','age','outfit','hairstyle','cloth','cell','foot_origin','directions')}
            for key,item in manifest['characters'].items()},
        'character_policy': {'required':True,'missing':'nearest_available',
                             'scientific_graphics':'native_vector_canvas',
                             'selection_priority':['age','outfit','hairstyle','cloth']},
        'environment': {key:{'width':item['width'],'height':item['height'],'kind':'ready_to_draw_object'} for key,item in manifest['catalog'].items() if item.get('kind')=='object'},
        'actions': {key:{k:v for k,v in item.items() if k!='row'} for key,item in manifest['actions'].items()},
        'integration': [
            '程序在head注入全局EduSprites；不要复制实现、new Image、编码图片或使用外部链接。可留/*__EDU_SPRITES__*/标记。所有调用在同步renderFrame(t)中或纯函数中。人物drawActor直接绘制到已挂载在舞台的可见Canvas，不先画到未挂载离屏Canvas；背景或科学图形可单独分层。',
            '故事人物必须使用此目录的完整角色并通过EduSprites.drawActor绘制，不再自行拼接身体、袖子或关节。先为每个人物选择最接近的素材并全片复用；缺少完全匹配的角色时依次按年龄、服装身份、发型、配色近似，接受古装等细节差异，不因不匹配而重新绘制。字幕、道具和情节表达具体身份。',
            '未知variant可传fallback_variant指定目录中的近似角色；也可提供age:"child"/"adult"/"elder"和outfit等目录属性，由actor选择近似素材。例如古代儿童仍选儿童而不是缩小成人。公式、函数图像、实验器材及标注继续原生SVG/Canvas清晰绘制，不放入低分辨率像素画布；混合影片只让故事人物和故事场景采用像素。',
            '全片用同一角色定义，稳定四方向；站立时固定朝向，只有面向对象改变才转身，不按时间反复左右翻转。不旋转、拉伸或拆分精灵肢体。',
            'EduSprites.travel({points:[{x:200,y:460},{x:350,y:460},{x:400,y:500}],start:2,end:8,stride:32,startDirection:"right",endDirection:"down"},t)返回x,y,direction,action,frame,distance。x,y是脚底。整次连续行走使用完整路径一个时段，不在拐点停步或重置步态；停顿才拆开。stride是一个8帧步态的世界像素距离，人物scale变化时按32*scale调整。',
            'const a=EduSprites.actor({variant:"farmer_m",scale:2,...EduSprites.travel(route,t)}); EduSprites.drawActor(ctx,a)。行动结束后保持终点与endDirection；不要又用初始坐标重画。所有角色相同视角、近似像素比例，尽量整数缩放；不要把64像素角色放大到满屏。儿童使用boy_blue/girl_rose/boy_sage/girl_gold；老人使用grandpa/grandma/elder_scholar；选择符合时代与身份的服装。',
            '动作由绝对时间生成：EduSprites.actor({variant:"girl_rose",x:440,y:480,scale:2,direction:"left",...EduSprites.animate("wave",t,{start:2})})。wave挥手、nod点头、talk说话、pickup弯腰拾取、carry双手端物走、sit坐下、jump跳跃、work通用劳动手势。loop:false动作只播放一次并保持末帧；不要重复触发。jump图集自带起跳离地，不要再次对人物y叠加跳高。carry可配合travel的action:"carry"保持按路程行走；物品用手连接点绘制，库不自带工具/座椅或物品，模型需安排接触、座椅和道具。',
            '独立姿态：EduSprites.actor({variant:"scholar",x:440,y:480,scale:2,direction:"left",pose:"hands_front"})。neutral、hands_front、raised_arms仅静态姿势，不依次轮播，不能冒充劳动或跳跃；不构成全局动作白名单。',
            'EduSprites.anchor(actor,"hand")返回缩放后手部连接点；还支持leftHand/rightHand/foot/head/center。物品持有时每帧从同一个actor的连接点计算，不能独立计时漂移；绘制绳索的两端用两个当前人物anchor。连接点是基础素材近似位置，需在构图中确保接触可见。',
            'EduSprites.transfer(donor,receiver,t,{start:9,end:10,lift:2})连续返回两个当前手部连接点之间的位置。先让双方走近、面向对方并hands_front保持；只在接触距离内递交，开始前物品跟随donor，结束后跟随receiver。不隔空递物、不全身旋转。',
            'EduSprites.drawAsset(ctx,"tree",{x:200,y:150,width:128,height:192})直接画完整树。house为完整房屋；dirt可平铺；grass透明草丛只稀疏点缀纯色草地；water_ripple在自绘水面内裁剪点缀。book、basket、bucket可配手部连接点。没有的场景用Canvas/SVG自行绘制，保持整体轮廓。',
            '模型决定故事、构图、镜头与语义过渡。图集只解决常见人物/环境绘制与通用接触，不要生成关卡界面、游戏按钮或把所有故事套同一舞台。科学图形继续清晰绘制。'
        ],
    }


def assemble_sprites(html, *, enabled, required=False):
    if not enabled: return html
    manifest, files, digest = load_bundle()
    payload = {key:manifest[key] for key in ('catalog','characters','actions','aliases','contacts','art_origin')}
    payload['images'] = {key:'data:image/png;base64,'+base64.b64encode(files[item['file']]).decode() for key,item in manifest['catalog'].items()}
    data = json.dumps(payload,separators=(',',':')).replace('<','\\u003c')
    credits = files['CREDITS.txt'].decode('utf-8').replace('--','—').replace('<','&lt;')
    attributes=' data-edu-characters-required="true"' if required else ''
    script = '<!-- EDU-SPRITES '+digest+'\n'+credits+' -->\n<script id="edu-sprites-runtime"'+attributes+'>'+RUNTIME.read_text(encoding='utf-8')+'\nEduSprites.configure('+data+');</script>'
    if script in html: return html
    if 'id="edu-sprites-runtime"' in html: raise ValueError('素材运行时版本不一致，请重新生成')
    html = html.replace(MARKER,'')
    if re.search(r'<head\b[^>]*>',html,re.I):
        return re.sub(r'(<head\b[^>]*>)',lambda m:m[0]+script,html,count=1,flags=re.I)
    return re.sub(r'(<html\b[^>]*>)',lambda m:m[0]+'<head>'+script+'</head>',html,count=1,flags=re.I)


def model_source(html):
    """Do not send trusted base64 sheets or runtime back to the writer on repair."""
    return re.sub(r'<!-- EDU-SPRITES [a-f0-9]{64}\n[\s\S]*? -->\n<script id="edu-sprites-runtime"[^>]*>[\s\S]*?</script>', '', html)


def export_metadata(html):
    """Frozen films retain their embedded provenance when the active art changes."""
    match = re.search(r'<!-- EDU-SPRITES [a-f0-9]{64}\n([\s\S]*?) -->\n<script id="edu-sprites-runtime"[^>]*>', html)
    if not match:
        return {}
    credits = match[1].replace('&lt;', '<')
    comment = 'Original local pixel art; Edu Video; source: pixel-art/original-cast/build.py' if 'original-local-pixel-art' in credits else 'Embedded pixel art; see retained copyright and license information'
    return {'copyright': credits, 'comment': comment}
