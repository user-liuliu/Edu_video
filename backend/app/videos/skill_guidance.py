"""Curated upstream documents consumed by direct HTML generation, never executable plugins."""
import hashlib
import json
import re
from pathlib import Path, PurePosixPath

SKILLS_ROOT = Path(__file__).with_name('skills')
SKILL_IDS = ('animation-principles', 'svg-animation', 'diagram-animation', 'javascript-animation',
             '2d-character-rig-animation', 'game-graphics')
ADAPTER_VERSION = 'direct-html-skills-7'
RUNTIME_ADAPTER = (
    '上游Skill只用于运动、构图、绘制及教学表达。最终输出完整HTML。'
    '原生HTML、SVG或Canvas均可；使用同步renderFrame(t)绝对时钟，不依赖累计状态。'
    '禁止CDN、外联、系统时钟、自动播放、独立配音或额外审核。'
    '保留已审核内容及最终讲稿、统一整片风格和自然转场；教师明确要求优先。'
    '只借鉴参考资料的绘制、连接、接触和表演原则，不照搬骨骼引擎、姿态库、游戏状态机、'
    '外部工具、审批工作流或夸张的挤压拉伸。有sprite_library时故事人物必须使用程序提供的离线角色与动作接口；缺少角色使用近似人物，不重新拼接人体。否则角色由模型在完整HTML内自主绘制。'
    '每个角色在代码内部复用同一绘制定义，保持比例、服饰、像素密度和肢段长度一致；'
    '肩肘腕髋膝连接稳定，弯曲方向合理，手和持有物用同一接触位置计算，不瞬移。'
    '简单清楚的动作优先：如小步走动、轻微转头、短距离拿取递交；这些仅是例子，不是动作白名单。'
    '动作有准备、执行、收势与停顿，用视线和轻微表情表达意图及回应；无需一直摆动或做复杂关节动作。'
    '跨段保持人物朝向、位置和持有物连续，自然转移注意力，不反复重置舞台。'
    '人物故事默认细腻像素风、清楚轮廓，不强制粗块低分辨率；公式、图像、实验保持清晰图形。教师明确其他风格优先；'
    '非像素风忽略资料中的像素网格建议。上游对实时循环、运行器或游戏玩法的要求均不适用。'
)
NATIVE_DRAWING_GUIDANCE = (
    '\n非像素风绘制规范：本次未提供像素人物素材库，按教师明确画风直接用HTML、SVG或Canvas绘制；'
    '没有人物或动物时不添加角色，公式、函数图像和实验保持清晰，不强制像素化。'
    '先在代码内部建立可复用的角色比例、自然站姿和朝向，再从基础姿态连续生成动作，不输出额外设计说明。'
    '人体左右肩、肘部、腕部、髋、膝和踝分别连接，肢段长度与身体比例保持稳定；'
    '默认站姿手臂自然垂放或轻微前屈，双肘留在身体各自一侧，双脚支撑身体，不能无故交叉成X形或反向折叠。'
    '侧身时正确处理远近肢体遮挡，不能把所有肢体铺在身体最前层；衣袖包覆并跟随手臂，不能把交领、衣褶或袖口画成额外手臂。'
    '若使用两段关节求解，明确左右弯曲方向和朝向，结合姿态及可达范围选择稳定解，避免镜像分支翻转；'
    '不能因手脚目标距离过短而把多余肢段长度硬折成三角形、交叉形或锯齿形，目标不可达时调整躯干位置、走位或姿态，不拉长肢体。'
    '动物按物种设计躯干、四肢与关节，不能直接套用人体膝肘或让相邻腿反向内折；'
    '站立时承重腿符合该物种的自然支撑姿态，不能统一套用深蹲折腿模板；足端落在同一地面或合理支撑面，关节不锁死、不反折，远近腿有正确遮挡。'
    '行走时支撑足接地稳定，摆动足抬起后再落地，重心与步幅协调；停下后回到合理站姿，不保留深蹲或折腿步态。'
    '拿取、递交和放下保持手物接触连续，身体和关节缓入缓出；细节拿不准时简化轮廓与动作，不用扭曲肢体或夸张衣袖填补。'
    '生成代码前内部检查静止、行走、接触及转场的代表姿态；这只是本次生成的绘制要求，不新增AI审核调用，'
    '不限制动作种类，也不绑定某个故事、人物或动物。'
)


def _read_bundle(root):
    root = Path(root).resolve()
    try:
        raw = (root / 'sources.json').read_bytes()
        if len(raw) > 32000: raise ValueError('Skill来源清单过大')
        manifest = json.loads(raw)
        if manifest.get('schema_version') != 1 or set(manifest['skills']) != set(SKILL_IDS):
            raise ValueError('Skill来源清单无效')
        documents = {}
        for skill_id in SKILL_IDS:
            source = manifest['skills'][skill_id]
            if not re.fullmatch(r'[0-9a-f]{40}', source['commit']) or source['license'] not in ('MIT', 'Apache-2.0'):
                raise ValueError('Skill来源版本或许可证无效')
            files = source['files']
            if not {'LICENSE', 'SKILL.md'} <= set(files) or len(files) > 24:
                raise ValueError('Skill来源清单无效')
            skill_root = (root / 'upstream' / skill_id).resolve()
            if not skill_root.is_relative_to(root): raise ValueError('Skill路径越界')
            for relative, expected in files.items():
                path = PurePosixPath(relative)
                if path.is_absolute() or '..' in path.parts or chr(92) in relative or ':' in relative:
                    raise ValueError('Skill路径无效')
                target = (skill_root / relative).resolve()
                if not target.is_relative_to(skill_root): raise ValueError('Skill路径越界')
                if target.stat().st_size > 64000: raise ValueError('Skill文件过大')
                content = target.read_bytes()
                if hashlib.sha256(content).hexdigest() != expected:
                    raise ValueError('Skill文件完整性校验失败')
                documents[(skill_id, relative)] = content.decode('utf-8')
            license_text = documents[(skill_id, 'LICENSE')]
            license_markers = {'MIT': ('MIT License',),
                               'Apache-2.0': ('Apache License', 'Version 2.0, January 2004',
                                              'TERMS AND CONDITIONS', 'END OF TERMS AND CONDITIONS')}
            if not all(marker in license_text for marker in license_markers[source['license']]):
                raise ValueError('Skill许可证完整性校验失败')
    except (OSError, KeyError, TypeError, UnicodeError, json.JSONDecodeError):
        raise ValueError('Skill文件完整性或来源校验失败') from None
    digest = hashlib.sha256(raw + RUNTIME_ADAPTER.encode() + NATIVE_DRAWING_GUIDANCE.encode() + ADAPTER_VERSION.encode()).hexdigest()
    return manifest, documents, digest


def bundle_metadata(*, root=SKILLS_ROOT):
    manifest, _, digest = _read_bundle(root)
    return {'adapter_version': ADAPTER_VERSION, 'digest': digest,
            'sources': {key: {'repository':value['repository'],'commit':value['commit']}
                        for key,value in manifest['skills'].items()}}


def _sections(text, starts):
    lines=text.splitlines(keepends=True)
    result=[]; active=False
    for line in lines:
        if line.startswith('## '): active=any(line.startswith(start) for start in starts)
        if active: result.append(line)
    return ''.join(result).strip()


def sprite_reference_documents(guidance):
    """Use applicable upstream excerpts when the runtime already draws actors.

    Rig construction, sprite creation and third-party animation examples are
    unnecessary for existing sprite sheets. Preserve source text/provenance,
    contact/performance principles and native scientific diagram guidance.
    """
    headings = {
        ('animation-principles','SKILL.md'): ('## Three pillars','## Three motion layers'),
        ('javascript-animation','character.md'): ('## Anchor points',),
        ('2d-character-rig-animation','SKILL.md'): ('## Animate performance, not controls','## Cycles and contacts'),
        ('game-graphics','concept-art-reference.md'): ('## Style Consistency Across Characters',),
        ('game-graphics','pixel-art-reference.md'): ('## Readability Guidelines',),
        ('diagram-animation','SKILL.md'): ('## Core principle: progressive disclosure',),
    }
    documents=[]
    for doc in guidance['documents']:
        selected=headings.get((doc['skill_id'],PurePosixPath(doc['path']).name))
        if selected:
            content=_sections(doc['content'],selected)
            if not content:raise ValueError('素材动画参考章节缺失')
            documents.append({**doc,'content':content})
    if len(json.dumps(documents,ensure_ascii=False).encode('utf-8'))>9000:
        raise ValueError('素材动画参考内容超过上下文预算')
    return documents


def animation_guidance(segment, style, *, root=SKILLS_ROOT):
    manifest, files, digest = _read_bundle(root)
    selected = ['animation-principles','svg-animation']
    subject = segment.get('subject','')
    value = style.get('value','')
    content = ' '.join(str(segment.get(key,'')) for key in
                       ('visuals','narration','teacher_request','whole_film_visual_prompt','teacher_visual_instruction'))
    revision = str(segment.get('teacher_visual_instruction',''))
    teacher = str(segment.get('teacher_request',''))
    # Explicit local style changes win; motion-only edits keep the film style.
    style_terms = (
        r'像素|pixel|水墨|剪纸|写实|卡通|油画|扁平|手绘|水彩|素描|黏土|粘土|'
        r'赛博|(?:[A-Za-z]+|[\u4e00-\u9fff]{2,8})风格|'
        r'watercolor|realistic|cartoon|photorealistic|flat\s+design|ink\s+(?:style|painting)'
    )
    science = subject in ('数学','物理','化学','生物')
    story = subject in ('语文','历史','英语','道德与法治')
    no_story = bool(re.search(r'(?:不要|不用|不使用|避免|禁止|不讲|无需).{0,4}(?:故事|人物|情节|角色)|\b(?:no|without|avoid)\s+(?:stories|story|characters)\b', teacher, re.I))
    narrative = not no_story and bool(re.search(r'故事|情节|叙事|寓言|童话|\b(?:story|stories|narrative)\b', content, re.I))
    technical = science or bool(re.search(r'函数|公式|图像|电路|实验|坐标|地形|水循环|笔顺|笔画|书写顺序|汉字结构|字词结构|语法|词汇|拼写|diagram|graph|experiment|grammar|vocabulary|spelling', content, re.I))
    # The subject default also covers named stories without a literal story or
    # character keyword. Keep technical language lessons and explicit opt-outs
    # on the native graphics route rather than listing every possible hero.
    default_story = value == 'pixel_story' and not technical and not no_story
    character = not no_story and bool(re.search(r'人物|角色|小人|孔融|男孩|女孩|哥哥|姐姐|父亲|母亲|老人|老师|学生|农夫|农妇|牧羊人|村民|百姓|书生|商人|旅人|科学家|character|actor|person|farmer|shepherd|villager', content, re.I))
    revision_style = re.search(
        r'像素|pixel|(?:改为|改成|改用|换成|采用|使用|切换|换用|变为).{0,16}(?:'+style_terms+r')|'
        r'(?:水墨|水彩|剪纸|写实|油画|扁平|手绘|素描|黏土|粘土|赛博)\s*风|'
        r'(?:'+style_terms+r').{0,4}(?:风格|画风)|'
        r'(?:switch|change|use).{0,20}(?:style|watercolor|ink|realistic|cartoon)', revision, re.I)
    if revision_style:
        style_context = revision
    elif re.search(style_terms, teacher, re.I):
        style_context = teacher
    elif style.get('source') in ('selection','request'):
        style_context = value
    elif not style.get('defaults') and re.search(style_terms, content, re.I):
        style_context = content
    else:
        # This is only reference routing; the model receives the content-level
        # policy too, so a science story can use pixels with clear diagrams.
        style_context = 'pixel' if narrative or default_story or ((character or value == 'story_sketch') and not technical and not no_story) else ''
    pixel = bool(re.search(r'像素|pixel', style_context, re.I)) and not re.search(
        r'(?:不要|不采用|不使用|不用|禁止|避免|非|不是|取消)\s*(?:采用|使用)?\s*(?:像素|pixel)|'
        r'(?:no|non|without|avoid|(?:do\s+)?not\s+(?:use\s+)?)[ -]*(?:pixel)',
        style_context, re.I)
    if technical: selected.append('diagram-animation')
    if story or narrative or value in ('story_sketch','pixel_story'):
        selected.append('javascript-animation')
    character = character or narrative or default_story or (not no_story and value == 'story_sketch')
    if character: selected.append('2d-character-rig-animation')
    if character or pixel: selected.append('game-graphics')
    specs=[('animation-principles','SKILL.md',('## Three pillars','## Three motion layers','## Core principles')),
           ('svg-animation','SKILL.md',('## Core techniques',))]
    if 'diagram-animation' in selected:
        specs.append(('diagram-animation','SKILL.md',('## Core principle: progressive disclosure','## Quick reference')))
    if 'javascript-animation' in selected:
        specs.extend([('javascript-animation','SKILL.md',('## Rules that prevent',)),
                      ('javascript-animation','references/character.md',('## Anchor points','## Poses that read'))])
    if character:
        specs.extend([
            ('2d-character-rig-animation','SKILL.md',
             ('## Choose rigid, replacement, or deforming parts',
              '## Animate performance, not controls','## Cycles and contacts')),
            ('game-graphics','concept-art-reference.md',('## Style Consistency Across Characters',))])
    if pixel:
        specs.extend([
            ('game-graphics','pixel-art-reference.md',('## Readability Guidelines','## Common Pixel Art Mistakes')),
            ('game-graphics','animation-reference.md',('## Walk Cycle Anatomy','## Idle Animation'))])
    documents=[]
    for skill_id, path, headings in specs:
        content=_sections(files[(skill_id,path)],headings)
        if not content: raise ValueError('Skill参考章节缺失')
        source=manifest['skills'][skill_id]
        documents.append({'skill_id':skill_id,'repository':source['repository'],
                          'commit':source['commit'],'path':source['upstream_path']+'/'+path,'content':content})
    adapter = RUNTIME_ADAPTER + (NATIVE_DRAWING_GUIDANCE if not pixel else '')
    result={'adapter_version':ADAPTER_VERSION,'digest':digest,'skill_ids':selected,'style':style,'runtime_adapter':adapter,'documents':documents}
    if len(json.dumps(result,ensure_ascii=False))>23500: raise ValueError('Skill参考内容超过上下文预算')
    return result
