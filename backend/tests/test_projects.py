from conftest import login
import httpx
import pytest
from uuid import UUID
from sqlalchemy import func, select

from app.models import ObjectCleanup, OutlineJob, VideoProject, VideoSegment, VideoVersion


async def add_video_version(db, project, *, status='succeeded', media_key='videos/final.mp4', number=1):
    job = OutlineJob(owner_id=project.owner_id, project_id=project.id, kind='video',
                     idempotency_key=f'version-{number}', expected_revision=project.revision, status='succeeded')
    db.add(job)
    await db.flush()
    version = VideoVersion(owner_id=project.owner_id, project_id=project.id, job_id=job.id,
                           number=number, outline_revision=project.revision, snapshot={},
                           status=status, media_key=media_key)
    db.add(version)
    await db.flush()
    return version


async def create(client, **kwargs):
    response = await client.post('/api/projects', json={'prompt': '讲解二次函数', **kwargs})
    assert response.status_code == 201, response.text
    return response.json()


async def test_project_crud_and_revision(teacher_client):
    project = await create(teacher_client)
    assert project['status'] == 'draft' and project['revision'] == 1
    response = await teacher_client.patch(f"/api/projects/{project['id']}", json={'revision': 1, 'prompt': '用投篮讲二次函数'})
    assert response.status_code == 200, response.text
    assert response.json()['revision'] == 2
    stale = await teacher_client.patch(f"/api/projects/{project['id']}", json={'revision': 1, 'prompt': '旧内容'})
    assert stale.status_code == 409
    listing = (await teacher_client.get('/api/projects?scope=drafts')).json()
    assert listing['total'] == 1 and listing['items'][0]['prompt'] == '用投篮讲二次函数'
    assert (await teacher_client.delete(f"/api/projects/{project['id']}?revision=2")).status_code == 204
    assert (await teacher_client.get(f"/api/projects/{project['id']}")).status_code == 404


@pytest.mark.parametrize('queued_key', ['', 'videos/shared.mp4'])
async def test_project_delete_ignores_empty_and_already_queued_object_keys(app, teacher_client, db, queued_key):
    project = await create(teacher_client, title='含空素材键的项目')
    project_id = UUID(project['id'])
    row = await db.get(VideoProject, project_id)
    version = await add_video_version(db, row)
    db.add(VideoSegment(
        version_id=version.id,
        outline_segment_id=UUID('00000000-0000-0000-0000-000000000001'),
        position=0,
        title='片段',
        narration='旁白',
        assets={'audio_instruction': '', 'visual_instruction': '', 'audio': 'videos/shared.mp4', 'hashes': {}},
    ))
    db.add(ObjectCleanup(object_key=queued_key))
    await db.commit()

    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url='http://test', cookies=teacher_client.cookies) as client:
        response = await client.delete(f"/api/projects/{project['id']}?revision={project['revision']}")

    assert response.status_code == 204, response.text
    assert await db.scalar(select(func.count()).select_from(VideoProject).where(VideoProject.id == project_id)) == 0
    queued_keys = (await db.scalars(select(ObjectCleanup.object_key))).all()
    expected_keys = ['videos/final.mp4', 'videos/shared.mp4']
    if queued_key == '':
        expected_keys.insert(0, '')
    assert sorted(queued_keys) == expected_keys


async def test_project_delete_does_not_queue_modification_instructions(teacher_client, db):
    project = await create(teacher_client)
    row = await db.get(VideoProject, UUID(project['id']))
    version = await add_video_version(db, row)
    db.add(VideoSegment(
        version_id=version.id,
        outline_segment_id=UUID('00000000-0000-0000-0000-000000000002'),
        position=0, title='片段', narration='旁白',
        assets={'audio_instruction': '放慢语速', 'visual_instruction': '放大图像', 'captions': 'videos/captions.json'},
    ))
    await db.commit()

    response = await teacher_client.delete(f"/api/projects/{project['id']}?revision={project['revision']}")

    assert response.status_code == 204, response.text
    assert sorted((await db.scalars(select(ObjectCleanup.object_key))).all()) == ['videos/captions.json', 'videos/final.mp4']


async def test_project_lists_separate_completed_videos_from_drafts(teacher_client, db):
    draft = await create(teacher_client, title='未完成')
    completed = await create(teacher_client, title='已完成')
    row = await db.get(VideoProject, UUID(completed['id']))
    row.status = 'completed'
    await add_video_version(db, row)
    await db.commit()

    completed_listing = (await teacher_client.get('/api/projects?scope=completed')).json()
    assert completed_listing['total'] == 1
    assert completed_listing['items'][0]['id'] == completed['id']

    drafts_listing = (await teacher_client.get('/api/projects?scope=drafts')).json()
    assert drafts_listing['total'] == 1
    assert drafts_listing['items'][0]['id'] == draft['id']


@pytest.mark.parametrize('project_status,version_status,media_key,exported', [
    ('completed', None, None, False),
    ('preview_ready', 'preview_ready', None, False),
    ('video_exporting', 'preview_ready', None, False),
    ('video_failed', 'failed', None, False),
    ('completed', 'succeeded', None, False),
    ('completed', 'succeeded', '', False),
    ('completed', 'failed', 'videos/incomplete.mp4', False),
    ('completed', 'succeeded', 'videos/final.mp4', True),
    ('outline_ready', 'succeeded', 'videos/final.mp4', True),
    ('video_generating', 'succeeded', 'videos/final.mp4', True),
    ('preview_ready', 'succeeded', 'videos/final.mp4', True),
    ('video_exporting', 'succeeded', 'videos/final.mp4', True),
    ('video_failed', 'succeeded', 'videos/final.mp4', True),
])
async def test_project_lists_follow_successful_mp4_export(teacher_client, db, project_status, version_status, media_key, exported):
    project = await create(teacher_client, title='按导出结果分类')
    row = await db.get(VideoProject, UUID(project['id']))
    row.status = project_status
    if version_status is not None:
        await add_video_version(db, row, status=version_status, media_key=media_key)
    await db.commit()

    for scope, expected in [('completed', exported), ('drafts', not exported)]:
        response = await teacher_client.get(f'/api/projects?scope={scope}')
        assert response.status_code == 200, response.text
        listing = response.json()
        assert listing['total'] == int(expected)
        assert [item['id'] for item in listing['items']] == ([project['id']] if expected else [])
    assert (await teacher_client.get('/api/projects?scope=all')).json()['total'] == 1


async def test_exported_project_is_counted_once_and_isolated_by_owner(teacher_client, db, make_user):
    project = await create(teacher_client)
    row = await db.get(VideoProject, UUID(project['id']))
    row.status = 'preview_ready'
    await add_video_version(db, row, number=1)
    await add_video_version(db, row, number=2)
    other = await make_user('teacher-export-other')
    other_project = VideoProject(owner_id=other.id, title='其他教师的成片', prompt='其他教师')
    db.add(other_project)
    await db.flush()
    await add_video_version(db, other_project)
    await db.commit()

    listing = (await teacher_client.get('/api/projects?scope=completed&page_size=1')).json()
    assert listing['total'] == 1
    assert [item['id'] for item in listing['items']] == [project['id']]
    assert (await teacher_client.get('/api/projects?scope=completed&page_size=1&page=2')).json()['items'] == []
    assert (await teacher_client.get('/api/projects?scope=drafts')).json()['total'] == 0


async def test_project_owner_isolation(teacher_client, app, make_client, make_user, admin_client):
    project = await create(teacher_client)
    await make_user('teacher2')
    other = make_client(app)
    await login(other, 'teacher2', 'pass1234')
    for client in (other, admin_client):
        assert (await client.get('/api/projects')).json()['total'] == 0
        path = f"/api/projects/{project['id']}"
        assert (await client.get(path)).status_code == 404
        assert (await client.patch(path, json={'revision': 1, 'prompt': '篡改'})).status_code == 404
        assert (await client.delete(path + '?revision=1')).status_code == 404


async def test_project_requires_active_account(client, make_user):
    assert (await client.get('/api/projects')).status_code == 401
    await make_user('pending1', status='pending')
    await login(client, 'pending1', 'pass1234')
    assert (await client.post('/api/projects', json={'prompt': 'test'})).status_code == 403


async def test_empty_prompt_rejected(teacher_client):
    assert (await teacher_client.post('/api/projects', json={'prompt': '   '})).status_code == 422


async def test_legacy_draft_style_is_ignored_without_invalidating_confirmed_outline(teacher_client, app):
    from uuid import UUID
    from app.models import VideoProject
    project = await create(teacher_client, prompt='用水墨风格讲一次函数')
    async with app.state.sessionmaker() as db:
        row = await db.get(VideoProject, UUID(project['id']))
        row.form_values = {**row.form_values, 'style': 'old-custom-style'}
        row.outline = {'segments': [{'title': '观察图像'}]}
        row.status = 'outline_confirmed'
        await db.commit()
    response = await teacher_client.patch(f"/api/projects/{project['id']}", json={
        'revision': project['revision'], 'prompt': project['prompt'],
        'form_values': {**project['form_values'], 'style': 'old-custom-style'},
    })
    assert response.status_code == 200, response.text
    saved = response.json()
    assert 'style' not in saved['form_values']
    assert saved['prompt'] == '用水墨风格讲一次函数'
    assert saved['status'] == 'outline_confirmed'
    assert saved['needs_regeneration'] is False


async def test_works_cards_download_latest_successful_mp4_even_during_new_revision(teacher_client,db):
    project=await create(teacher_client);row=await db.get(VideoProject,UUID(project['id']))
    first=await add_video_version(db,row,number=1)
    latest=await add_video_version(db,row,number=2)
    await add_video_version(db,row,number=3,status='failed',media_key='videos/failed.mp4')
    await add_video_version(db,row,number=4,status='preview_ready',media_key=None)
    row.status='video_generating';await db.commit()
    items=(await teacher_client.get('/api/projects?scope=completed')).json()['items']
    assert items[0]['download_url']==f"/api/projects/{project['id']}/videos/{latest.id}/media/final?download=1"
    assert str(first.id) not in items[0]['download_url']
    draft=await create(teacher_client,title='还没导出')
    drafts=(await teacher_client.get('/api/projects?scope=drafts')).json()['items']
    assert next(p for p in drafts if p['id']==draft['id'])['download_url'] is None
