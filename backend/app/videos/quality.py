"""Content-level visual defaults; teacher requests take precedence."""
RULES_VERSION = 'direct-html-2'


def resolve_style(form_values: dict, explicit: str = '') -> dict:
    science = form_values.get('subject') in ('数学', '物理', '化学', '生物')
    story = form_values.get('subject') in ('语文', '历史', '英语', '道德与法治')
    return {
        'value': explicit.strip() or ('science_animation' if science else 'pixel_story' if story else 'content_auto'),
        'source': 'request' if explicit.strip() else 'subject',
        'rules_version': RULES_VERSION,
        'defaults': {'character_stories': 'detailed_pixel_art', 'formulas_graphs_experiments': 'clean_graphics'},
        'instruction': '教师明确风格及局部修改优先；否则人物故事默认细腻像素风、简单自然动作，公式、图像和实验用清晰图形动画。按内容而非仅科目选择；混合内容保持配色统一，科学图形不强制像素化。',
    }
