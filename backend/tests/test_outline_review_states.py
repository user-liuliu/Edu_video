from uuid import UUID
from unittest.mock import AsyncMock
import pytest
from langgraph.checkpoint.memory import InMemorySaver
from app.models import VideoProject
from app.outline.graph import build_outline_graph
from app.outline.schemas import JobRequest
from app.outline.service import start_outline
from test_outline_edit import segment


def reviewed(passed=True):
    return {**segment(), 'review_passed': passed, 'review_issues': [] if passed else ['公式错误，请修改'], 'review_notes': ['建议补充例子']}


async def project_with_outline(db, teacher_client, segments):
    response = await teacher_client.post('/api/projects', json={'prompt': '串联电路'})
    p = await db.get(VideoProject, UUID(response.json()['id']))
    p.outline = {'segments': segments}; p.status = 'outline_ready'
    await db.commit()
    return p, '/api/projects/' + str(p.id) + '/outline'


async def test_confirm_requires_explicit_save_even_when_all_segments_pass(db, teacher_client):
    p, path = await project_with_outline(db, teacher_client, [reviewed()])
    initial = (await teacher_client.get(path)).json()
    assert initial['needs_save'] is True
    result = await teacher_client.post(path + '/confirm', json={'revision': 1})
    assert result.status_code == 409
    assert result.json()['detail']['code'] == 'outline_save_required'
    saved = (await teacher_client.put(path, json={'revision': 1, 'segments': initial['segments']})).json()
    assert saved['needs_save'] is False
    result = await teacher_client.post(path + '/confirm', json={'revision': saved['revision']})
    assert result.status_code == 200, result.text


@pytest.mark.parametrize('status', ['pending', 'failed', 'legacy'])
async def test_save_keeps_unapproved_work_but_confirm_rejects_it(db, teacher_client, status):
    s = reviewed(status != 'failed')
    if status == 'pending': s['reviewed_revision'] = 0
    if status == 'legacy': s.pop('review_passed'); s.pop('review_issues')
    p, path = await project_with_outline(db, teacher_client, [s])
    response = await teacher_client.put(path, json={'revision': 1, 'segments': [s]})
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved['needs_save'] is False
    result = await teacher_client.post(path + '/confirm', json={'revision': saved['revision']})
    assert result.status_code == 409
    assert result.json()['detail']['code'] == 'review_required'


async def test_save_cannot_forge_review_and_edit_invalidates_result(db, teacher_client):
    s = reviewed(False)
    p, path = await project_with_outline(db, teacher_client, [s])
    forged = {**s, 'review_passed': True, 'review_issues': [], 'review_notes': [], 'reviewed_revision': 999}
    saved = (await teacher_client.put(path, json={'revision': 1, 'segments': [forged]})).json()
    assert saved['segments'][0]['review_passed'] is False
    assert saved['segments'][0]['review_issues'] == ['公式错误，请修改']
    forged['narration'] = '已修改的讲稿'
    saved = (await teacher_client.put(path, json={'revision': saved['revision'], 'segments': [forged]})).json()
    assert saved['segments'][0]['review_passed'] is None
    assert saved['segments'][0]['reviewed_revision'] != saved['segments'][0]['content_revision']
    assert saved['segments'][0]['review_issues'] == []


async def test_review_selects_failed_pending_and_legacy_but_not_passed(db, teacher_client, box, monkeypatch):
    approved, rejected, pending, legacy = reviewed(), reviewed(False), reviewed(), segment()
    pending['reviewed_revision'] = 0
    p, path = await project_with_outline(db, teacher_client, [approved, rejected, pending, legacy])
    monkeypatch.setattr('app.outline.service.system_available', AsyncMock(return_value=True))
    teacher = type('Teacher', (), {'id': p.owner_id})()
    job = await start_outline(db, teacher, p.id, JobRequest(revision=1, idempotency_key='recheck'), 'review', box)
    assert job.payload['segment_ids'] == [rejected['id'], pending['id'], legacy['id']]


async def test_review_replaces_old_issues_preserves_unselected_and_save_receipt():
    from app.outline.review import mark_saved, needs_save
    bad, good = reviewed(False), reviewed()
    original = mark_saved({'segments': [bad, good]})
    async def no_generate(state): raise AssertionError('review must not regenerate')
    async def review(state):
        return {bad['id']: {'passed': True, 'issues': [], 'notes': ['可增加例子']}}
    graph = build_outline_graph(InMemorySaver(), no_generate, review)
    result = await graph.ainvoke({'outline': original, 'evidence': [], 'form_values': {}, 'operation': 'review', 'segment_ids': [bad['id']]}, {'configurable': {'thread_id': 'recheck'}})
    first, second = result['outline']['segments']
    assert first['review_passed'] is True and first['review_issues'] == []
    assert '公式错误，请修改' not in first['review_notes']
    assert '可增加例子' in first['review_notes']
    assert second == good
    assert needs_save(result['outline']) is False


async def test_explicit_rejection_is_a_successful_review_result_and_warnings_do_not_fail_it():
    s = segment()
    async def generate(state): return {'segments': [s]}
    async def review(state): return {s['id']: {'passed': False, 'issues': ['公式错误'], 'notes': ['建议补充单位']}}
    graph = build_outline_graph(InMemorySaver(), generate, review)
    result = await graph.ainvoke({'evidence': [], 'form_values': {}, 'operation': 'generate'}, {'configurable': {'thread_id': 'reject'}})
    current = result['outline']['segments'][0]
    assert current['review_passed'] is False
    assert current['review_issues'] == ['公式错误']
    assert current['reviewed_revision'] == current['content_revision']
    assert result['__interrupt__']


async def test_malformed_verdict_never_publishes_a_rejection_or_pass():
    import copy
    original = {'segments': [reviewed(False)]}
    before = copy.deepcopy(original)
    async def unused(state): raise AssertionError('review only')
    async def broken(state): return {original['segments'][0]['id']: {'passed': 'false', 'issues': [], 'notes': []}}
    graph = build_outline_graph(InMemorySaver(), unused, broken)
    with pytest.raises(ValueError):
        await graph.ainvoke({'outline': original, 'operation': 'review', 'evidence': [], 'form_values': {}}, {'configurable': {'thread_id': 'malformed'}})
    assert original == before


def test_strict_review_results_accept_advice_but_require_explicit_valid_verdicts():
    from app.outline.review import normalize_review_results
    assert normalize_review_results({'items': [{'segment_id': 'a', 'passed': True, 'issues': [], 'notes': ['建议补例']}]}, ['a']) == {'a': {'passed': True, 'issues': [], 'notes': ['建议补例']}}
    invalid = [
        {'items': [{'segment_id': 'a', 'notes': []}]},
        {'items': [{'segment_id': 'a', 'passed': 'false', 'issues': [], 'notes': []}]},
        {'items': [{'segment_id': 'a', 'passed': False, 'issues': [' '], 'notes': []}]},
        {'items': [{'segment_id': 'a', 'passed': True, 'issues': ['错误'], 'notes': []}]},
        {'items': []},
        {'items': [{'segment_id': 'other', 'passed': True, 'issues': [], 'notes': []}]},
        {'items': [{'segment_id': 'a', 'passed': True, 'issues': [], 'notes': []}] * 2},
        {'notes': {'a': []}},
    ]
    for value in invalid:
        with pytest.raises(ValueError): normalize_review_results(value, ['a'])


def test_save_receipt_tracks_identity_order_and_content_not_review_metadata():
    import copy
    from app.outline.review import mark_saved, needs_save
    first, second = reviewed(), reviewed()
    original = mark_saved({'segments': [first, second]})
    altered = copy.deepcopy(original)
    altered['segments'][0].update(review_passed=False, review_issues=['新审核问题'], reviewed_revision=2)
    assert needs_save(altered) is False
    altered['segments'].reverse()
    assert needs_save(altered) is True
    altered = copy.deepcopy(original)
    altered['segments'][0]['narration'] += '新内容'
    assert needs_save(altered) is True


async def test_reorder_save_keeps_review_and_rejects_confirmation_of_stale_version(db, teacher_client):
    p, path = await project_with_outline(db, teacher_client, [reviewed(), reviewed()])
    segments = p.outline['segments']
    response = await teacher_client.put(path, json={'revision': 1, 'segments': segments[::-1]})
    assert response.status_code == 200
    saved = response.json()
    assert [s['id'] for s in saved['segments']] == [segments[1]['id'], segments[0]['id']]
    assert all(s['review_passed'] is True for s in saved['segments'])
    assert (await teacher_client.post(path + '/confirm', json={'revision': 1})).status_code == 409
    assert (await teacher_client.post(path + '/confirm', json={'revision': saved['revision']})).status_code == 200


async def test_worker_review_timeout_does_not_publish_a_verdict(db, teacher_client, settings, monkeypatch):
    import copy
    from uuid import uuid4
    from app.jobs.service import create_job
    from app.outline.service import execute_outline_job
    from app.jobs.setup import initialize_agent_state
    from app.model_configs.schemas import ResolvedConfig
    from app.purposes import Purpose
    from sqlalchemy import text
    schema = 'agent_test_' + uuid4().hex
    isolated = settings.model_copy(update={'agent_schema': schema})
    await initialize_agent_state(isolated)
    try:
        pending = reviewed(); pending['review_passed'] = None; pending['reviewed_revision'] = 0
        pending['visuals'] *= 3
        p, path = await project_with_outline(db, teacher_client, [pending])
        before = copy.deepcopy(p.outline)
        version = (await teacher_client.get('/api/config/form')).json()['form_version']
        job = await create_job(db, p, 'review', 'timeout', {'segment_ids': [pending['id']], 'form_version': version})
        job.status = 'running'; job.lease_token = uuid4(); await db.commit()
        async def resolve(db, box, purpose):
            if purpose not in (Purpose.outline_llm, Purpose.review_llm): return None
            return ResolvedConfig(purpose, 'https://mock.invalid/v1', 'test-key', 'test', {})
        async def timeout(*args, **kwargs): raise ValueError('模型调用超时，请稍后重试')
        monkeypatch.setattr('app.outline.service.resolve', resolve)
        monkeypatch.setattr('app.outline.service.chat_json', timeout)
        with pytest.raises(ValueError, match='模型调用超时'):
            await execute_outline_job(db, job, isolated)
        await db.rollback(); await db.refresh(p)
        assert p.outline == before
        assert p.outline['segments'][0]['review_passed'] is None
    finally:
        await db.rollback()
        await db.execute(text('DROP SCHEMA ' + schema + ' CASCADE')); await db.commit()
