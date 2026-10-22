from copy import deepcopy
from app.videos.direct_pipeline import html_repair_request
from app.videos.film_modules import assemble_film, extract_film


def test_code_repair_keeps_teacher_instruction_and_frozen_timeline_without_reference_duplication():
    segment={'narration':'小石块的总重量等于大象的重量。','start':0,'end':8,
             'sentences':[{'text':'小石块的总重量等于大象的重量。','start':0,'end':8}],
             'teacher_visual_instruction':'石头必须随船移动'}
    request={'source_duration':8,'title':'称象','teacher_request':'不使用像素风格',
             'segments':[segment],'visual_style':{'value':'auto'},
             'whole_film_visual_prompt':'保持船与石头相对位置',
             'animation_reference_adapter':{'runtime':'absolute time'},
             'approved_outline':{'segments':[segment]},
             'animation_design_references':[{'content':'long design reference'}]}
    before=deepcopy(request)
    html='<html><script>window.renderFrame=t=>{};</script></html>'
    repair=html_repair_request(request,html)
    assert repair['teacher_request']=='不使用像素风格'
    assert repair['segments']==[segment]
    assert repair['previous_html']==html
    assert repair['whole_film_visual_prompt']=='保持船与石头相对位置'
    assert 'sprite_library' not in repair
    assert 'approved_outline' not in repair and 'animation_design_references' not in repair
    assert request==before


def test_code_repair_preserves_shared_characters_and_segment_handoffs():
    continuity={'characters':[{'id':'kongrong','appearance':'青衣孩童'}],
                'segments':[{'id':'segment-1','scene_id':'room','entry_state':'桌旁站立','exit_state':'留在桌旁'}]}
    request={'continuity_manifest':continuity,'segments':[],'source_duration':8}
    repaired=html_repair_request(request,'<html>prior</html>')
    assert repaired['continuity_manifest']==continuity


def test_first_generation_repair_keeps_full_bundle_scope_and_prior_shared_code():
    targets=[{'render_key':'segment-0','start':0.,'end':8.,'narration':'分梨。'}]
    bundle={'shared_html':'<svg><text>家中</text></svg>','shared_code':'return {table: makeTable()};',
            'segments':[{'id':'segment-0','html':'<svg/>','code':'draw(root);'}],'transitions':[]}
    prior=assemble_film(bundle,targets)
    request={'film_module_protocol':'film-modules-1','source_duration':8.,'segments':targets,
             'whole_film_visual_prompt':'保持桌椅和人物一致'}

    repaired=html_repair_request(request,prior)

    assert 'film_revision_source' not in repaired
    assert 'editable_segment_ids' not in repaired
    assert repaired['previous_film_bundle']==extract_film(prior)
    assert repaired['segments']==targets
    assert '仅修复运行错误' in repaired['instruction']
