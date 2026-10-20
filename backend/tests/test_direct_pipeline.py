from uuid import UUID
import pytest
from sqlalchemy import select
from app.models import VideoVersion,VideoSegment,ModelConfigRow
from app.jobs.tasks import run_job
from test_videos import ready_project
from direct_fakes import Store,Renderer,external_fakes
from test_direct_html import HTML


async def prepare(db,client,box,settings,monkeypatch):
    project,path=await ready_project(db,client,box)
    store,renderer=Store(),Renderer();counts=external_fakes(monkeypatch,store,renderer)
    calls=[]
    async def generate(config,request,http,**kwargs):
        calls.append(request);return HTML
    async def direct(html,manifest,audio,size,*,validate=False):
        if renderer.fail:raise ValueError('测试渲染失败')
        if validate:return {'validated':True}
        return b'film',{'duration':manifest['duration'],'width':size[0],'height':size[1]}
    renderer.direct=direct
    monkeypatch.setattr('app.videos.direct_pipeline.generate_html',generate)
    monkeypatch.setattr('app.videos.media.MaterialStorage',lambda settings:store)
    return project,path,store,renderer,counts,calls


async def ready(db,client,box,settings,monkeypatch):
    project,path,store,renderer,counts,calls=await prepare(db,client,box,settings,monkeypatch)
    response=await client.post(path,json={'revision':1,'idempotency_key':'direct'})
    assert response.status_code==202,response.text
    await run_job(response.json()['job']['id'],settings)
    result=(await client.get(path+'/'+response.json()['id'])).json()
    assert result['status']=='preview_ready',result
    return project,path,result,store,renderer,counts,calls


async def test_production_default_is_whole_html_not_scene_and_export_is_provider_free(db,teacher_client,admin_client,box,settings,monkeypatch):
    project,path,result,store,renderer,counts,calls=await ready(db,teacher_client,box,settings,monkeypatch)
    assert result['playback_mode']=='whole_html' and result['html_url'] and result['audio_url']
    assert len(calls)==1 and counts=={'speech':1,'scene':0}
    assert (await teacher_client.get(result['html_url'])).status_code==200
    assert (await admin_client.get(result['html_url'])).status_code==404
    assert (await teacher_client.get(result['audio_url'],headers={'Range':'bytes=0-9'})).status_code==206
    for config in (await db.scalars(select(ModelConfigRow))).all():config.enabled=False
    await db.commit()
    async def forbidden(*args,**kwargs):raise AssertionError('No models during export')
    monkeypatch.setattr('app.videos.direct_pipeline.resolve',forbidden)
    response=await teacher_client.post(path+'/'+result['id']+'/export',json={'idempotency_key':'export'})
    assert response.status_code==202,response.text
    await run_job(response.json()['id'],settings)
    exported=(await teacher_client.get(path+'/'+result['id'])).json()
    assert exported['status']=='succeeded' and exported['media_url'],exported
    assert len(calls)==1 and counts=={'speech':1,'scene':0}


async def test_visual_revision_rebuilds_whole_film_reuses_audio_voice_revision_reuses_html(db,teacher_client,box,settings,monkeypatch):
    project,path,result,store,renderer,counts,calls=await ready(db,teacher_client,box,settings,monkeypatch)
    original=await db.get(VideoVersion,UUID(result['id']),populate_existing=True)
    original_audio=original.snapshot['direct_manifest']['hashes']['audio']
    for mode in ('visual','voice'):
        response=await teacher_client.post(path+'/'+result['id']+'/revisions',json={'revision':1,'idempotency_key':mode,'segment_ids':[result['segments'][0]['id']],'instruction':'更自然一些','mode':mode})
        assert response.status_code==202,response.text
        await run_job(response.json()['job']['id'],settings)
        revised=(await teacher_client.get(path+'/'+response.json()['id'])).json()
        assert revised['status']=='preview_ready',revised
        row=await db.get(VideoVersion,UUID(revised['id']),populate_existing=True)
        if mode=='visual':
            assert len(calls)==2 and counts['speech']==1
            assert row.snapshot['direct_manifest']['hashes']['audio']==original_audio
        else:assert len(calls)==2 and counts['speech']==2


async def test_corrupt_whole_film_is_not_exported(db,teacher_client,box,settings,monkeypatch):
    project,path,result,store,renderer,counts,calls=await ready(db,teacher_client,box,settings,monkeypatch)
    row=await db.get(VideoVersion,UUID(result['id']),populate_existing=True)
    store.files[row.snapshot['direct_manifest']['keys']['html']]+=b'bad'
    response=await teacher_client.post(path+'/'+result['id']+'/export',json={'idempotency_key':'bad'})
    assert response.status_code==409


async def test_failed_export_retains_whole_preview_and_retry_uses_no_model(db,teacher_client,box,settings,monkeypatch):
    project,path,result,store,renderer,counts,calls=await ready(db,teacher_client,box,settings,monkeypatch)
    renderer.fail=True
    url=path+'/'+result['id']+'/export'
    response=await teacher_client.post(url,json={'idempotency_key':'fail'})
    await run_job(response.json()['id'],settings)
    failed=(await teacher_client.get(path+'/'+result['id'])).json()
    assert failed['status']=='preview_ready' and failed['html_url'] and failed['export_status']=='failed'
    renderer.fail=False
    retry=await teacher_client.post(url,json={'idempotency_key':'retry'})
    await run_job(retry.json()['id'],settings)
    assert (await teacher_client.get(path+'/'+result['id'])).json()['status']=='succeeded'
    assert len(calls)==1 and counts=={'speech':1,'scene':0}


async def test_runtime_code_repair_keeps_frozen_audio_and_is_bounded(db,teacher_client,box,settings,monkeypatch):
    from app.videos.render_contract import DirectHtmlRuntimeError
    project,path,store,renderer,counts,calls=await prepare(db,teacher_client,box,settings,monkeypatch)
    original=renderer.direct;seen=[]
    async def direct(html,manifest,audio,size,*,validate=False):
        seen.append(audio)
        if len(seen)==1:raise DirectHtmlRuntimeError('renderFrame引用不存在的节点')
        return await original(html,manifest,audio,size,validate=validate)
    renderer.direct=direct
    response=await teacher_client.post(path,json={'revision':1,'idempotency_key':'repair'})
    await run_job(response.json()['job']['id'],settings)
    result=(await teacher_client.get(path+'/'+response.json()['id'])).json()
    assert result['status']=='preview_ready',result
    assert counts=={'speech':1,'scene':0} and len(calls)==2 and seen[0]==seen[1]


async def test_persistent_runtime_error_stops_repairs_and_retains_audio_checkpoint(db,teacher_client,box,settings,monkeypatch):
    from app.videos.render_contract import DirectHtmlRuntimeError
    project,path,store,renderer,counts,calls=await prepare(db,teacher_client,box,settings,monkeypatch)
    async def broken(*args,**kwargs):raise DirectHtmlRuntimeError('动画脚本语法错误：SyntaxError')
    renderer.direct=broken
    response=await teacher_client.post(path,json={'revision':1,'idempotency_key':'bounded-repair'})
    await run_job(response.json()['job']['id'],settings)
    result=(await teacher_client.get(path+'/'+response.json()['id'])).json()
    assert result['status']=='failed' and result['html_url'] is None
    assert 1<len(calls)<=3 and counts=={'speech':1,'scene':0}
    version=await db.get(VideoVersion,UUID(result['id']),populate_existing=True)
    assert version.snapshot['direct_source']['key'] in store.files
    assert 'direct_manifest' not in version.snapshot
    segment=await db.scalar(select(VideoSegment).where(VideoSegment.version_id==version.id))
    assert segment.assets['audio'] in store.files


async def test_failed_preparation_retry_reuses_frozen_html_and_audio(db,teacher_client,box,settings,monkeypatch):
    project,path,store,renderer,counts,calls=await prepare(db,teacher_client,box,settings,monkeypatch)
    renderer.fail=True
    response=await teacher_client.post(path,json={'revision':1,'idempotency_key':'failed'})
    await run_job(response.json()['job']['id'],settings)
    result=(await teacher_client.get(path+'/'+response.json()['id'])).json()
    assert result['status']=='failed' and len(calls)==1 and counts['speech']==1
    renderer.fail=False
    retry=await teacher_client.post(path,json={'revision':1,'idempotency_key':'retry','retry_version_id':result['id']})
    assert retry.status_code==202,retry.text
    await run_job(retry.json()['job']['id'],settings)
    value=(await teacher_client.get(path+'/'+retry.json()['id'])).json()
    assert value['status']=='preview_ready',value
    assert len(calls)==1 and counts['speech']==1


async def test_multiple_sections_form_one_continuous_audio_clock(db,teacher_client,box,settings,monkeypatch):
    from copy import deepcopy
    from uuid import uuid4
    from app.outline.review import mark_saved
    project,path,store,renderer,counts,calls=await prepare(db,teacher_client,box,settings,monkeypatch)
    first=deepcopy(project.outline['segments'][0]);second={**deepcopy(first),'id':str(uuid4()),'position':1}
    project.outline=mark_saved({'segments':[first,second]});await db.commit()
    value=(await teacher_client.post(path,json={'revision':1,'idempotency_key':'multiple'})).json()
    await run_job(value['job']['id'],settings)
    result=(await teacher_client.get(path+'/'+value['id'])).json()
    assert result['status']=='preview_ready',result
    assert len(calls)==1 and counts=={'speech':2,'scene':0}
    assert [s['start'] for s in result['segments']]==[0.,1.]
    assert [s['end'] for s in result['segments']]==[1.,2.]
    row=await db.get(VideoVersion,UUID(result['id']),populate_existing=True)
    from app.videos.direct_html import validate_manifest
    validate_manifest(row.snapshot['direct_manifest']['timeline'])


async def test_stale_lease_cannot_publish_whole_preview(db,teacher_client,box,settings,monkeypatch):
    from datetime import UTC,datetime,timedelta
    from uuid import uuid4
    from sqlalchemy import update
    from app.db import create_sessionmaker
    from app.models import OutlineJob
    project,path,store,renderer,counts,calls=await prepare(db,teacher_client,box,settings,monkeypatch)
    response=await teacher_client.post(path,json={'revision':1,'idempotency_key':'stale'})
    async def revoke(*args,**kwargs):
        async with create_sessionmaker(db.bind)() as other:
            await other.execute(update(OutlineJob).where(OutlineJob.id==UUID(response.json()['job']['id'])).values(lease_token=uuid4(),lease_until=datetime.now(UTC)+timedelta(seconds=90)))
            await other.commit()
        return {'validated':True}
    renderer.direct=revoke
    await run_job(response.json()['job']['id'],settings)
    result=(await teacher_client.get(path+'/'+response.json()['id'])).json()
    assert result['status']=='running' and result['html_url'] is None
    row=await db.get(VideoVersion,UUID(result['id']),populate_existing=True)
    assert 'direct_manifest' not in row.snapshot


async def test_new_pipeline_does_not_require_video_review_model(db,teacher_client,box,settings,monkeypatch):
    project,path,store,renderer,counts,calls=await prepare(db,teacher_client,box,settings,monkeypatch)
    config=await db.get(ModelConfigRow,'review_llm');config.enabled=False;await db.commit()
    response=await teacher_client.post(path,json={'revision':1,'idempotency_key':'no-review'})
    assert response.status_code==202,response.text
    await run_job(response.json()['job']['id'],settings)
    assert (await teacher_client.get(path+'/'+response.json()['id'])).json()['status']=='preview_ready'


async def test_old_generation_endpoints_are_removed(db,teacher_client,box):
    project,path=await ready_project(db,teacher_client,box)
    response=await teacher_client.get(path+'/00000000-0000-0000-0000-000000000000/preview/00000000-0000-0000-0000-000000000000/html')
    assert response.status_code==404


async def test_checkpoint_repair_keeps_frozen_content_and_sprite_api_without_duplicate_guides(db,teacher_client,box,settings,monkeypatch):
    from app.videos.render_contract import DirectHtmlRuntimeError
    project,path,store,renderer,counts,calls=await prepare(db,teacher_client,box,settings,monkeypatch)
    project.prompt='用细腻像素小人演示孔融把梨递给哥哥，动作简单自然'
    await db.commit()
    renderer.fail=True
    response=await teacher_client.post(path,json={'revision':1,'idempotency_key':'characters-fail'})
    await run_job(response.json()['job']['id'],settings)
    failed=(await teacher_client.get(path+'/'+response.json()['id'])).json()
    assert failed['status']=='failed'
    renderer.fail=False;original=renderer.direct;attempts=[]
    async def repair_once(*args,**kwargs):
        attempts.append(True)
        if len(attempts)==1:raise DirectHtmlRuntimeError('需要修复播放代码')
        return await original(*args,**kwargs)
    renderer.direct=repair_once
    retry=await teacher_client.post(path,json={'revision':1,'idempotency_key':'characters-retry','retry_version_id':failed['id']})
    assert retry.status_code==202,retry.text
    await run_job(retry.json()['job']['id'],settings)
    result=(await teacher_client.get(path+'/'+retry.json()['id'])).json()
    assert result['status']=='preview_ready',result
    assert len(calls)==2 and counts=={'speech':1,'scene':0}
    ids={doc['skill_id'] for doc in calls[0]['animation_design_references']}
    assert {'game-graphics','2d-character-rig-animation'} <= ids
    for request in calls:
        assert request['teacher_request']==project.prompt
        assert request['animation_reference_adapter']
    repaired=calls[1]
    assert 'animation_design_references' not in repaired
    assert 'approved_outline' not in repaired
    assert repaired['previous_html']==HTML
    assert repaired['segments']==calls[0]['segments']
    assert repaired['sprite_library']==calls[0]['sprite_library']
    assert repaired['visual_style']==calls[0]['visual_style']
    import json
    assert len(json.dumps(repaired,ensure_ascii=False)) < len(json.dumps({**calls[0],'previous_html':HTML},ensure_ascii=False))*.8


async def test_story_default_reaches_saved_snapshot_and_html_request_without_pixel_keyword(db,teacher_client,box,settings,monkeypatch):
    project,path,store,renderer,counts,calls=await prepare(db,teacher_client,box,settings,monkeypatch)
    project.title='大禹治水';project.prompt='讲述大禹带领百姓疏通河道的故事'
    project.form_values={**project.form_values,'subject':'语文'};await db.commit()
    response=await teacher_client.post(path,json={'revision':1,'idempotency_key':'default-pixel-story'})
    assert response.status_code==202,response.text
    await run_job(response.json()['job']['id'],settings)
    result=(await teacher_client.get(path+'/'+response.json()['id'])).json()
    assert result['status']=='preview_ready',result
    row=await db.get(VideoVersion,UUID(result['id']),populate_existing=True)
    assert row.snapshot['style']['value']=='pixel_story'
    assert calls[0]['visual_style']['defaults']['character_stories']=='detailed_pixel_art'
    assert calls[0]['visual_style']['defaults']['formulas_graphs_experiments']=='clean_graphics'
    assert any(d['path'].endswith('/pixel-art-reference.md') for d in calls[0]['animation_design_references'])
    assert len(calls)==1 and counts=={'speech':1,'scene':0}
