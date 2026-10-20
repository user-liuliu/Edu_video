from copy import deepcopy
from uuid import UUID

import pytest
from sqlalchemy import select

from app.jobs.service import create_job
from app.models import VideoProject, ModelConfigRow, OutlineJob
from app.outline.review import mark_saved
from app.settings_store import GenerationParams, put_generation_params
from test_outline_review_states import reviewed


async def ready_project(db, client, box):
    result = await client.post('/api/projects', json={'title': '一次函数', 'prompt': '讲解一次函数'})
    project = await db.get(VideoProject, UUID(result.json()['id']))
    # These existing model-voice scenarios explicitly exercise the configured TTS.
    project.form_values={**project.form_values,'voice':'voice'}
    project.outline = mark_saved({'segments': [reviewed()]})
    project.status = 'outline_confirmed'
    for purpose in ('outline_llm', 'tts', 'review_llm'):
        if not await db.get(ModelConfigRow, purpose):
            db.add(ModelConfigRow(purpose=purpose, enabled=True, base_url='https://model.invalid/v1', model='model', api_key_encrypted=box.encrypt('test-key'), extra={'voices': [{'speaker_id': 'voice', 'label': '讲师'}]} if purpose == 'tts' else {}))
    await db.commit()
    return project, f'/api/projects/{project.id}/videos'


async def test_legacy_draft_style_does_not_enter_new_video_model_context(db, teacher_client, box):
    from app.models import VideoVersion
    project, path = await ready_project(db, teacher_client, box)
    project.form_values = {**project.form_values, 'style': 'old-custom-style'}
    await db.commit()
    response = await teacher_client.post(path, json={'revision': 1, 'idempotency_key': 'retired-style'})
    assert response.status_code == 202, response.text
    version = await db.get(VideoVersion, UUID(response.json()['id']))
    assert 'style' not in version.snapshot['form_values']
    assert version.snapshot['style']['value'] == 'science_animation'
    assert version.snapshot['style']['source'] == 'subject'


@pytest.mark.parametrize('broken,code', [('unconfirmed','outline_confirmation_required'), ('unsaved','outline_save_required'), ('pending','review_required'), ('failed','review_required'), ('changed','regeneration_required')])
async def test_video_rejects_unapproved_or_unconfirmed_outline(db, teacher_client, box, broken, code):
    project, path = await ready_project(db, teacher_client, box)
    if broken == 'unconfirmed': project.status = 'outline_ready'
    elif broken == 'changed': project.needs_regeneration = True
    else:
        value = deepcopy(project.outline)
        if broken == 'unsaved': value.pop('saved_content_hash')
        elif broken == 'pending': value['segments'][0]['reviewed_revision'] = 0
        else: value['segments'][0]['review_passed'] = False
        project.outline = value
    await db.commit()
    response = await teacher_client.post(path, json={'revision': 1, 'idempotency_key': 'bad'})
    assert response.status_code == 409, response.text
    assert response.json()['detail']['code'] == code
    assert not (await db.scalars(select(OutlineJob).where(OutlineJob.kind == 'video'))).all()


async def test_video_versions_snapshot_idempotency_and_owner_isolation(db, teacher_client, admin_client, box):
    project, path = await ready_project(db, teacher_client, box)
    response = await teacher_client.post(path, json={'revision': 1, 'idempotency_key': 'once'})
    assert response.status_code == 202, response.text
    first = response.json()
    assert first['job']['kind'] == 'video' and first['status'] == 'queued'
    assert first['outline_revision'] == 1
    again = await teacher_client.post(path, json={'revision': 1, 'idempotency_key': 'once'})
    assert again.status_code == 202 and again.json()['id'] == first['id']
    assert (await admin_client.get(path)).status_code == 404
    assert (await admin_client.get(path+'/'+first['id'])).status_code == 404
    assert (await admin_client.post(path, json={'revision': 1, 'idempotency_key': 'other'})).status_code == 404
    assert (await teacher_client.get(path+'/'+first['id'])).json()['segments'][0]['narration'] == '同学们好'
    assert 'test-key' not in response.text and 'model.invalid' not in response.text
    assert (await teacher_client.post(path, json={'revision': 1, 'idempotency_key': 'different'})).status_code == 409
    from app.models import VideoVersion
    stored = await db.get(VideoVersion, UUID(first['id']))
    assert stored.snapshot['outline']['segments'][0]['narration'] == '同学们好'
    project.outline = mark_saved({'segments': [{**reviewed(), 'narration': '下一版'}]})
    await db.commit()
    await db.refresh(stored)
    assert stored.snapshot['outline']['segments'][0]['narration'] == '同学们好'


async def test_video_and_outline_share_each_teachers_capacity(db, teacher_client, box):
    project, path = await ready_project(db, teacher_client, box)
    other = VideoProject(owner_id=project.owner_id, title='另一个', prompt='另一个')
    db.add(other); await db.flush()
    await create_job(db, other, 'generate', 'outline', {})
    await put_generation_params(db, GenerationParams(max_concurrent_jobs=1))
    response = await teacher_client.post(path, json={'revision': 1, 'idempotency_key': 'limit'})
    assert response.status_code == 409
    assert response.json()['detail']['message'] == '超出最大任务数：已存在1个生成任务'


async def test_failed_new_video_preserves_successful_version_and_retry_snapshot(db, teacher_client, box):
    from app.models import VideoVersion
    project, path = await ready_project(db, teacher_client, box)
    first = (await teacher_client.post(path, json={'revision': 1, 'idempotency_key': 'first'})).json()
    version = await db.get(VideoVersion, UUID(first['id']))
    job = await db.get(OutlineJob, UUID(first['job']['id']))
    version.status, job.status, project.status = 'succeeded', 'succeeded', 'completed'
    version.media_key = 'private/old.mp4'
    await db.commit()
    second = await teacher_client.post(path, json={'revision': 1, 'idempotency_key': 'second'})
    assert second.status_code == 202, second.text
    assert (await teacher_client.get(path+'/'+first['id'])).json()['status'] == 'succeeded'
    pending = await db.get(VideoVersion, UUID(second.json()['id']))
    pending_job = await db.get(OutlineJob, UUID(second.json()['job']['id']))
    pending.status, pending_job.status, project.status = 'failed', 'failed', 'video_failed'
    await db.commit()
    retry = await teacher_client.post(path, json={'revision': 1, 'idempotency_key': 'retry', 'retry_version_id': str(pending.id)})
    assert retry.status_code == 202, retry.text
    assert retry.json()['source_version_id'] == str(pending.id)
    assert len((await teacher_client.get(path)).json()) == 3
