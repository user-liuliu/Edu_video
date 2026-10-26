"""Native figure instructions reach the model without changing the sealed player."""
import json
from pathlib import Path

import httpx
import pytest

from app.videos.direct_pipeline import html_generation_request, html_repair_request
from app.videos.quality import resolve_style


def request_for(prompt, subject='语文', revision=''):
    snapshot = {'title': '教学动画', 'prompt': prompt, 'form_values': {'subject': subject},
                'style': resolve_style({'subject': subject}), 'outline': {},
                'film_expression': {'visual_prompt': '连续演示'}}
    targets = [{'id':'test-scene','render_key':'segment-0','start':0.,'end':10.,'narration': '观察并解释这个过程。', 'teacher_visual_instruction': revision}]
    return html_generation_request(snapshot, targets, 10.)


def test_story_generation_uses_reusable_whole_characters_without_sprite_assets():
    request = request_for('讲述孔融让梨的故事，让人物简单自然地演绎情节')

    assert 'sprite_library' not in request
    guidance = request['animation_reference_adapter']
    assert '完整、可复用的整体角色' in guidance
    assert '整体移动' in guidance
    assert '水平翻转' in guidance
    assert '淡入和淡出' in guidance
    assert '不要拆分四肢' in guidance
    assert 'EduSprites' not in guidance
    assert 'transfer(' not in guidance
    assert '2d-character-rig-animation' not in {
        doc['skill_id'] for doc in request['animation_design_references']
    }
    direct_prompt = (Path(__file__).parents[1] / 'app/videos/direct_prompt.txt').read_text(encoding='utf-8')
    assert '人物作为整体，仅通过整体移动、水平翻转、淡入和淡出' in direct_prompt
    assert '人物遵循通用人体运动规律' not in direct_prompt


@pytest.mark.parametrize('prompt', ['不要像素风，讲述曹冲称象', '用水彩风格讲述人物故事'])
def test_story_generation_uses_simple_reusable_character_guidance(prompt):
    request = request_for(prompt)
    assert 'sprite_library' not in request
    rules = request['animation_reference_adapter']
    for instruction in ('完整、可复用的整体角色', '整体移动', '水平翻转', '淡入和淡出', '道具', '自然转场'):
        assert instruction in rules
    assert request['teacher_request'] == prompt


def test_explicit_non_pixel_revision_uses_native_rules_including_code_repair():
    request = request_for('用像素风讲述人物故事', revision='改为水彩风格，不用像素风')
    assert 'sprite_library' not in request
    from app.videos.film_modules import assemble_film
    bundle={'shared_html':'','shared_code':'return {};','segments':[{'id':'segment-0','html':'<svg></svg>','code':''}],'transitions':[]}
    repaired = html_repair_request(request, assemble_film(bundle,request['segments']))
    assert '人物作为整体' in repaired['animation_reference_adapter']


def test_pixel_story_keeps_pixel_style_but_does_not_inject_character_assets():
    request = request_for('用像素风讲述人物故事')
    assert 'sprite_library' not in request
    assert request['visual_style']['value'] == 'vector_story'
    assert any(d['path'].endswith('/pixel-art-reference.md') for d in request['animation_design_references'])
    assert '人物作为整体' in request['animation_reference_adapter']


def test_science_guidance_does_not_require_figures_or_change_clear_graphics():
    request = request_for('不要人物，只展示二次函数图像与公式', '数学')
    assert 'sprite_library' not in request
    assert '没有人物或动物时不添加角色' in request['animation_reference_adapter']
    assert '公式、函数图像和实验保持清晰' in request['animation_reference_adapter']


def test_prompt_changes_update_provenance_without_invalidating_existing_playback(monkeypatch):
    from app.videos import skill_guidance
    from app.videos.direct_html import direct_digest
    before_prompt = skill_guidance.bundle_metadata()['digest']
    before_runtime = direct_digest()
    monkeypatch.setattr(skill_guidance, 'CHARACTER_MOTION_GUIDANCE', skill_guidance.CHARACTER_MOTION_GUIDANCE + 'test revision')
    assert skill_guidance.bundle_metadata()['digest'] != before_prompt
    assert direct_digest() == before_runtime


@pytest.mark.parametrize(('prompt','pixel'), [('讲述人物合作的故事', False), ('用像素风讲述人物故事', True), ('不用像素风，使用水彩人物讲述故事', False)])
async def test_simple_character_rules_reach_actual_model_payload_without_extra_calls(prompt,pixel):
    from app.videos.direct_html import generate_html
    sent = []
    bundle={'shared_html':'','shared_code':'return {};','segments':[{'id':'segment-0','html':'<svg></svg>','code':''}],'transitions':[]}
    def respond(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={'choices': [{'message': {'content': json.dumps(bundle)}}]})
    config = type('Config', (), {'base_url': 'https://example.invalid/v1', 'api_key': 'test', 'model': 'test'})()
    request = request_for(prompt)
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        from app.videos.film_modules import extract_film
        assert extract_film(await generate_html(config, request, http)) == bundle
    assert len(sent) == 1
    model_input = json.loads(sent[0]['messages'][1]['content'])
    assert '人物作为整体' in model_input['animation_reference_adapter']
    assert 'sprite_library' not in model_input
    assert model_input['visual_style']['defaults']['character_stories']=='clear_vector_illustration'
    assert any(d['path'].endswith('/pixel-art-reference.md') for d in model_input['animation_design_references']) is pixel


@pytest.mark.parametrize('subject',['语文','历史','英语','道德与法治','综合实践','数学'])
def test_default_story_request_keeps_clear_illustration_and_omits_pixel_reference(subject):
    request=request_for('讲述人物合作的故事',subject)
    assert request['visual_style']['defaults']['character_stories']=='clear_vector_illustration'
    assert request['visual_style']['defaults']['formulas_graphs_experiments']=='clean_graphics'
    assert not any(d['path'].endswith('/pixel-art-reference.md') for d in request['animation_design_references'])
    assert 'sprite_library' not in request
