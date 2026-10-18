"""服务端解析教师输入；隐藏项绝不接受客户端覆盖。"""
import hashlib
import json
import math

from app.errors import api_error
from app.model_configs.schemas import Voice
from .schemas import FieldKey, FormFieldsConfig, OPTION_FIELDS


def form_version(config: FormFieldsConfig, voices: list[Voice], search_ready: bool) -> str:
    data = [config.model_dump(mode='json'), [v.model_dump() for v in voices], search_ready]
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def resolve_form_values(config: FormFieldsConfig, submitted: dict, *, voices: list[Voice], search_ready: bool) -> dict:
    fields = {f.key: f for f in config.fields}
    result = {}
    for key in OPTION_FIELDS:
        field = fields[key]
        default = field.default
        if key == FieldKey.textbook_edition:
            default = field.default_by_subject.get(result.get('subject'), default)
        value = submitted.get(key, default) if field.visible else default
        valid_options = [o.value for o in field.options if not o.subjects or result.get('subject') in o.subjects]
        if not isinstance(value, str) or value not in valid_options:
            raise api_error(422, 'invalid_form_value', f'{field.label}不在当前可选值中，请重新选择')
        result[key.value] = value
    minutes = submitted.get('custom_duration_minutes') if result['duration'] == 'custom' else result['duration']
    try:
        if isinstance(minutes, bool):
            raise ValueError
        minutes = float(minutes)
        if not math.isfinite(minutes) or minutes <= 0 or minutes > 60:
            raise ValueError
    except (ValueError, TypeError):
        raise api_error(422, 'invalid_duration', '自定义时长需大于 0 且不超过 60 分钟') from None
    result['duration_seconds'] = round(minutes * 60)
    if result['duration'] == 'custom':
        result['custom_duration_minutes'] = minutes
    search_field = fields[FieldKey.web_search]
    search = submitted.get('web_search', search_field.default) if search_field.visible else search_field.default
    if not isinstance(search, bool):
        raise api_error(422, 'invalid_search', '联网搜索选项必须为开关值')
    result['web_search'] = search and search_ready
    voice_field = fields[FieldKey.voice]
    default_voice = voice_field.default if voice_field.default in [v.speaker_id for v in voices] else (voices[0].speaker_id if voices else None)
    voice = submitted.get('voice', default_voice) if voice_field.visible else default_voice
    if voices and voice not in [v.speaker_id for v in voices]:
        raise api_error(422, 'invalid_voice', '请选择当前可用的配音音色')
    result['voice'] = voice if voices else None
    return result
