from copy import deepcopy
from app.videos.direct_pipeline import html_repair_request


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
