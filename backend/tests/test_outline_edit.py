from uuid import uuid4
from app.models import VideoProject
from app.outline.schemas import OutlineData

def segment():
    return {'id':str(uuid4()),'position':0,'title':'开场','objective':'理解','narration':'同学们好','visuals':[{'kind':'文字卡','description':'概念'}],'evidence_ids':[],'content_kind':'knowledge','review_notes':['未核实出处'],'estimated_duration_seconds':3,'content_revision':1,'reviewed_revision':1}

async def test_edit_invalidates_only_changed_segment_and_blocks_confirm(db,teacher_client,admin_client):
    p=(await teacher_client.post('/api/projects',json={'prompt':'数学'})).json()
    row=await db.get(VideoProject,__import__('uuid').UUID(p['id']))
    first,second=segment(),segment();second['position']=1
    row.outline={'segments':[first,second]};row.status='outline_ready'
    await db.commit()
    path='/api/projects/'+p['id']+'/outline'
    assert (await admin_client.get(path)).status_code==404
    first['narration']='新的讲稿'
    response=await teacher_client.put(path,json={'revision':1,'segments':[second,first]})
    assert response.status_code==200,response.text
    data=response.json()
    assert data['segments'][0]['reviewed_revision']==1
    assert data['segments'][1]['content_revision']==2
    assert data['segments'][1]['reviewed_revision']==1
    assert (await teacher_client.post(path+'/confirm',json={'revision':data['revision']})).status_code==409
    assert (await teacher_client.put(path,json={'revision':1,'segments':[first]})).status_code==409
