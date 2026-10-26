from copy import deepcopy
import json

import httpx
import pytest

from app.outline.model_client import ModelCallError
from app.videos import film_modules as modules
from test_film_generation_recovery import CONFIG, bundle, request, response


async def test_completed_prefix_survives_interruption_and_resume_requests_only_missing_module(monkeypatch):
    saved=[];calls=[];value=bundle();original=request()
    original['source_duration']=300
    async def save(part):
        saved.append(deepcopy(part))
    async def send(http,url,headers,payload,**kwargs):
        user=json.loads(payload['messages'][1]['content']);calls.append(user)
        if len(calls)==1:return response({**value,'segments':value['segments'][:1],'transitions':[]})
        if len(calls)==2:return response({'segments':[value['segments'][1]],'transitions':[value['transitions'][0]]})
        raise ModelCallError('服务暂时异常',category='unavailable',status_code=502)
    monkeypatch.setattr('app.videos.model_stream.animation_response',send)
    with pytest.raises(ModelCallError):
        await modules.generate_film(CONFIG,original,None,save_checkpoint=save)
    assert [len(part['segments']) for part in saved]==[1,2]
    prior=deepcopy(saved[-1]);calls.clear()
    async def finish(http,url,headers,payload,**kwargs):
        user=json.loads(payload['messages'][1]['content']);calls.append(user)
        assert [s['render_key'] for s in user['segments']]==['s2']
        assert user['film']['shared_code']==value['shared_code']
        assert user['read_only_boundary_context']==[value['segments'][1]]
        assert user['previous_segment_context']=={k:v for k,v in original['segments'][1].items() if k!='sentences'}
        return response({'segments':[value['segments'][2]],'transitions':[value['transitions'][1]]})
    monkeypatch.setattr('app.videos.model_stream.animation_response',finish)
    raw=await modules.generate_film(CONFIG,original,None,checkpoint=prior,save_checkpoint=save)
    assert modules.extract_film(raw)==value and len(calls)==1
    assert prior==saved[-2]


async def test_bounded_batches_save_before_yield_and_never_request_completed_modules(monkeypatch):
    saved=[];calls=[];value=bundle();original=request();original['source_duration']=300
    async def save(part):saved.append(deepcopy(part))
    async def send(http,url,headers,payload,**kwargs):
        user=json.loads(payload['messages'][1]['content']);calls.append(user)
        if len(calls)==1:return response({**value,'segments':value['segments'][:1],'transitions':[]})
        return response({'segments':[value['segments'][1]],'transitions':[value['transitions'][0]]})
    monkeypatch.setattr('app.videos.model_stream.animation_response',send)
    with pytest.raises(Exception) as error:
        await modules.generate_film(CONFIG,original,None,save_checkpoint=save,max_modules=2)
    assert type(error.value).__name__=='FilmBatchPending'
    assert error.value.completed==2 and error.value.total==3
    assert len(calls)==2 and len(saved[-1]['segments'])==2


async def test_checkpoint_write_failure_stops_generation_before_next_module(monkeypatch):
    calls=[];original=request();original['source_duration']=300;value=bundle()
    async def save(part):raise OSError('storage write failed')
    async def send(http,url,headers,payload,**kwargs):
        calls.append(payload);return response({**value,'segments':value['segments'][:1],'transitions':[]})
    monkeypatch.setattr('app.videos.model_stream.animation_response',send)
    with pytest.raises(OSError):await modules.generate_film(CONFIG,original,None,save_checkpoint=save)
    assert len(calls)==1


async def test_full_checkpoint_needs_no_provider_call(monkeypatch):
    async def forbidden(*args,**kwargs):raise AssertionError('no model request needed')
    monkeypatch.setattr('app.videos.model_stream.animation_response',forbidden)
    raw=await modules.generate_film(CONFIG,request(),None,checkpoint=bundle())
    assert modules.extract_film(raw)==bundle()


def test_generation_fingerprint_ignores_retry_uuids_but_invalidates_content_models_and_runtime():
    from app.videos.film_checkpoints import generation_fingerprint
    frozen=request();other=deepcopy(frozen)
    for i,target in enumerate(other['segments']):target['id']='new-uuid-'+str(i)
    for i,target in enumerate(other['continuity_manifest']['segments']):target['id']='new-uuid-'+str(i)
    fingerprint=generation_fingerprint(frozen,'writer-a','runtime-a')
    assert generation_fingerprint(other,'writer-a','runtime-a')==fingerprint
    other['segments'][1]['narration']='changed approved text'
    assert generation_fingerprint(other,'writer-a','runtime-a')!=fingerprint
    assert generation_fingerprint(frozen,'writer-b','runtime-a')!=fingerprint
    assert generation_fingerprint(frozen,'writer-a','runtime-b')!=fingerprint


async def checkpoint_store(index=None):
    import hashlib
    from app.videos.film_checkpoints import FilmCheckpoints
    from direct_fakes import Store
    storage=Store();indices=[]
    async def publish(name,data,kind):
        digest=hashlib.sha256(data).hexdigest();key='videos/owned/'+name+'-'+digest
        storage.put(key,data,kind);return key,digest
    async def persist(index):indices.append(deepcopy(index))
    manager=FilmCheckpoints(storage,request(),'frozen-fingerprint',index,publish,persist)
    return manager,storage,indices,publish,persist


async def test_corrupt_middle_part_restores_only_verified_prefix_and_invalidates_suffix():
    from app.videos.film_checkpoints import FilmCheckpoints
    manager,storage,indices,publish,persist=await checkpoint_store()
    await manager.save(bundle())
    index=deepcopy(indices[-1]);storage.files[index['parts'][1]['key']]+=b'bad'
    restored=FilmCheckpoints(storage,request(),'frozen-fingerprint',index,publish,persist)
    prefix=await restored.restore()
    assert prefix['segments']==bundle()['segments'][:1] and prefix['transitions']==[]
    assert len(indices[-1]['parts'])==1
    assert len(index['parts'])==3


async def test_upload_failure_does_not_advance_checkpoint_index_and_prefix_stays_readable():
    from app.videos.film_checkpoints import FilmCheckpoints
    manager,storage,indices,publish,persist=await checkpoint_store()
    first={**bundle(),'segments':bundle()['segments'][:1],'transitions':[]}
    await manager.save(first);before=deepcopy(indices[-1]);writes=[]
    async def broken(name,data,kind):
        writes.append(name);raise OSError('upload interrupted')
    failed=FilmCheckpoints(storage,request(),'frozen-fingerprint',before,broken,persist)
    assert await failed.restore()==first
    with pytest.raises(OSError):await failed.save(bundle())
    assert indices[-1]==before and writes


async def test_changed_generation_fingerprint_discards_saved_prefix_without_reading_objects():
    from app.videos.film_checkpoints import FilmCheckpoints
    manager,storage,indices,publish,persist=await checkpoint_store();await manager.save(bundle())
    storage.files.clear()
    changed=FilmCheckpoints(storage,request(),'different-fingerprint',indices[-1],publish,persist)
    assert await changed.restore() is None


async def test_guard_failure_does_not_publish_complete_index():
    from app.videos.film_checkpoints import FilmCheckpoints
    manager,storage,indices,publish,persist=await checkpoint_store()
    async def reject(index):raise ValueError('stale lease')
    fenced=FilmCheckpoints(storage,request(),'frozen-fingerprint',None,publish,reject)
    with pytest.raises(ValueError,match='stale'):await fenced.save(bundle())
    assert indices==[]


async def test_restored_shared_resources_cannot_be_changed_by_append():
    manager,storage,indices,publish,persist=await checkpoint_store()
    first={**bundle(),'segments':bundle()['segments'][:1],'transitions':[]}
    await manager.save(first);prior=deepcopy(indices[-1]);changed=bundle();changed['shared_code']='return {wrong:true};'
    with pytest.raises(ValueError):await manager.save(changed)
    assert indices[-1]==prior


async def test_full_response_storage_failure_preserves_already_uploaded_part_prefix():
    from app.videos.film_checkpoints import FilmCheckpoints
    manager,storage,indices,publish,persist=await checkpoint_store()
    async def fail_last(name,data,kind):
        if name=='checkpoint_part_2':raise OSError('last upload failed')
        return await publish(name,data,kind)
    interrupted=FilmCheckpoints(storage,request(),'frozen-fingerprint',None,fail_last,persist)
    with pytest.raises(OSError):await interrupted.save(bundle())
    assert len(indices[-1]['parts'])==2
    recovered=FilmCheckpoints(storage,request(),'frozen-fingerprint',indices[-1],publish,persist)
    prefix=await recovered.restore()
    assert prefix['segments']==bundle()['segments'][:2]
