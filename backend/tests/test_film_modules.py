from copy import deepcopy
import json
import pytest
from app.videos.film_modules import assemble_film, extract_film, patch_film, revision_request
from app.videos.direct_html import validate_html


def film():
    return {'shared_html':'<style>svg{width:1280px;height:720px}</style>',
            'shared_code':'return {color: "#286e62"};',
            'segments':[{'id':f's{i}','html':f'<svg><text data-title="t">场景{i}</text></svg>',
                         'code':"root.querySelector('text').setAttribute('x',String(t*10));"} for i in range(3)],
            'transitions':[{'from_id':f's{i}','to_id':f's{i+1}','duration':0.6,
                            'code':'outgoing.style.opacity=String(1-progress);incoming.style.opacity=String(progress);'} for i in range(2)]}


def timeline():
    return [{'id':f's{i}','render_key':f's{i}','start':i*8.,'end':(i+1)*8.,'narration':f'讲解{i}。'} for i in range(3)]


def test_compiled_film_retains_editable_modules_and_uses_existing_html_runtime():
    bundle=film();raw=assemble_film(bundle,timeline())
    assert validate_html(raw)==raw
    assert extract_film(raw)==bundle
    assert 'attachShadow' in raw


def test_local_patch_replaces_only_selected_scene_and_adjacent_transitions():
    source=film();before=deepcopy(source)
    change={'segments':[{**source['segments'][1],'html':'<svg><text>修改的中段</text></svg>'}],
            'transitions':[{**t,'code':'incoming.style.opacity=String(progress*progress);'} for t in source['transitions']]}
    revised=patch_film(source,change,['s1'],timeline())
    assert source==before
    assert revised['shared_html']==source['shared_html'] and revised['shared_code']==source['shared_code']
    assert revised['segments'][0]==source['segments'][0] and revised['segments'][2]==source['segments'][2]
    assert revised['segments'][1]['html']=='<svg><text>修改的中段</text></svg>'


@pytest.mark.parametrize('invalid',['unselected','missing','shared','transition','duplicate'])
def test_local_patch_rejects_changes_outside_selected_scope(invalid):
    source=film();change={'segments':[source['segments'][1]],'transitions':source['transitions']}
    if invalid=='unselected':change['segments']=[source['segments'][0]]
    if invalid=='missing':change['transitions']=[]
    if invalid=='shared':change['shared_code']='return {}; '
    if invalid=='transition':change['transitions']=[{'from_id':'s0','to_id':'s2','duration':0.6,'code':''}]
    if invalid=='duplicate':change['segments']*=2
    with pytest.raises(ValueError):patch_film(source,change,['s1'],timeline())


def test_revision_request_excludes_untouched_scene_code_but_keeps_boundary_context():
    source=film();targets=timeline()
    request=revision_request({'segments':targets,'continuity_manifest':{'characters':[]}},source,['s1'])
    assert request['editable_segment_ids']==['s1']
    assert [s['id'] for s in request['film']['segments']]==['s1']
    assert request['film']['shared_html']==source['shared_html']
    assert [s['id'] for s in request['segments']]==['s0','s1','s2']


@pytest.mark.asyncio
async def test_first_generation_runtime_repair_can_return_and_validate_full_bundle(monkeypatch):
    from types import SimpleNamespace
    import httpx
    from app.videos.direct_pipeline import html_repair_request
    from app.videos.film_modules import generate_film

    targets=[{'render_key':'segment-0','start':0.,'end':8.,'narration':'分梨。'}]
    original={'shared_html':'<svg><text>原场景</text></svg>','shared_code':'return {table: makeTable()};',
              'segments':[{'id':'segment-0','html':'<svg/>','code':'draw(root);'}],'transitions':[]}
    request=html_repair_request({'film_module_protocol':'film-modules-1','source_duration':8.,
        'segments':targets,'whole_film_visual_prompt':'保留画面'},assemble_film(original,targets))
    repaired={**original,'shared_code':'return {table: makeTable(), repaired: true};'}
    calls=[]

    async def respond(http,url,headers,payload):
        calls.append(payload)
        return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps(repaired)}}]})

    monkeypatch.setattr('app.videos.model_stream.animation_response',respond)
    html=await generate_film(SimpleNamespace(base_url='https://models.invalid',api_key='test',model='test'),request,None)

    user=json.loads(calls[0]['messages'][1]['content'])
    assert user['response_schema']['title']=='FilmBundle'
    assert user['film_repair_source']==original
    assert 'editable_segment_ids' not in user
    assert extract_film(html)['shared_code']==repaired['shared_code']


def test_continuous_transition_round_trip_and_selected_patch_preserve_other_modules():
    bundle=film();targets=timeline()
    for transition in bundle['transitions']:
        transition.update(mode='continuous',code=';')
    raw=assemble_film(bundle,targets)
    assert extract_film(raw)==bundle
    delta={'segments':[bundle['segments'][1]],'transitions':bundle['transitions']}
    revised=patch_film(bundle,delta,['s1'],targets)
    assert revised==bundle


@pytest.mark.asyncio
async def test_generation_rejects_dissolve_between_segments_of_same_scene(monkeypatch):
    from types import SimpleNamespace
    import httpx
    from app.videos.film_modules import generate_film
    targets=[{**t,'scene_id':'same-board'} for t in timeline()]
    invalid=film()
    for transition in invalid['transitions']:transition['mode']='dissolve'
    valid=deepcopy(invalid)
    for transition in valid['transitions']:transition['mode']='continuous'
    responses=iter([invalid,valid]);calls=[]
    async def respond(http,url,headers,payload):
        calls.append(payload)
        return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps(next(responses))}}]})
    monkeypatch.setattr('app.videos.model_stream.animation_response',respond)
    raw=await generate_film(SimpleNamespace(base_url='https://models.invalid',api_key='test',model='test'),{'segments':targets},None)
    assert len(calls)==2
    assert all(t['mode']=='continuous' for t in extract_film(raw)['transitions'])


def test_generation_request_carries_authoritative_boundary_state_and_scene_modes():
    from app.videos.direct_pipeline import html_generation_request
    targets=timeline()
    for index,target in enumerate(targets):
        target.update(scene_id='board' if index<2 else 'outdoors',entry_state='begin',exit_state=f'end-state-{index}')
    snapshot={'title':'测试','prompt':'讲解概念','form_values':{'subject':'数学'},'outline':{},
              'film_expression':{'visual_prompt':'同一教学画布','characters':[]},'style':{}}
    result=html_generation_request(snapshot,targets,24.)
    assert result['connection_contracts']==[
        {'from_id':'s0','to_id':'s1','mode':'continuous','boundary_state':'end-state-0'},
        {'from_id':'s1','to_id':'s2','mode':'scene_change','boundary_state':'end-state-1'},
    ]
    from app.videos.direct_pipeline import html_repair_request
    repair=html_repair_request(result,assemble_film(film(),targets))
    assert repair['connection_contracts']==result['connection_contracts']
    edit=revision_request(result,film(),['s1'])
    assert edit['connection_contracts']==result['connection_contracts']


def test_generation_policy_changes_do_not_invalidate_saved_film_runtime(monkeypatch):
    from pathlib import Path
    from app.videos.direct_html import direct_digest
    baseline=direct_digest();read=Path.read_bytes
    def changed(path):
        value=read(path)
        if path.name in ('film_modules_prompt.txt','film_modules.py','direct_prompt.txt'):value+=b'\n'
        return value
    monkeypatch.setattr(Path,'read_bytes',changed)
    assert direct_digest()==baseline


def test_compiler_changes_invalidate_runtime_for_export_safety(monkeypatch):
    from pathlib import Path
    from app.videos.direct_html import direct_digest
    baseline=direct_digest();read=Path.read_bytes
    def changed(path):
        value=read(path)
        if path.name=='film_module_compiler.py':value+=b'\n'
        return value
    monkeypatch.setattr(Path,'read_bytes',changed)
    assert direct_digest()!=baseline
