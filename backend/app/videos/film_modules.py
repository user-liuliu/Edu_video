"""Editable HTML film modules with byte-stable, scoped visual revisions."""
import json
import re
from html.parser import HTMLParser
from typing import Literal
from .film_module_compiler import assemble_film
from pydantic import BaseModel, ConfigDict, Field

FILM_MODULE_PROTOCOL = 'film-modules-1'
MAX_BUNDLE_BYTES = 650_000
MAX_PART_BYTES = 120_000
KEY_PATTERN = r'^[A-Za-z0-9_-]{1,64}$'



class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class SegmentModule(StrictModel):
    id: str = Field(pattern=KEY_PATTERN)
    html: str = Field(max_length=MAX_PART_BYTES)
    code: str = Field(max_length=MAX_PART_BYTES)


class TransitionModule(StrictModel):
    from_id: str = Field(pattern=KEY_PATTERN)
    to_id: str = Field(pattern=KEY_PATTERN)
    duration: float = Field(gt=0, le=3)
    code: str = Field(min_length=1, max_length=MAX_PART_BYTES)
    mode: Literal['continuous', 'dissolve'] | None = None


class FilmBundle(StrictModel):
    shared_html: str = Field(max_length=MAX_PART_BYTES)
    shared_code: str = Field(max_length=MAX_PART_BYTES)
    segments: list[SegmentModule] = Field(min_length=1, max_length=500)
    transitions: list[TransitionModule] = Field(max_length=499)


class FilmDelta(StrictModel):
    segments: list[SegmentModule] = Field(min_length=1, max_length=500)
    transitions: list[TransitionModule] = Field(max_length=499)


def render_key(target, index):
    return target.get('render_key') or f'segment-{index}'


def _check_fragment(value, *, shared=False):
    if len(value.encode('utf-8')) > MAX_PART_BYTES:
        raise ValueError('动画模块超出大小限制')
    if re.search(r'</script|<!--|@import\b', value, re.I):
        raise ValueError('动画模块包含不支持的嵌入或自主动画')

    class Check(HTMLParser):
        def handle_starttag(self, tag, attrs):
            if tag.lower() in ('script','iframe','object','embed','base','form','link','audio','video','html','head','body'):
                raise ValueError('动画模块包含不支持的元素')
            for key, content in attrs:
                content = content or ''
                if key.lower().startswith('on') or key.lower() in ('srcdoc','action','formaction'):
                    raise ValueError('动画模块包含事件或外链属性')
                if key.lower() in ('src','href','xlink:href') and not content.startswith(('#','data:image/')):
                    raise ValueError('动画模块不能加载外部资源')
        handle_startendtag = handle_starttag

    Check().feed(value)
    return value


def _expected_transitions(keys):
    return [(left, right) for left, right in zip(keys, keys[1:])]


def validate_film(value, targets):
    bundle = FilmBundle.model_validate(value).model_dump(exclude_none=True)
    keys = [render_key(target, index) for index, target in enumerate(targets)]
    if len(keys) != len(set(keys)) or [item['id'] for item in bundle['segments']] != keys:
        raise ValueError('动画模块没有与全部教学片段一一对应')
    pairs = _expected_transitions(keys)
    if [(item['from_id'], item['to_id']) for item in bundle['transitions']] != pairs:
        raise ValueError('动画转场没有与相邻教学片段一一对应')
    _check_fragment(bundle['shared_html'], shared=True)
    for item in bundle['segments']:
        _check_fragment(item['html'])
        if '</script' in item['code'].lower() or '<!--' in item['code'] or re.search(r'\b(?:document|window|parent|top|opener)\s*\.', item['code']):
            raise ValueError('动画模块包含不支持的全局访问或代码边界')
    for item in bundle['transitions']:
        if '</script' in item['code'].lower() or '<!--' in item['code'] or re.search(r'\b(?:document|window|parent|top|opener)\s*\.', item['code']):
            raise ValueError('动画转场包含不支持的全局访问或代码边界')
    if '</script' in bundle['shared_code'].lower() or '<!--' in bundle['shared_code']:
        raise ValueError('共享动画代码包含不支持的代码边界')
    if len(json.dumps(bundle, ensure_ascii=False).encode('utf-8')) > MAX_BUNDLE_BYTES:
        raise ValueError('整片动画模块超出大小限制')
    return bundle


def validate_delta(value, source, selected_ids, targets):
    delta = FilmDelta.model_validate(value).model_dump(exclude_none=True)
    old_keys = [item['id'] for item in source['segments']]
    keys = [render_key(target, index) for index, target in enumerate(targets)]
    if old_keys != keys:
        raise ValueError('待修改片段与已生成动画的模块映射不一致')
    selected = set(selected_ids)
    if not selected or not selected <= set(keys):
        raise ValueError('请选择有效的动画片段')
    expected_transitions = [pair for pair in _expected_transitions(keys) if pair[0] in selected or pair[1] in selected]
    if [item['id'] for item in delta['segments']] != [key for key in keys if key in selected]:
        raise ValueError('局部修改返回了未选择的片段或遗漏了目标片段')
    if [(item['from_id'], item['to_id']) for item in delta['transitions']] != expected_transitions:
        raise ValueError('局部修改没有同时更新目标片段的相邻转场')
    for item in delta['segments']:
        _check_fragment(item['html'])
        if '</script' in item['code'].lower() or '<!--' in item['code'] or re.search(r'\b(?:document|window|parent|top|opener)\s*\.', item['code']):
            raise ValueError('动画模块包含不支持的全局访问或代码边界')
    for item in delta['transitions']:
        if '</script' in item['code'].lower() or '<!--' in item['code'] or re.search(r'\b(?:document|window|parent|top|opener)\s*\.', item['code']):
            raise ValueError('动画转场包含不支持的全局访问或代码边界')
    return delta


def patch_film(source, delta, selected_ids, targets):
    source = FilmBundle.model_validate(source).model_dump(exclude_none=True)
    delta = validate_delta(delta, source, selected_ids, targets)
    segments = {item['id']: item for item in source['segments']}
    segments.update({item['id']: item for item in delta['segments']})
    changed_transitions = {(item['from_id'], item['to_id']): item for item in delta['transitions']}
    transitions = []
    for item in source['transitions']:
        key = (item['from_id'], item['to_id'])
        transitions.append(changed_transitions.get(key, item))
    if set(segments) != {item['id'] for item in source['segments']}:
        raise ValueError('局部修改改变了动画模块范围')
    return {**source, 'segments': [segments[key] for key in (item['id'] for item in source['segments'])],
            'transitions': transitions}


def revision_request(request, source, selected_ids):
    source = FilmBundle.model_validate(source).model_dump(exclude_none=True)
    keys = [item['id'] for item in source['segments']]
    selected = set(selected_ids)
    if not selected or not selected <= set(keys):
        raise ValueError('请选择有效的动画片段')
    editable_transitions = [item for item in source['transitions']
                            if item['from_id'] in selected or item['to_id'] in selected]
    adjacent = {key for item in editable_transitions for key in (item['from_id'], item['to_id'])} - selected
    contexts = [item for item in source['segments'] if item['id'] in adjacent]
    return {
        'film_edit_mode': 'selected_modules_and_adjacent_transitions',
        'editable_segment_ids': [key for key in keys if key in selected],
        'editable_transitions': [{'from_id': item['from_id'], 'to_id': item['to_id']}
                                 for item in editable_transitions],
        'film': {'shared_html': source['shared_html'], 'shared_code': source['shared_code'],
                 'segments': [item for item in source['segments'] if item['id'] in selected],
                 'transitions': editable_transitions},
        'read_only_boundary_context': contexts,
        'segments': request['segments'],
        'continuity_manifest': request.get('continuity_manifest', {}),
        'connection_contracts': request.get('connection_contracts', []),
        'teacher_request': request.get('teacher_request', ''),
        'title': request.get('title', ''),
        'visual_style': request.get('visual_style', {}),
        'instruction': request.get('instruction', ''),
    }


def extract_film(raw):
    marker = '<script type="application/json" id="edu-film-bundle">'
    start = raw.find(marker)
    if start < 0:
        raise ValueError('此预览尚无可局部编辑的动画模块，请先重新生成完整视频')
    start += len(marker)
    end = raw.find('</script>', start)
    if end < 0:
        raise ValueError('动画模块索引不完整')
    return FilmBundle.model_validate(json.loads(raw[start:end])).model_dump(exclude_none=True)


async def generate_film(config, request, http, *, feedback=''):
    from pathlib import Path
    from .model_stream import animation_response
    from app.outline.model_client import ModelCallError, _http_failure
    delta_source = request.get('film_revision_source')
    repair_source = request.get('previous_film_bundle')
    selected = request.get('editable_segment_ids',[])
    prompt = Path(__file__).with_name('film_modules_prompt.txt').read_text(encoding='utf-8')
    user = {key:value for key,value in request.items()
            if key not in ('film_revision_source','previous_html','previous_film_bundle')}
    if delta_source:
        user = revision_request(request,delta_source,selected)
    elif repair_source:
        user['film_repair_source']=FilmBundle.model_validate(repair_source).model_dump(exclude_none=True)
        user['repair_contract']='仅修复运行错误。基于既有动画返回完整FilmBundle，保留教学设计、讲稿和时间轴；可以修复共享素材和代码，不得重新创作影片。'
    user['response_schema'] = (FilmDelta if delta_source else FilmBundle).model_json_schema()
    messages=[{'role':'system','content':prompt},{'role':'user','content':json.dumps(user,ensure_ascii=False)}]
    if feedback:
        messages.append({'role':'user','content':'技术检查失败，请修复代码并保持修改范围、逐句讲稿和时间轴：'+feedback[:800]})
    url=config.base_url.rstrip('/')
    if not url.endswith('/chat/completions'):url+='/chat/completions'
    for attempt in range(2):
        response=await animation_response(http,url,{'Authorization':'Bearer '+config.api_key},
            {'model':config.model,'messages':messages,'response_format':{'type':'json_object'},'stream':True,'max_tokens':18000})
        if not response.is_success:raise _http_failure(response)
        try:
            value=json.loads(response.json()['choices'][0]['message']['content'])
            bundle=patch_film(delta_source,value,selected,request['segments']) if delta_source else validate_film(value,request['segments'])
            # New same-scene joins must retain the canvas rather than hiding
            # mismatched states behind a whole-layer dissolve. Old stored films
            # remain extractable; only regenerated adjacent joins are constrained.
            editable={(item['from_id'],item['to_id']) for item in value.get('transitions',[])}
            for index,transition in enumerate(bundle['transitions']):
                if delta_source and (transition['from_id'],transition['to_id']) not in editable:continue
                left,right=request['segments'][index:index+2]
                if left.get('scene_id') and left.get('scene_id')==right.get('scene_id') and transition.get('mode')!='continuous':
                    raise ValueError('同一scene_id必须使用continuous连接，保持边界画面一致；不要整层淡入淡出')
            return assemble_film(bundle,request['segments'])
        except (ValueError,KeyError,IndexError,TypeError) as error:
            if attempt:raise ValueError('动画片段或转场结构不完整，请重试') from None
            messages.append({'role':'user','content':'上一结果无效：'+str(error)[:350]+'。只修正并返回schema要求的完整JSON；局部修改只能返回选中片段及相邻转场，不改变共享资源。'})
