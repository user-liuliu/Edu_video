from uuid import UUID
from app.models import VideoProject
from test_outline_edit import segment

async def test_prompt_change_preserves_snapshot_but_requires_regeneration(db,teacher_client):
    p=(await teacher_client.post('/api/projects',json={'prompt':'物理'})).json()
    row=await db.get(VideoProject,UUID(p['id']));row.outline={'segments':[segment()]};row.status='outline_confirmed';await db.commit()
    response=await teacher_client.patch('/api/projects/'+p['id'],json={'prompt':'数学','revision':1,'form_values':p['form_values']})
    assert response.status_code==200
    assert response.json()['needs_regeneration'] is True
    await db.refresh(row);assert row.outline['segments']
    assert (await teacher_client.post('/api/projects/'+p['id']+'/outline/confirm',json={'revision':2})).status_code==409
