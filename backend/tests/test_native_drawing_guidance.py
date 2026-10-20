"""Native figure instructions reach the model without changing the sealed player."""
import json

import httpx
import pytest

from app.videos.direct_pipeline import html_generation_request, html_repair_request
from app.videos.quality import resolve_style


def request_for(prompt, subject='语文', revision=''):
    snapshot = {'title': '教学动画', 'prompt': prompt, 'form_values': {'subject': subject},
                'style': resolve_style({'subject': subject}), 'outline': {},
                'film_expression': {'visual_prompt': '连续演示'}}
    targets = [{'narration': '观察并解释这个过程。', 'teacher_visual_instruction': revision}]
    return html_generation_request(snapshot, targets, 10.)


@pytest.mark.parametrize('prompt', ['不要像素风，讲述曹冲称象', '用水彩风格讲述人物故事'])
def test_non_pixel_generation_carries_human_and_animal_drawing_rules(prompt):
    request = request_for(prompt)
    assert 'sprite_library' not in request
    rules = request['animation_reference_adapter']
    for instruction in ('非像素风绘制规范', '自然站姿', '肘部', '衣袖', '动物', '支撑', '肢段长度', '不限制动作种类'):
        assert instruction in rules
    assert request['teacher_request'] == prompt


def test_explicit_non_pixel_revision_uses_native_rules_including_code_repair():
    request = request_for('用像素风讲述人物故事', revision='改为水彩风格，不用像素风')
    assert 'sprite_library' not in request
    repaired = html_repair_request(request, '<html><script>window.renderFrame=t=>{};</script></html>')
    assert '非像素风绘制规范' in repaired['animation_reference_adapter']


def test_pixel_story_still_uses_cast_without_native_figure_instructions():
    request = request_for('用像素风讲述人物故事')
    assert request['sprite_library']['character_policy']['required'] is True
    assert '非像素风绘制规范' not in request['animation_reference_adapter']


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
    monkeypatch.setattr(skill_guidance, 'NATIVE_DRAWING_GUIDANCE', skill_guidance.NATIVE_DRAWING_GUIDANCE + 'test revision')
    assert skill_guidance.bundle_metadata()['digest'] != before_prompt
    assert direct_digest() == before_runtime


async def test_non_pixel_rules_reach_actual_model_payload_without_extra_calls():
    from app.videos.direct_html import generate_html
    sent = []
    html = '<!doctype html><html><body><script>window.renderFrame=t=>{};</script></body></html>'
    def respond(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={'choices': [{'message': {'content': json.dumps({'html': html})}}]})
    config = type('Config', (), {'base_url': 'https://example.invalid/v1', 'api_key': 'test', 'model': 'test'})()
    request = request_for('不用像素风，使用水彩人物讲述故事')
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        assert await generate_html(config, request, http) == html
    assert len(sent) == 1
    model_input = json.loads(sent[0]['messages'][1]['content'])
    assert '非像素风绘制规范' in model_input['animation_reference_adapter']
