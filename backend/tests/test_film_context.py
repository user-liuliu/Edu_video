from copy import deepcopy
import json
import httpx
import pytest
from app.videos.film_modules import _film_exchange,FilmBundle
from test_film_generation_recovery import CONFIG,bundle,response

def sample():
    targets=[{'id':f'id-{i}','outline_segment_id':f'o-{i}','render_key':f'segment-{i}','title':f'课题{i}', 'narration':'完整讲稿'+str(i), 'visual_prompt':'完整画面'+str(i),'scene_id':'board','character_ids':['teacher'],'start':i*20,'end':(i+1)*20,'entry_state':'已存在曲线'+str(i),'exit_state':'已存在曲线'+str(i+1),'transition_in':'承接','transition_out':'保持','sentences':[{'start':i*20,'end':(i+1)*20,'text':'完整讲稿'+str(i)}]} for i in range(3)]
    outline={'segments':[{'id':f'o-{i}','title':f'课题{i}','objective':'知识点'+str(i),'narration':t['narration'],'visuals':[{'description':'y=(x-1)^2+1; 顶点(1,1); a≠0'}],'review_notes':['比较范围：顶点相同'],'content_revision':1,'reviewed_revision':1,'review_passed':True,'estimated_duration_seconds':20} for i,t in enumerate(targets)],'saved_content_hash':'workflow'}
    return {'title':'二次函数','teacher_request':'完整要求','segments':[targets[1]],'approved_outline':outline,'film_build_mode':'append_modules','film':{'shared_code':'return {axis:1};','shared_html':'<svg id=axis/>'},'read_only_boundary_context':[{'id':'segment-0','html':'previous svg','code':'previous code'}], 'previous_segment_context':targets[0],'next_segment_context':[targets[2]],'continuity_manifest':{'characters':[{'id':'teacher','appearance':'保持外观'}]},'connection_contracts':[{'from_id':'segment-0','to_id':'segment-1','mode':'continuous','boundary_state':'已存在曲线1'}]},targets


async def exchange(user):
    calls=[]
    def handle(req):calls.append(json.loads(req.content));return response(bundle())
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        await _film_exchange(CONFIG,http,'policy',user,FilmBundle,lambda value:value)
    return json.loads(calls[0]['messages'][1]['content'])

async def test_real_exchange_preserves_whole_route_and_shared_boundary_and_reduces_bytes():
    user,targets=sample();before=deepcopy(user);value=await exchange(user)
    assert user==before
    for key in ('segments','film','read_only_boundary_context','continuity_manifest','connection_contracts','teacher_request'):assert value[key]==user[key]
    route=value['approved_outline']['segments']
    assert [s['id'] for s in route]==['o-0','o-1','o-2']
    for i,part in enumerate(route):
        for key in ('objective','visuals','review_notes'):assert part[key]==user['approved_outline']['segments'][i][key]
        assert 'review_passed' not in part and 'estimated_duration_seconds' not in part
    assert 'narration' not in route[1] and route[0]['narration']==targets[0]['narration']
    assert value['previous_segment_context']=={k:v for k,v in targets[0].items() if k!='sentences'}
    assert value['next_segment_context']==[{k:v for k,v in targets[2].items() if k!='sentences'}]
    value.pop('response_schema');assert len(json.dumps(value).encode())<len(json.dumps(user).encode())

async def test_seed_keeps_future_narration_and_all_unique_approved_facts():
    user,targets=sample();user['film_build_mode']='shared_first';user['segments']=[targets[0]];user['read_only_film_plan']=targets[1:]
    user['approved_outline']['segments'][0].update(narration='独有审核条件：a≠0',review_issues=['必须保留的条件'],extension={'formula':'F=ma'})
    before=deepcopy(user);value=await exchange(user)
    assert user==before and value['segments']==user['segments']
    item=value['approved_outline']['segments'][0]
    assert item['narration']=='独有审核条件：a≠0' and item['review_issues']==['必须保留的条件'] and item['extension']=={'formula':'F=ma'}
    for old,new in zip(user['read_only_film_plan'],value['read_only_film_plan']):assert new=={k:v for k,v in old.items() if k!='sentences'}

@pytest.mark.parametrize('mode',['whole','revision','repair'])
async def test_other_generation_scopes_are_unchanged(mode):
    user,targets=sample();user.pop('film_build_mode')
    if mode=='revision':user['film_edit_mode']='selected_modules_and_adjacent_transitions'
    if mode=='repair':user['film_repair_source']={'segments':['untouched']}
    before=deepcopy(user);value=await exchange(user);value.pop('response_schema')
    assert value==before and user==before

async def test_adapter_does_not_add_empty_neighbor_fields():
    user,targets=sample();user.pop('previous_segment_context');user.pop('next_segment_context')
    value=await exchange(user)
    assert 'next_segment_context' not in value and 'previous_segment_context' not in value


@pytest.mark.parametrize('resume', [False, True])
async def test_ordered_generation_and_resume_apply_adapter_at_transport_entry(resume):
    from app.videos.film_modules import generate_film, extract_film
    from test_film_generation_recovery import request

    original = request()
    original['source_duration'] = 300
    for index, target in enumerate(original['segments']):
        target['outline_segment_id'] = f'outline-{index}'
        original['approved_outline']['segments'][index].update(
            review_passed=True, content_revision=2, reviewed_revision=2,
            objective=f'不可遗漏的目标{index}')
    before = deepcopy(original)
    value = bundle()
    checkpoint = {**value, 'segments': value['segments'][:1], 'transitions': []} if resume else None
    calls = []

    def handle(req):
        user = json.loads(json.loads(req.content)['messages'][1]['content'])
        calls.append(user)
        target = user['segments'][0]
        index = int(target['render_key'][1:])
        assert user['segments'] == [original['segments'][index]]
        outline = user['approved_outline']['segments']
        assert [part['id'] for part in outline] == [f'outline-{i}' for i in range(3)]
        for i, part in enumerate(outline):
            assert part['objective'] == f'不可遗漏的目标{i}'
            assert part['visuals'] == original['approved_outline']['segments'][i]['visuals']
            assert 'review_passed' not in part and 'content_revision' not in part
        if index == 0:
            assert user['film_build_mode'] == 'shared_first'
            assert all('sentences' not in part for part in user['read_only_film_plan'])
            return response({**value, 'segments': value['segments'][:1], 'transitions': []})
        assert user['film_build_mode'] == 'append_modules'
        assert user['film'] == {key: value[key] for key in ('shared_html', 'shared_code')}
        assert user['read_only_boundary_context'] == [value['segments'][index - 1]]
        assert user['previous_segment_context'] == {
            key: item for key, item in original['segments'][index - 1].items() if key != 'sentences'}
        assert all('sentences' not in part for part in user['next_segment_context'])
        return response({'segments': [value['segments'][index]],
                         'transitions': [value['transitions'][index - 1]]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        html = await generate_film(CONFIG, original, http, checkpoint=checkpoint)
    assert extract_film(html) == value
    assert original == before
    assert len(calls) == (2 if resume else 3)
    if resume:
        assert checkpoint == {**value, 'segments': value['segments'][:1], 'transitions': []}
