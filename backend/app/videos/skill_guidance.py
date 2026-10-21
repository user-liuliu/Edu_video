"""Curated upstream documents consumed by direct HTML generation, never executable plugins."""
import hashlib
import json
import re
from pathlib import Path, PurePosixPath

SKILLS_ROOT = Path(__file__).with_name('skills')
SKILL_IDS = ('animation-principles', 'svg-animation', 'diagram-animation', 'javascript-animation',
             '2d-character-rig-animation', 'game-graphics')
ADAPTER_VERSION = 'direct-html-skills-9'
RUNTIME_ADAPTER = (
    '上游Skill只用于运动、构图、绘制及教学表达。最终输出完整HTML。'
    '原生HTML、SVG或Canvas均可；使用同步renderFrame(t)绝对时钟，不依赖累计状态。'
    '禁止CDN、外联、系统时钟、自动播放、独立配音或额外审核。'
    '保留已审核内容及最终讲稿、统一整片风格和自然转场；教师明确要求优先。'
    '故事默认采用清晰矢量／简洁插画人物；只有教师明确要求像素风时才使用像素风及相关参考，不能仅因有故事或人物而像素化。'
    '没有人物或动物时不添加角色；公式、函数图像和实验保持清晰，不强制像素化。'
    '参考资料只作视觉表达参考，不照搬外部工具、游戏状态机或审批流程。'
    '上游对实时循环、运行器或游戏玩法的要求均不适用。'
)
CHARACTER_MOTION_GUIDANCE = (
    '\n故事演绎中的人物使用完整、可复用的整体角色图形或SVG分组，并在全片保持造型、颜色和服饰一致。'
    '人物作为整体，只用整体移动、水平翻转、淡入和淡出表达简单动作；不要拆分四肢或制作关节、步态循环和手物接触动画。'
    '用人物整体位置变化、对白、道具、环境变化和镜头转场表达情节，不要求人物完成复杂的拿取或递交动作。'
    '片段衔接时沿用角色上一时刻的位置、朝向和造型，避免瞬移、闪现或重新绘制。'
    '公式、函数图像和实验保持清晰图形，不因故事风格而强制像素化。'
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
    digest = hashlib.sha256(raw + RUNTIME_ADAPTER.encode() + CHARACTER_MOTION_GUIDANCE.encode() + ADAPTER_VERSION.encode()).hexdigest()
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


def animation_reference_documents(guidance):
    """Keep compact design excerpts while omitting implementation-specific rig guidance."""
    headings = {
        ('animation-principles','SKILL.md'): ('## Three pillars','## Three motion layers'),
        ('javascript-animation','SKILL.md'): ('## Rules that prevent',),
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
        raise ValueError('动画设计参考内容超过上下文预算')
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
        r'赛博|矢量|插画|vector|illustration|(?:[A-Za-z]+|[\u4e00-\u9fff]{2,8})风格|'
        r'watercolor|realistic|cartoon|photorealistic|flat\s+design|ink\s+(?:style|painting)'
    )
    science = subject in ('数学','物理','化学','生物')
    story = subject in ('语文','历史','英语','道德与法治')
    no_story = bool(re.search(r'(?:不要|不用|不使用|避免|禁止|不讲|无需)\s*(?:任何|额外的?|添加|绘制|讲述|讲)?\s*(?:故事|人物|情节|角色)|\b(?:no|without|avoid)\s+(?:stories|story|characters)\b', teacher, re.I))
    narrative = not no_story and bool(re.search(r'故事|情节|叙事|寓言|童话|\b(?:story|stories|narrative)\b', content, re.I))
    technical = science or bool(re.search(r'函数|公式|图像|电路|实验|坐标|地形|水循环|笔顺|笔画|书写顺序|汉字结构|字词结构|语法|词汇|拼写|diagram|graph|experiment|grammar|vocabulary|spelling', content, re.I))
    # The subject default also covers named stories without a literal story or
    # character keyword. Keep technical language lessons and explicit opt-outs
    # on the native graphics route rather than listing every possible hero.
    default_story = value in ('vector_story','pixel_story') and not technical and not no_story
    character = not no_story and bool(re.search(r'人物|角色|小人|孔融|男孩|女孩|哥哥|姐姐|父亲|母亲|老人|老师|学生|农夫|农妇|牧羊人|村民|百姓|书生|商人|旅人|科学家|character|actor|person|farmer|shepherd|villager', content, re.I))
    revision_style = re.search(
        r'像素|pixel|(?:改为|改成|改用|换成|采用|使用|切换|换用|变为).{0,16}(?:'+style_terms+r')|'
        r'(?:水墨|水彩|剪纸|写实|油画|扁平|手绘|素描|黏土|粘土|赛博)\s*风|矢量|插画|'
        r'(?:'+style_terms+r').{0,4}(?:风格|画风)|'
        r'(?:switch|change|use).{0,20}(?:style|watercolor|ink|realistic|cartoon|vector|illustration)', revision, re.I)
    if revision_style:
        style_context = revision
    elif re.search(style_terms, teacher, re.I):
        style_context = teacher
    elif style.get('source') in ('selection','request'):
        style_context = value
    else:
        # Model-authored visuals and subject defaults are not teacher choices.
        style_context = ''
    pixel = bool(re.search(r'像素|pixel', style_context, re.I)) and not re.search(
        r'(?:不要|不采用|不使用|不用|禁止|避免|非|不是|取消)\s*(?:采用|使用)?\s*(?:像素|pixel)|'
        r'(?:no|non|without|avoid|(?:do\s+)?not\s+(?:use\s+)?)[ -]*(?:pixel)',
        style_context, re.I)
    if technical: selected.append('diagram-animation')
    if story or narrative or value in ('story_sketch','vector_story','pixel_story'):
        selected.append('javascript-animation')
    character = character or narrative or default_story or (not no_story and value == 'story_sketch')
    story_characters = not no_story and (
        narrative or default_story or ((character or value == 'story_sketch') and not technical)
    )
    if character or pixel: selected.append('game-graphics')
    specs=[('animation-principles','SKILL.md',('## Three pillars','## Three motion layers','## Core principles')),
           ('svg-animation','SKILL.md',('## Core techniques',))]
    if 'diagram-animation' in selected:
        specs.append(('diagram-animation','SKILL.md',('## Core principle: progressive disclosure','## Quick reference')))
    if 'javascript-animation' in selected:
        specs.append(('javascript-animation','SKILL.md',('## Rules that prevent',)))
    if character:
        specs.append(('game-graphics','concept-art-reference.md',('## Style Consistency Across Characters',)))
    if pixel:
        specs.append(('game-graphics','pixel-art-reference.md',('## Readability Guidelines','## Common Pixel Art Mistakes')))
    documents=[]
    for skill_id, path, headings in specs:
        content=_sections(files[(skill_id,path)],headings)
        if not content: raise ValueError('Skill参考章节缺失')
        source=manifest['skills'][skill_id]
        documents.append({'skill_id':skill_id,'repository':source['repository'],
                          'commit':source['commit'],'path':source['upstream_path']+'/'+path,'content':content})
    adapter = RUNTIME_ADAPTER + (CHARACTER_MOTION_GUIDANCE if story_characters else '')
    result={'adapter_version':ADAPTER_VERSION,'digest':digest,'skill_ids':selected,'style':style,
            'story_characters':story_characters,'runtime_adapter':adapter,'documents':documents}
    if len(json.dumps(result,ensure_ascii=False))>23500: raise ValueError('Skill参考内容超过上下文预算')
    return result
