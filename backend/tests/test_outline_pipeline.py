from uuid import UUID, uuid4

from sqlalchemy import select

from app.jobs.service import create_job
from app.jobs.tasks import run_job
from app.models import Material, OutlineJob, VideoProject


async def submit_with_material(db, teacher_client, monkeypatch, status='stored'):
    async def available(*args):
        return True
    monkeypatch.setattr('app.outline.service.system_available', available)
    data = (await teacher_client.post('/api/projects', json={'prompt': '串联电路'})).json()
    project = await db.get(VideoProject, UUID(data['id']))
    material = Material(owner_id=project.owner_id, project_id=project.id, filename='电路.docx',
                        object_key='test/private', content_type='application/octet-stream', size=100, status=status)
    db.add(material)
    await db.commit()
    version = (await teacher_client.get('/api/config/form')).json()['form_version']
    body = {'revision': project.revision, 'form_version': version, 'idempotency_key': str(uuid4())}
    response = await teacher_client.post(f'/api/projects/{project.id}/outline/generate', json=body)
    return project, material, response, body


async def test_generate_persists_material_dependencies_and_reserves_one_slot(db, teacher_client, monkeypatch):
    project, material, response, body = await submit_with_material(db, teacher_client, monkeypatch)
    assert response.status_code == 202, response.text
    await db.refresh(project)
    await db.refresh(material)
    assert project.status == 'outlining'
    assert material.status == 'pending'
    jobs = (await db.scalars(select(OutlineJob).where(OutlineJob.project_id == project.id))).all()
    assert sorted(job.kind for job in jobs) == ['generate', 'parse']
    parent = next(job for job in jobs if job.kind == 'generate')
    child = next(job for job in jobs if job.kind == 'parse')
    assert parent.payload['material_job_ids'] == [str(child.id)]
    from app.jobs.service import count_active_generation_jobs
    assert await count_active_generation_jobs(db, project.owner_id) == 1
    duplicate = await teacher_client.post(f'/api/projects/{project.id}/outline/generate', json=body)
    assert duplicate.status_code == 202
    assert duplicate.json()['id'] == response.json()['id']


async def test_waiting_dependencies_do_not_consume_attempts_or_call_outline_model(db, teacher_client, settings, monkeypatch):
    project, material, response, _ = await submit_with_material(db, teacher_client, monkeypatch)
    assert response.status_code == 202, response.text
    called = []
    async def execute(*args):
        called.append(True)
    monkeypatch.setattr('app.outline.service.execute_outline_job', execute)
    job_id = UUID(response.json()['id'])
    await run_job(job_id, settings)
    job = await db.get(OutlineJob, job_id, populate_existing=True)
    assert job.status == 'pending'
    assert job.attempts == 0
    assert job.lease_token is None
    assert not called
    child = await db.scalar(select(OutlineJob).where(OutlineJob.project_id == project.id, OutlineJob.kind == 'parse'))
    child.status = 'succeeded'
    material.status = 'ready'
    await db.commit()
    await run_job(job_id, settings)
    await db.refresh(job)
    assert job.status == 'succeeded'
    assert called == [True]


async def test_failed_dependency_stops_generation_and_keeps_old_outline(db, teacher_client, settings, monkeypatch):
    project, material, response, _ = await submit_with_material(db, teacher_client, monkeypatch)
    assert response.status_code == 202, response.text
    project.outline = {'segments': []}
    child = await db.scalar(select(OutlineJob).where(OutlineJob.project_id == project.id, OutlineJob.kind == 'parse'))
    child.status = 'failed'
    material.status = 'failed'
    material.error_message = '文档损坏，请重新上传'
    await db.commit()
    async def never(*args):
        raise AssertionError('解析失败不能调用大纲模型')
    monkeypatch.setattr('app.outline.service.execute_outline_job', never)
    await run_job(response.json()['id'], settings)
    job = await db.get(OutlineJob, UUID(response.json()['id']), populate_existing=True)
    await db.refresh(project)
    assert job.status == 'failed'
    assert '文档损坏' in job.error_message
    assert project.outline == {'segments': []}
    assert project.status == 'failed'


async def test_existing_parse_is_reused_and_failed_material_can_be_retried(db, teacher_client, monkeypatch):
    project, material, response, _ = await submit_with_material(db, teacher_client, monkeypatch, status='failed')
    assert response.status_code == 202, response.text
    await db.refresh(material)
    assert material.status == 'pending'
    jobs = (await db.scalars(select(OutlineJob).where(OutlineJob.project_id == project.id))).all()
    child = next(job for job in jobs if job.kind == 'parse')
    parent = next(job for job in jobs if job.kind == 'generate')
    parent.status = 'failed'
    project.status = 'failed'
    await db.commit()
    version = (await teacher_client.get('/api/config/form')).json()['form_version']
    second = await teacher_client.post(f'/api/projects/{project.id}/outline/generate', json={
        'revision': project.revision, 'form_version': version, 'idempotency_key': str(uuid4()),
    })
    assert second.status_code == 202, second.text
    jobs = (await db.scalars(select(OutlineJob).where(OutlineJob.project_id == project.id))).all()
    assert len([job for job in jobs if job.kind == 'parse']) == 1
    new_parent = next(job for job in jobs if str(job.id) == second.json()['id'])
    assert new_parent.payload['material_job_ids'] == [str(child.id)]


async def test_over_capacity_creates_no_parse_jobs_or_material_state_change(db, teacher_client, monkeypatch):
    from app.settings_store import GenerationParams, put_generation_params
    await put_generation_params(db, GenerationParams(max_concurrent_jobs=1))
    first, _, response, _ = await submit_with_material(db, teacher_client, monkeypatch)
    assert response.status_code == 202
    second, material, rejected, _ = await submit_with_material(db, teacher_client, monkeypatch)
    assert rejected.status_code == 409
    assert rejected.json()['detail']['message'] == '超出最大任务数：已存在1个生成任务'
    await db.refresh(material)
    assert material.status == 'stored'
    assert not (await db.scalars(select(OutlineJob).where(OutlineJob.project_id == second.id))).all()


async def test_lowering_capacity_allows_accepted_queue_to_drain(db,teacher_client,settings,monkeypatch):
    from app.settings_store import GenerationParams,put_generation_params
    data=(await teacher_client.post('/api/projects',json={'prompt':'函数'})).json()
    project=await db.get(VideoProject,UUID(data['id']))
    other=VideoProject(owner_id=project.owner_id,title='电路',prompt='电路')
    db.add(other);await db.flush()
    first=await create_job(db,project,'generate','accepted-one',{})
    second=await create_job(db,other,'generate','accepted-two',{})
    await db.commit()
    await put_generation_params(db,GenerationParams(max_concurrent_jobs=1))
    ran=[]
    async def execute(db,job,settings):
        ran.append(job.id)
    monkeypatch.setattr('app.outline.service.execute_outline_job',execute)
    await run_job(first.id,settings)
    await db.refresh(first)
    assert first.status=='succeeded'
    await run_job(second.id,settings)
    await db.refresh(second)
    assert second.status=='succeeded'
    assert ran==[first.id,second.id]
