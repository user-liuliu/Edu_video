from conftest import login


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


async def test_project_lists_separate_completed_videos_from_drafts(teacher_client, app):
    draft = await create(teacher_client, title='未完成')
    completed = await create(teacher_client, title='已完成')
    from sqlalchemy import update
    from app.models import VideoProject
    async with app.state.sessionmaker() as db:
        await db.execute(update(VideoProject).where(VideoProject.id == completed['id']).values(status='completed'))
        await db.commit()

    completed_listing = (await teacher_client.get('/api/projects?scope=completed')).json()
    assert completed_listing['total'] == 1
    assert completed_listing['items'][0]['id'] == completed['id']

    drafts_listing = (await teacher_client.get('/api/projects?scope=drafts')).json()
    assert drafts_listing['total'] == 1
    assert drafts_listing['items'][0]['id'] == draft['id']


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
