"""Conservative outgoing context shaping for ordered animation generation."""
from copy import deepcopy

_WORKFLOW_FIELDS = ('review_passed', 'reviewed_revision', 'content_revision',
                    'estimated_duration_seconds')


def compact_module_context(user):
    """Keep the complete teaching route and exact active/shared/boundary data."""
    value = deepcopy(user)
    if value.get('film_build_mode') not in ('shared_first', 'append_modules'):
        return value
    active = {str(target['outline_segment_id']): target
              for target in value.get('segments', []) if target.get('outline_segment_id')}
    outline = value.get('approved_outline')
    if isinstance(outline, dict):
        outline.pop('saved_content_hash', None)
        for item in outline.get('segments', []):
            for key in _WORKFLOW_FIELDS:
                item.pop(key, None)
            # Keep nonempty findings: compatible imported data may carry facts.
            if not item.get('review_issues'):
                item.pop('review_issues', None)
            current = active.get(str(item.get('id')))
            if current and item.get('narration') == current.get('narration'):
                item.pop('narration', None)
    # Keep all neighboring narration, design and entry/exit states. Only their
    # read-only sentence cue arrays are redundant; active cues stay untouched.
    # Rebuild dictionaries to avoid mutating aliased active targets in the copy.
    for key in ('read_only_film_plan', 'next_segment_context'):
        if key in value:
            value[key] = [{k: v for k, v in target.items() if k != 'sentences'}
                          for target in value[key]]
    prior = value.get('previous_segment_context')
    if isinstance(prior, dict):
        value['previous_segment_context'] = {k: v for k, v in prior.items()
                                             if k != 'sentences'}
    return value
