from copy import deepcopy
from uuid import UUID,uuid4
import io
import re
import wave

import pytest
from sqlalchemy import select

from app.jobs.tasks import run_job
from app.models import VideoVersion,VideoSegment,OutlineJob,CreditReservation
from app.outline.review import mark_saved
from app.videos.speech import Narration
from test_direct_pipeline import prepare


async def setup(db,client,box,settings,monkeypatch,*,texts=('第一段。','第二段。'),merged_captions=False):
    project,path,store,renderer,counts,visual_calls=await prepare(db,client,box,settings,monkeypatch)
    first=deepcopy(project.outline['segments'][0])
    project.outline=mark_saved({'segments':[{**deepcopy(first),'id':str(uuid4()),'position':i,'narration':text} for i,text in enumerate(texts)]})
    await db.commit()
    requested=[];generated=[]
    async def speech(config,text,http,*,speaker=None,instruction=''):
        counts['speech']+=1;requested.append((text,instruction))
        sentences=re.findall(r'[^。]+。|[^。]+$',text)
        stream=io.BytesIO()
        with wave.open(stream,'wb') as w:
            w.setparams((1,2,48000,0,'NONE','not compressed'))
            w.writeframes(b''.join((i+100).to_bytes(2,'little',signed=True)*48000 for i in range(len(sentences))))
        captions=[{'start':i+.2,'end':i+.8,'text':sentence} for i,sentence in enumerate(sentences)]
        if merged_captions and len(sentences)>1:captions=[{'start':.2,'end':len(sentences)-.2,'text':text}]
        result=Narration(stream.getvalue(),captions);generated.append(result);return result
    monkeypatch.setattr('app.videos.pipeline.synthesize_narration',speech)
    return project,path,store,renderer,counts,visual_calls,requested,generated


async def generate(db,client,path,settings,key='continuous'):
    response=await client.post(path,json={'revision':1,'idempotency_key':key})
    assert response.status_code==202,response.text
    value=response.json();await run_job(value['job']['id'],settings)
    return value,await db.get(VideoVersion,UUID(value['id']),populate_existing=True)


async def test_real_pipeline_synthesizes_adjacent_paragraphs_once_and_keeps_exact_pcm(db,teacher_client,box,settings,monkeypatch):
    project,path,store,renderer,counts,calls,requested,generated=await setup(db,teacher_client,box,settings,monkeypatch)
    value,row=await generate(db,teacher_client,path,settings)
    assert row.status=='preview_ready'
    assert [r[0] for r in requested]==['第一段。第二段。']
    assert '连续' in requested[0][1]
    parts=(await db.scalars(select(VideoSegment).where(VideoSegment.version_id==row.id).order_by(VideoSegment.position))).all()
    assert [(s.start,s.end) for s in parts]==[(0.,1.),(1.,2.)]
    assert store.files[row.snapshot['direct_manifest']['keys']['audio']]==generated[0].audio
    assert (await teacher_client.get('/api/account/credits/transactions?type=expense')).json()['total']==1
    assert row.snapshot['narration_blocks']


async def test_missing_subtitle_boundaries_fall_back_to_single_paragraphs_once(db,teacher_client,box,settings,monkeypatch):
    project,path,store,renderer,counts,calls,requested,generated=await setup(db,teacher_client,box,settings,monkeypatch,merged_captions=True)
    value,row=await generate(db,teacher_client,path,settings)
    assert row.status=='preview_ready'
    assert [r[0] for r in requested]==['第一段。第二段。','第一段。','第二段。']
    assert any(block.get('single_required') for block in row.snapshot['narration_blocks'].values())
    assert (await teacher_client.get('/api/account/credits/transactions?type=expense')).json()['total']==1


@pytest.mark.parametrize('selected',[(1,),(1,2)])
async def test_visual_and_selected_voice_edits_do_not_regenerate_unselected_audio(db,teacher_client,box,settings,monkeypatch,selected):
    texts=('第一段。','第二段。','第三段。')
    project,path,store,renderer,counts,calls,requested,generated=await setup(db,teacher_client,box,settings,monkeypatch,texts=texts)
    value,row=await generate(db,teacher_client,path,settings)
    assert len(requested)==1
    original=(await teacher_client.get(path+'/'+value['id'])).json()
    prior=(await db.scalars(select(VideoSegment).where(VideoSegment.version_id==row.id).order_by(VideoSegment.position))).all()
    for mode in ('visual','voice'):
        response=await teacher_client.post(path+'/'+value['id']+'/revisions',json={
            'revision':1,'idempotency_key':mode,'segment_ids':[original['segments'][i]['id'] for i in selected],
            'instruction':'放慢语速' if mode=='voice' else '放大图形','mode':mode})
        assert response.status_code==202,response.text
        item=response.json();await run_job(item['job']['id'],settings)
        current=await db.get(VideoVersion,UUID(item['id']),populate_existing=True)
        assert current.status=='preview_ready'
        revised=(await db.scalars(select(VideoSegment).where(VideoSegment.version_id==current.id).order_by(VideoSegment.position))).all()
        assert len(requested)==(1 if mode=='visual' else 2)
        for i in set(range(3))-(set(selected) if mode=='voice' else set()):
            assert revised[i].assets['audio']==prior[i].assets['audio']
    assert requested[-1][0]==''.join(texts[i] for i in selected)


async def test_slow_group_checkpoints_all_audio_before_yield_and_does_not_pay_twice(db,teacher_client,box,settings,monkeypatch):
    import app.videos.pipeline as shared
    import app.videos.direct_pipeline as pipeline
    project,path,store,renderer,counts,calls,requested,generated=await setup(db,teacher_client,box,settings,monkeypatch)
    clock=[0.];monkeypatch.setattr(pipeline,'batch_clock',lambda:clock[0])
    original=shared.synthesize_narration
    async def slow(*args,**kwargs):
        result=await original(*args,**kwargs);clock[0]+=310;return result
    monkeypatch.setattr(shared,'synthesize_narration',slow)
    value,row=await generate(db,teacher_client,path,settings)
    job=await db.get(OutlineJob,UUID(value['job']['id']),populate_existing=True)
    assert job.status=='pending' and len(requested)==1
    parts=(await db.scalars(select(VideoSegment).where(VideoSegment.version_id==row.id))).all()
    assert all(s.assets.get('audio') and s.assets.get('captions') for s in parts)
    assert (await db.get(CreditReservation,job.id,populate_existing=True)).state=='reserved'
    await db.commit();await run_job(job.id,settings)
    result=(await teacher_client.get(path+'/'+value['id'])).json()
    assert result['status']=='preview_ready' and len(requested)==1 and len(calls)==1
    assert (await teacher_client.get('/api/account/credits/transactions?type=expense')).json()['total']==1


async def test_retry_after_interrupted_distribution_recovers_the_group_without_new_synthesis(db,teacher_client,box,settings,monkeypatch):
    project,path,store,renderer,counts,calls,requested,generated=await setup(db,teacher_client,box,settings,monkeypatch)
    put=store.put;caption_writes=[0]
    def interrupt(key,data,content_type=''):
        if '/captions-' in key:
            caption_writes[0]+=1
            if caption_writes[0]==2:raise OSError('interrupted segment persistence')
        return put(key,data,content_type)
    monkeypatch.setattr(store,'put',interrupt)
    value,row=await generate(db,teacher_client,path,settings)
    assert row.status=='failed' and len(requested)==1
    assert row.snapshot['narration_blocks']
    retry=await teacher_client.post(path,json={'revision':1,'idempotency_key':'recover-group','retry_version_id':value['id']})
    assert retry.status_code==202,retry.text
    saved=retry.json();await run_job(saved['job']['id'],settings)
    result=(await teacher_client.get(path+'/'+saved['id'])).json()
    assert result['status']=='preview_ready' and len(requested)==1 and len(calls)==1
    assert (await teacher_client.get('/api/account/credits/transactions?type=expense')).json()['total']==1


async def test_provider_failure_does_not_trigger_separate_paragraph_requests(db,teacher_client,box,settings,monkeypatch):
    from app.outline.model_client import ModelCallError
    project,path,store,renderer,counts,calls,requested,generated=await setup(db,teacher_client,box,settings,monkeypatch)
    seen=[]
    async def unavailable(config,text,*args,**kwargs):
        seen.append(text);raise ModelCallError('配音服务暂时不可用',category='unavailable')
    monkeypatch.setattr('app.videos.pipeline.synthesize_narration',unavailable)
    value,row=await generate(db,teacher_client,path,settings)
    assert row.status=='failed'
    assert seen==['第一段。第二段。']
    assert (await db.get(CreditReservation,UUID(value['job']['id']),populate_existing=True)).state=='released'


async def test_interruption_after_group_assets_commit_keeps_an_atomic_recovery_record(db,teacher_client,box,settings,monkeypatch):
    from sqlalchemy.ext.asyncio import AsyncSession
    project,path,store,renderer,counts,calls,requested,generated=await setup(db,teacher_client,box,settings,monkeypatch)
    commit=AsyncSession.commit;interrupted=[False]
    async def interrupt_after_commit(session):
        await commit(session)
        if interrupted[0]:return
        for item in session.identity_map.values():
            if isinstance(item,VideoVersion) and any(name.startswith('narration_captions_') for name in item.snapshot.get('direct_assets',{})):
                interrupted[0]=True
                raise OSError('worker stopped after group assets were committed')
    monkeypatch.setattr(AsyncSession,'commit',interrupt_after_commit)
    value,row=await generate(db,teacher_client,path,settings)
    assert interrupted[0] and row.status=='failed' and len(requested)==1
    retry=await teacher_client.post(path,json={'revision':1,'idempotency_key':'atomic-group-recovery','retry_version_id':value['id']})
    assert retry.status_code==202,retry.text
    result=retry.json();await run_job(result['job']['id'],settings)
    assert (await teacher_client.get(path+'/'+result['id'])).json()['status']=='preview_ready'
    assert len(requested)==1


async def test_unsplittable_group_does_not_retry_a_shorter_suffix_after_continuation(db,teacher_client,box,settings,monkeypatch):
    import app.videos.pipeline as shared
    import app.videos.direct_pipeline as pipeline
    project,path,store,renderer,counts,calls,requested,generated=await setup(db,teacher_client,box,settings,monkeypatch,texts=('第一段。','第二段。','第三段。'),merged_captions=True)
    clock=[0.];monkeypatch.setattr(pipeline,'batch_clock',lambda:clock[0])
    speech=shared.synthesize_narration
    async def slow_first_individual(config,text,*args,**kwargs):
        result=await speech(config,text,*args,**kwargs)
        if text=='第一段。':clock[0]+=310
        return result
    monkeypatch.setattr(shared,'synthesize_narration',slow_first_individual)
    value,row=await generate(db,teacher_client,path,settings)
    job=await db.get(OutlineJob,UUID(value['job']['id']),populate_existing=True)
    assert job.status=='pending'
    await db.commit();await run_job(job.id,settings)
    assert (await teacher_client.get(path+'/'+value['id'])).json()['status']=='preview_ready'
    assert [r[0] for r in requested]==['第一段。第二段。第三段。','第一段。','第二段。','第三段。']


async def test_pipeline_keeps_same_chapter_continuity_instead_of_filling_previous_chapter(db,teacher_client,box,settings,monkeypatch):
    texts=('先复习。'*30,'抛物线平移。'*18,'再看交点。'*18)
    project,path,store,renderer,counts,calls,requested,generated=await setup(db,teacher_client,box,settings,monkeypatch,texts=texts)
    outline=deepcopy(project.outline)
    for s,title in zip(outline['segments'],['一次函数：复习','二次函数：平移','二次函数：交点']):s['title']=title
    project.outline=mark_saved(outline);await db.commit()
    value,row=await generate(db,teacher_client,path,settings)
    assert row.status=='preview_ready'
    assert [r[0] for r in requested]==[texts[0],texts[1]+texts[2]]
