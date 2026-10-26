"""Editable HTML film modules with byte-stable, scoped visual revisions."""
import asyncio
import json
import logging
from copy import deepcopy
import re
from html.parser import HTMLParser
from typing import Literal
from .film_module_compiler import assemble_film
from pydantic import BaseModel, ConfigDict, Field

FILM_MODULE_PROTOCOL = 'film-modules-1'
MAX_GENERATION_SECONDS = 900
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


def _compact_request(request):
    """Remove only exact duplicate data; never abbreviate unique approved facts."""
    user = deepcopy({key: value for key, value in request.items()
                     if key not in ('film_revision_source', 'previous_html', 'previous_film_bundle')})
    targets = user.get('segments', [])
    by_id = {target.get('id', target.get('render_key')): target for target in targets}
    manifest = user.get('continuity_manifest', {})
    entries = manifest.get('segments')
    if isinstance(entries, list) and all(
        isinstance(entry, dict) and entry.get('id') in by_id and all(
            key == 'id' or by_id[entry['id']].get(key) == value for key, value in entry.items())
        for entry in entries
    ):
        del manifest['segments']
    narrations = {target.get('narration') for target in targets}
    outline = user.get('approved_outline', {})
    if isinstance(outline, dict):
        for segment in outline.get('segments', []):
            if isinstance(segment, dict) and segment.get('narration') in narrations:
                segment.pop('narration', None)
    return user


def _validate_connections(bundle, targets, editable=None):
    for index, transition in enumerate(bundle['transitions']):
        if editable is not None and (transition['from_id'], transition['to_id']) not in editable:
            continue
        left, right = targets[index:index+2]
        if left.get('scene_id') and left.get('scene_id') == right.get('scene_id') and transition.get('mode') != 'continuous':
            raise ValueError('同一scene_id必须使用continuous连接，保持边界画面一致；不要整层淡入淡出')
    return bundle


async def _film_exchange(config, http, prompt, user, schema, validate, *, feedback='', split=False, max_tokens=18000):
    from .model_stream import animation_response
    from app.outline.model_client import _http_failure
    from .film_context import compact_module_context
    user = {**compact_module_context(user), 'response_schema': schema.model_json_schema()}
    messages = [{'role': 'system', 'content': prompt},
                {'role': 'user', 'content': json.dumps(user, ensure_ascii=False, separators=(',', ':'))}]
    if feedback:
        messages.append({'role': 'user', 'content': '技术检查失败，请修复代码并保持修改范围、逐句讲稿和时间轴：' + feedback[:800]})
    url = config.base_url.rstrip('/')
    if not url.endswith('/chat/completions'):
        url += '/chat/completions'
    for attempt in range(2):
        options = {'split_on_slow_failure': True} if split else {}
        # Transport failures do not consume format correction retries or change edit scope.
        response = await animation_response(http, url, {'Authorization': 'Bearer ' + config.api_key},
            {'model': config.model, 'messages': messages, 'response_format': {'type': 'json_object'},
             'stream': True, 'max_tokens': max_tokens}, **options)
        if not response.is_success:
            raise _http_failure(response)
        try:
            return validate(json.loads(response.json()['choices'][0]['message']['content']))
        except (ValueError, KeyError, IndexError, TypeError) as error:
            if attempt:
                raise ValueError('动画片段或转场结构不完整，请重试') from None
            messages.append({'role': 'user', 'content': '上一结果无效：' + str(error)[:350]
                + '。只修正并返回schema要求的完整JSON；不得改变请求的片段范围、共享资源或时间轴。'})


class FilmBatchPending(Exception):
    def __init__(self, completed, total):
        self.completed, self.total = completed, total
        super().__init__(f'Animation checkpoint {completed}/{total}')


async def _generate_ordered_modules(config, http, prompt, user, *, checkpoint=None, save_checkpoint=None, max_modules=None):
    targets = user['segments']
    import time
    started = time.monotonic()
    made = 0
    if checkpoint is not None:
        count = len(checkpoint.get('segments', []))
        if not 1 <= count <= len(targets):
            raise ValueError('动画检查点片段范围无效')
        bundle = _validate_connections(validate_film(checkpoint, targets[:count]), targets[:count])
    else:
        # Design shared components against the entire frozen film before any scene.
        seed = {**user, 'film_build_mode': 'shared_first', 'segments': targets[:1],
                'read_only_film_plan': targets[1:], 'connection_contracts': []}
        bundle = await _film_exchange(config, http, prompt, seed, FilmBundle,
            lambda value: validate_film(value, targets[:1]), max_tokens=12000)
        if save_checkpoint:
            await save_checkpoint(deepcopy(bundle))
        made += 1
    for index in range(len(bundle['segments']), len(targets)):
        # Yield only after a complete response has been durably saved.
        if save_checkpoint and (max_modules and made >= max_modules or made and time.monotonic()-started >= 300):
            raise FilmBatchPending(len(bundle['segments']), len(targets))
        target = targets[index]
        previous_key = render_key(targets[index-1], index-1)
        key = render_key(target, index)
        contracts = [item for item in user.get('connection_contracts', [])
                     if item.get('from_id') == previous_key and item.get('to_id') == key]
        append = {name: user[name] for name in ('title', 'teacher_request', 'source_duration',
                  'whole_film_visual_prompt', 'visual_style', 'continuity_manifest', 'animation_reference_adapter') if name in user}
        # Carry approved subject facts throughout, including facts absent from narration.
        append.update(film_build_mode='append_modules', segments=[target],
            approved_outline=user.get('approved_outline', {}), connection_contracts=contracts,
            film={'shared_html': bundle['shared_html'], 'shared_code': bundle['shared_code']},
            read_only_boundary_context=[bundle['segments'][-1]],
            previous_segment_context=targets[index-1],
            next_segment_context=targets[index+1:index+2])

        def validate_append(value):
            delta = FilmDelta.model_validate(value).model_dump(exclude_none=True)
            if [item['id'] for item in delta['segments']] != [key]:
                raise ValueError('分批生成遗漏目标片段或返回了未选择片段')
            if [(item['from_id'], item['to_id']) for item in delta['transitions']] != [(previous_key, key)]:
                raise ValueError('分批生成必须包含且仅包含前一片段的连接')
            merged = {**bundle, 'segments': bundle['segments'] + delta['segments'],
                      'transitions': bundle['transitions'] + delta['transitions']}
            return _validate_connections(validate_film(merged, targets[:index+1]), targets[:index+1])

        bundle = await _film_exchange(config, http, prompt, append, FilmDelta, validate_append, max_tokens=10000)
        if save_checkpoint:
            await save_checkpoint(deepcopy(bundle))
        made += 1
    return _validate_connections(validate_film(bundle, targets), targets)


async def _generate_film(config, request, http, *, feedback='', checkpoint=None, save_checkpoint=None, max_modules=None):
    from pathlib import Path
    from .model_stream import SplitAnimationRequest
    from app.outline.model_client import ModelCallError
    delta_source = request.get('film_revision_source')
    repair_source = request.get('previous_film_bundle')
    selected = request.get('editable_segment_ids', [])
    prompt = Path(__file__).with_name('film_modules_prompt.txt').read_text(encoding='utf-8')
    user = _compact_request(request)
    if delta_source:
        user = _compact_request(revision_request(request, delta_source, selected))
    elif repair_source:
        user['film_repair_source'] = FilmBundle.model_validate(repair_source).model_dump(exclude_none=True)
        user['repair_contract'] = '仅修复运行错误。基于既有动画返回完整FilmBundle，保留教学设计、讲稿和时间轴；可以修复共享素材和代码，不得重新创作影片。'

    def validate(value):
        bundle = patch_film(delta_source, value, selected, request['segments']) if delta_source else validate_film(value, request['segments'])
        editable = {(item['from_id'], item['to_id']) for item in value.get('transitions', [])} if delta_source else None
        return _validate_connections(bundle, request['segments'], editable)

    can_split = not delta_source and not repair_source and len(request['segments']) > 1
    logger = logging.getLogger(__name__)
    logger.info('animation_generation_request mode=%s segments=%s input_bytes=%s',
                'revision' if delta_source else 'repair' if repair_source else 'whole',
                len(request['segments']), len(json.dumps(user, ensure_ascii=False, separators=(',', ':')).encode('utf-8')))
    if checkpoint is not None and (delta_source or repair_source):
        raise ValueError('局部修改或代码修复不能混入整片生成检查点')
    ordered = checkpoint is not None or can_split and (user.get('source_duration', 0) >= 180 or len(user['segments']) >= 8)
    if ordered:
        bundle = await _generate_ordered_modules(config, http, prompt, user, checkpoint=checkpoint,
            save_checkpoint=save_checkpoint, max_modules=max_modules)
        return assemble_film(bundle, request['segments'])
    try:
        bundle = await _film_exchange(config, http, prompt, user, FilmDelta if delta_source else FilmBundle,
                                      validate, feedback=feedback, split=can_split)
    except ModelCallError as error:
        if not can_split or not (isinstance(error, SplitAnimationRequest) or error.category == 'output_limit'):
            raise
        logger.warning('animation_generation_recovery mode=ordered_modules segments=%s category=%s',
                       len(request['segments']), error.category)
        bundle = await _generate_ordered_modules(config, http, prompt, user,
            save_checkpoint=save_checkpoint, max_modules=max_modules)
        return assemble_film(bundle, request['segments'])
    if save_checkpoint and not delta_source and not repair_source:
        await save_checkpoint(deepcopy(bundle))
    return assemble_film(bundle, request['segments'])


async def generate_film(config, request, http, *, feedback='', checkpoint=None, save_checkpoint=None, max_modules=None):
    from app.outline.model_client import ModelCallError
    try:
        # Leave time for speech, runtime checks and result persistence within the job limit.
        async with asyncio.timeout(MAX_GENERATION_SECONDS):
            return await _generate_film(config, request, http, feedback=feedback, checkpoint=checkpoint,
                save_checkpoint=save_checkpoint, max_modules=max_modules)
    except TimeoutError:
        raise ModelCallError('动画代码生成等待超时，本次任务已停止，请稍后重试', category='timeout') from None
