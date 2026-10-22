import json
import httpx
import pytest
from app.videos.expression import build_expression,validate_expression

def source():
    return {'outline':{'segments':[{'id':'section-1','narration':'一次函数y=kx+b，k不等于0。','visuals':'坐标图像'}]},
            'style':{'value':'science_animation'},'prompt':'讲一次函数','title':'一次函数','form_values':{'subject':'数学'}}


def targets():
    return [{'id':'seg-1','outline_segment_id':'section-1','title':'定义','narration':'一次函数y=kx+b，k不等于0。'}]


def response():
    return {'visual_prompt':'整片使用同一坐标轴、比例和背景，公式y=kx+b且k不等于0。',
            'characters':[],
            'segments':[{'id':'seg-1','narration':'先看一次函数。它写成y=kx+b，其中k不等于0。',
                         'visual_prompt':'沿用同一坐标图像，展示y=kx+b，k不等于0。',
                         'scene_id':'coordinate-plane','character_ids':[],
                         'entry_state':'坐标轴已经出现，尚未绘制直线。',
                         'exit_state':'直线y=kx+b与坐标轴保持可见。',
                         'transition_in':'从同一坐标轴开始','transition_out':'保留坐标轴供下一段继续'}]}


async def test_whole_film_expression_uses_source_and_returns_frozen_shared_script():
    from types import SimpleNamespace
    from app.purposes import Purpose
    requests=[]
    def handle(request):
        body=json.loads(request.content);requests.append(body)
        return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps(response(),ensure_ascii=False)}}]})
    cfg=SimpleNamespace(base_url='https://test.invalid/v1',model='writer',api_key='test',purpose=Purpose.outline_llm)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        result=await build_expression(cfg,source(),targets(),http)
    assert result['segments'][0]['narration'].startswith('先看一次函数。')
    assert result['segments'][0]['outline_segment_id']=='section-1'
    content=json.dumps(requests[0]['messages'],ensure_ascii=False)
    assert 'y=kx+b' in content and '坐标图像' in content


async def test_expression_keeps_story_facts_but_requests_whole_character_motion(monkeypatch):
    from types import SimpleNamespace
    from app.purposes import Purpose
    messages=[]
    async def capture_prompt(config, prompt_messages, **kwargs):
        messages.extend(prompt_messages)
        return response()
    monkeypatch.setattr('app.videos.expression.chat_json',capture_prompt)
    cfg=SimpleNamespace(base_url='https://test.invalid/v1',model='writer',api_key='test',purpose=Purpose.outline_llm)
    await build_expression(cfg,source(),targets(),None)
    system='\n'.join(m['content'] for m in messages if m['role']=='system')
    assert '故事关键行为、人物关系、因果与教学含义必须保留' in system
    assert '只通过整体移动、水平翻转、淡入淡出等简单方式表现动作' in system
    assert '不要求关节、步态或手物接触动画' in system
    assert '数学图像、实验与人物动作允许灵活设计' not in system


@pytest.mark.parametrize('change',['missing','duplicate','wrong_order','empty','formula'])
def test_invalid_expression_cannot_replace_approved_source(change):
    result=response()
    if change=='missing': result['segments']=[]
    if change=='duplicate': result['segments']*=2
    if change=='wrong_order': result['segments'][0]['id']='other'
    if change=='empty': result['segments'][0]['narration']='  '
    if change=='formula':
        result['visual_prompt']='统一背景';result['segments'][0]['narration']='观察直线。';result['segments'][0]['visual_prompt']='直线'
    with pytest.raises(ValueError): validate_expression(result,source(),targets())


@pytest.mark.parametrize('change',['duplicate_character','unknown_character','empty_entry','empty_exit','empty_scene'])
def test_expression_requires_resolved_character_and_scene_handoffs(change):
    result=response()
    character={'id':'korong','appearance':'同一名穿青绿色传统衣袍的男孩，圆脸，黑发。'}
    if change=='duplicate_character':result['characters']=[character,character.copy()]
    else:
        result['characters']=[character]
        result['segments'][0]['character_ids']=['missing' if change=='unknown_character' else 'korong']
    if change=='empty_entry':result['segments'][0]['entry_state']=' '
    if change=='empty_exit':result['segments'][0]['exit_state']=' '
    if change=='empty_scene':result['segments'][0]['scene_id']=' '
    with pytest.raises(ValueError):validate_expression(result,source(),targets())


def test_expression_carries_same_character_and_scene_state_between_segments():
    result=response()
    result['characters']=[{'id':'korong','appearance':'同一名穿青绿色传统衣袍的男孩，圆脸，黑发。'}]
    result['segments'][0]['scene_id']='family-room'
    result['segments'][0]['character_ids']=['korong']
    result['segments'][0]['exit_state']='孔融仍站在桌边，手中托着小梨。'
    second={**result['segments'][0], 'id':'seg-2',
            'narration':'孔融把梨递给哥哥。',
            'visual_prompt':'沿用孔融原有衣着、面容与桌边位置，哥哥仍在桌旁。',
            'entry_state':result['segments'][0]['exit_state'],
            'exit_state':'哥哥接过小梨，孔融仍在原处。',
            'transition_in':'从孔融托梨的姿势自然接续到递梨。',
            'transition_out':'停留在兄弟二人和小梨同框的画面。'}
    result['segments'].append(second)
    targets2=[*targets(),{'id':'seg-2','outline_segment_id':'section-2','title':'分享小梨','narration':'把小梨递给哥哥。'}]
    accepted=validate_expression(result,source(),targets2)
    assert accepted['segments'][1]['character_ids']==['korong']
    assert accepted['segments'][1]['scene_id']==accepted['segments'][0]['scene_id']
    assert accepted['segments'][1]['entry_state']==accepted['segments'][0]['exit_state']




async def test_expression_request_receives_automatic_story_policy_before_html_generation():
    from types import SimpleNamespace
    from app.purposes import Purpose
    from app.videos.quality import resolve_style
    snapshot=source();snapshot.update(title='大禹治水',prompt='讲述大禹治水的故事',form_values={'subject':'语文'})
    snapshot['style']=resolve_style(snapshot['form_values'])
    received=[]
    def handle(request):
        body=json.loads(request.content)
        received.append(json.loads(next(m['content'] for m in body['messages'] if m['role']=='user')))
        return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps(response(),ensure_ascii=False)}}]})
    cfg=SimpleNamespace(base_url='https://test.invalid/v1',model='writer',api_key='test',purpose=Purpose.outline_llm)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        await build_expression(cfg,snapshot,targets(),http)
    assert received[0]['style']['defaults']=={'character_stories':'clear_vector_illustration','formulas_graphs_experiments':'clean_graphics'}


def test_html_request_carries_canonical_characters_and_boundary_states():
    from app.videos.direct_pipeline import html_generation_request
    snapshot=source();snapshot['film_expression']=response()
    snapshot['film_expression']['characters']=[{'id':'kongrong','appearance':'青衣孩童'}]
    entry={**response()['segments'][0],'character_ids':['kongrong']}
    request=html_generation_request(snapshot,[entry],8)
    assert request['continuity_manifest']['characters']==[{'id':'kongrong','appearance':'青衣孩童'}]
    assert request['continuity_manifest']['segments'][0]['entry_state']=='坐标轴已经出现，尚未绘制直线。'
    assert request['continuity_manifest']['segments'][0]['character_ids']==['kongrong']
