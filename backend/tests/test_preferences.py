async def test_preferences_owner_and_fixed_categories(teacher_client,admin_client):
    body={'category':'expression','value':'简洁清晰'}
    response=await teacher_client.post('/api/preferences',json=body)
    assert response.status_code==201,response.text
    identifier=response.json()['id']
    assert (await admin_client.patch('/api/preferences/'+identifier,json=body)).status_code==404
    assert (await admin_client.delete('/api/preferences/'+identifier)).status_code==404
    assert (await teacher_client.post('/api/preferences',json={'category':'expression','value':'秦始皇于公元前221年统一六国'})).status_code==422
    assert (await teacher_client.get('/api/preferences')).json()['items'][0]['value']=='简洁清晰'

async def test_preference_suggestions_need_acceptance_and_global_switch(db,teacher_client,admin_client):
    from uuid import UUID
    from app.models import VideoProject,OutlineJob
    from app.jobs.service import create_job
    from app.settings_store import GenerationParams,put_generation_params
    from app.preferences.service import sync_store
    from unittest.mock import AsyncMock
    p=(await teacher_client.post('/api/projects',json={'prompt':'数学'})).json()
    project=await db.get(VideoProject,UUID(p['id']))
    for i in range(2):
        job=await create_job(db,project,'rewrite',str(i),{'instruction':'请简洁清晰，多用生活实例'})
        job.status='succeeded'
    await db.commit()
    data=(await teacher_client.get('/api/preferences')).json()
    assert not data['items'] and len(data['suggestions'])==2
    suggestion=data['suggestions'][0]
    path='/api/preferences/suggestions/'+suggestion['id']+'/accept'
    assert (await admin_client.post(path)).status_code==404
    assert (await teacher_client.post(path)).status_code==201
    data=(await teacher_client.get('/api/preferences')).json()
    assert len(data['items'])==1 and len(data['suggestions'])==1
    store=AsyncMock();store.asearch.return_value=[]
    values=await sync_store(db,store,project.owner_id)
    assert values==[{'category':suggestion['category'],'value':suggestion['value']}]
    assert store.aput.call_args.args[0]==('users',str(project.owner_id),'preferences')
    await put_generation_params(db,GenerationParams(long_term_memory_enabled=False))
    data=(await teacher_client.get('/api/preferences')).json()
    assert data['enabled'] is False and data['items']==[] and data['suggestions']==[]
    assert (await teacher_client.post('/api/preferences',json={'category':'expression','value':'简洁清晰'})).status_code==409
    await put_generation_params(db,GenerationParams())
    assert len((await teacher_client.get('/api/preferences')).json()['items'])==1
