"""Explicit content-review verdicts and server-owned save receipts."""
import hashlib
import json

CONTENT_FIELDS = ('title', 'objective', 'narration', 'visuals', 'evidence_ids', 'content_kind')

REVIEW_RESPONSE_SCHEMA = {
    'name': 'outline_review', 'strict': True,
    'schema': {
        'type': 'object', 'additionalProperties': False, 'required': ['items'],
        'properties': {'items': {'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False,
            'required': ['segment_id', 'passed', 'issues', 'notes'],
            'properties': {
                'segment_id': {'type': 'string'},
                'passed': {'type': 'boolean'},
                'issues': {'type': 'array', 'items': {'type': 'string'}},
                'notes': {'type': 'array', 'items': {'type': 'string'}},
            },
        }}},
    },
}


def validate_verdict(value):
    if not isinstance(value, dict) or type(value.get('passed')) is not bool:
        raise ValueError('审核结果缺少明确通过结论，请重新审核')
    result = {'passed': value['passed']}
    for key in ('issues', 'notes'):
        items = value.get(key)
        if not isinstance(items, list) or len(items) > 30 or any(not isinstance(item, str) for item in items):
            raise ValueError('审核结果格式无效，请重新审核')
        result[key] = list(dict.fromkeys(item.strip() for item in items if item.strip()))
    if result['passed'] == bool(result['issues']):
        raise ValueError('审核结论与问题原因不一致，请重新审核')
    return result


def normalize_review_results(result, segment_ids):
    if not isinstance(result, dict) or not isinstance(result.get('items'), list):
        raise ValueError('审核结果格式无效，请重新审核')
    values = {}
    expected = set(segment_ids)
    for item in result['items']:
        if not isinstance(item, dict):
            raise ValueError('审核结果格式无效，请重新审核')
        identifier = item.get('segment_id')
        if not isinstance(identifier, str) or identifier not in expected or identifier in values:
            raise ValueError('审核结果段落不匹配，请重新审核')
        values[identifier] = validate_verdict(item)
    if set(values) != expected:
        raise ValueError('审核结果遗漏段落，请重新审核')
    return values


def review_state(segment):
    if segment.get('reviewed_revision') != segment.get('content_revision') or type(segment.get('review_passed')) is not bool:
        return 'pending'
    return 'passed' if segment['review_passed'] else 'failed'


def content_fingerprint(outline):
    # Order and segment identity matter to saving; review metadata does not.
    contents = [dict(id=str(s['id']), **{key: s[key] for key in CONTENT_FIELDS}) for s in outline['segments']]
    encoded = json.dumps(contents, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(encoded.encode('utf-8')).hexdigest()


def mark_saved(outline):
    return {**outline, 'saved_content_hash': content_fingerprint(outline)}


def needs_save(outline):
    return not outline or outline.get('saved_content_hash') != content_fingerprint(outline)
