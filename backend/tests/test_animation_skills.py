import json
import shutil
import pytest

@pytest.mark.parametrize(('style','segment','included','excluded'), [
    ({'value':'science_animation'}, {'narration':'观察一次函数图像'}, 'diagram-animation', 'javascript-animation'),
    ({'value':'story_sketch'}, {'narration':'孔融拿起小梨递给哥哥'}, 'javascript-animation', 'diagram-animation'),
    ({'value':'自定义水墨','source':'selection'}, {'narration':'保持教师指定画风'}, None, 'diagram-animation'),
])
def test_guidance_selects_subject_references_without_overriding_explicit_style(style,segment,included,excluded):
    from app.videos.skill_guidance import animation_guidance
    result=animation_guidance(segment,style)
    assert {'animation-principles','svg-animation'} <= set(result['skill_ids'])
    if included: assert included in result['skill_ids']
    assert excluded not in result['skill_ids']
    assert result['style']==style
    assert len(result['documents'])>=2
    assert all(doc['content'].strip() and doc['commit'] and doc['path'] for doc in result['documents'])
    assert len(json.dumps(result,ensure_ascii=False))<24000


def test_source_integrity_rejects_modified_and_escaping_paths(tmp_path):
    from app.videos.skill_guidance import SKILLS_ROOT, animation_guidance
    root=tmp_path/'skills';shutil.copytree(SKILLS_ROOT,root)
    target=root/'upstream'/'svg-animation'/'SKILL.md'
    target.write_text(target.read_text(encoding='utf-8')+' modified',encoding='utf-8')
    with pytest.raises(ValueError,match='完整性'):animation_guidance({}, {},root=root)
    shutil.rmtree(root);shutil.copytree(SKILLS_ROOT,root)
    manifest=json.loads((root/'sources.json').read_text(encoding='utf-8'))
    manifest['skills']['svg-animation']['files']['../outside.md']='0'*64
    (root/'sources.json').write_text(json.dumps(manifest),encoding='utf-8')
    with pytest.raises(ValueError,match='路径'):animation_guidance({}, {},root=root)


def test_missing_license_fails_before_model_request(tmp_path):
    from app.videos.skill_guidance import SKILLS_ROOT, animation_guidance
    root=tmp_path/'skills';shutil.copytree(SKILLS_ROOT,root)
    (root/'upstream'/'animation-principles'/'LICENSE').unlink()
    with pytest.raises(ValueError,match='完整性'):animation_guidance({}, {},root=root)


def test_bundle_provenance_changes_visual_cache(tmp_path):
    import hashlib
    from app.videos.skill_guidance import SKILLS_ROOT, bundle_metadata
    from app.videos.cache import cache_fingerprint
    root=tmp_path/'skills';shutil.copytree(SKILLS_ROOT,root)
    original=bundle_metadata(root=root)
    path=root/'upstream'/'svg-animation'/'SKILL.md'
    path.write_bytes(path.read_bytes()+b' updated source')
    registry=root/'sources.json';manifest=json.loads(registry.read_text(encoding='utf-8'))
    manifest['skills']['svg-animation']['files']['SKILL.md']=hashlib.sha256(path.read_bytes()).hexdigest()
    registry.write_text(json.dumps(manifest),encoding='utf-8')
    changed=bundle_metadata(root=root)
    assert original['digest']!=changed['digest']
    assert cache_fingerprint({'scene':'same','skills':original['digest']})!=cache_fingerprint({'scene':'same','skills':changed['digest']})


@pytest.mark.parametrize(('subject','style','selected'),[('数学','水墨风','diagram-animation'),('语文','剪纸风','javascript-animation')])
def test_subject_routing_retains_custom_style(subject,style,selected):
    from app.videos.skill_guidance import animation_guidance
    result=animation_guidance({'subject':subject},{'value':style,'source':'selection'})
    assert selected in result['skill_ids'] and result['style']['value']==style


@pytest.mark.parametrize(('segment','style','selected'), [
    ({'subject':'地理','visuals':'展示地形剖面与水循环过程图像'}, {'value':'按科目自动'}, 'diagram-animation'),
    ({'subject':'综合实践','narration':'用连贯故事和图像解释分享'}, {'value':'story_sketch'}, 'javascript-animation'),
    ({'subject':'地理','visuals':'地形图像'}, {'value':'science_animation','source':'selection'}, 'diagram-animation'),
])
def test_uncategorized_subject_uses_style_or_content_fallback(segment,style,selected):
    from app.videos.skill_guidance import animation_guidance
    result=animation_guidance(segment,style)
    assert selected in result['skill_ids']
    assert result['style']==style




@pytest.mark.parametrize(('segment','style','character','pixel'), [
    ({'subject':'语文','narration':'孔融将梨递给哥哥','teacher_request':'细腻的像素风故事'}, {'value':'按科目自动'}, True, True),
    ({'subject':'数学','narration':'绘制二次函数的抛物线'}, {'value':'按科目自动'}, False, False),
    ({'subject':'物理','visuals':'老师拿起电池，学生连接电路'}, {'value':'按科目自动'}, True, False),
    ({'subject':'语文','narration':'孔融与哥哥分享梨','teacher_request':'不要像素风，采用水墨'}, {'value':'按科目自动'}, True, False),
    ({'subject':'语文','narration':'孔融递梨'}, {'value':'水墨风','source':'selection'}, True, False),
])
def test_character_and_pixel_guidance_follow_content_and_teacher_intent(segment,style,character,pixel):
    from app.videos.skill_guidance import animation_guidance
    result=animation_guidance(segment,style)
    assert ('2d-character-rig-animation' in result['skill_ids']) == character
    assert any(d['path'].endswith('/pixel-art-reference.md') for d in result['documents']) == pixel
    assert result['style']==style
    assert result['runtime_adapter']
    assert len(json.dumps(result,ensure_ascii=False))<24000


def test_character_guidance_keeps_original_sources_and_rejects_forged_license(tmp_path):
    import hashlib
    from app.videos.skill_guidance import SKILLS_ROOT, animation_guidance
    result=animation_guidance({'subject':'语文','narration':'孔融递梨','teacher_request':'像素风'}, {})
    docs=[d for d in result['documents'] if d['skill_id']=='game-graphics']
    assert docs and all(d['repository']=='https://github.com/fenre/skills' and d['commit']=='84bdc1dc884290ad78f4607e0e8f2068695377e7' for d in docs)
    root=tmp_path/'skills';shutil.copytree(SKILLS_ROOT,root)
    license_file=root/'upstream'/'game-graphics'/'LICENSE'
    license_file.write_bytes(b'MIT License')
    registry=root/'sources.json';manifest=json.loads(registry.read_text(encoding='utf-8'))
    manifest['skills']['game-graphics']['files']['LICENSE']=hashlib.sha256(license_file.read_bytes()).hexdigest()
    registry.write_text(json.dumps(manifest),encoding='utf-8')
    with pytest.raises(ValueError,match='许可证'):animation_guidance({}, {},root=root)


@pytest.mark.parametrize('teacher_text',['不采用像素风，采用水墨','禁止像素风','do not use pixel art'])
def test_negative_pixel_requests_do_not_inject_pixel_chapters(teacher_text):
    from app.videos.skill_guidance import animation_guidance
    result=animation_guidance({'subject':'语文','teacher_request':teacher_text}, {'value':'按科目自动'})
    assert not any(doc['path'].endswith('/pixel-art-reference.md') for doc in result['documents'])


def test_local_style_revision_supersedes_original_pixel_request():
    from app.videos.skill_guidance import animation_guidance
    result=animation_guidance({'subject':'语文','teacher_request':'像素风故事',
                              'teacher_visual_instruction':'改为水墨风，动作保持简单'}, {'value':'按科目自动'})
    assert not any(doc['path'].endswith('/pixel-art-reference.md') for doc in result['documents'])


@pytest.mark.parametrize(('subject','content','teacher_text','pixel'),[
    ('语文','大禹带领百姓疏通河道，三过家门而不入。','讲述大禹治水的故事',True),
    ('历史','商人和旅人沿道路运输货物。','讲述古代商人的故事',True),
    ('数学','观察二次函数图像与公式。','讲解二次函数',False),
    ('物理','老师连接电路，观察电流表。','演示串联电路实验',False),
    ('地理','展示水循环过程示意图。','讲解水循环',False),
    ('语文','大禹带领百姓疏通河道。','用水墨风讲述大禹治水',False),
    ('语文','大禹带领百姓疏通河道。','不要使用像素风',False),
    ('物理','科学家的故事，配合展示实验和公式。','通过科学家的故事讲解浮力',True),
    ('综合实践','人物把工具递给同伴。','演示两人合作',True),
    ('语文','展示字词笔顺与结构。','讲解汉字的结构图像',False),
    ('语文','古人沿河行走。','人物故事采用剪纸风',False),
    ('语文','古人沿河行走。','Tell the story in watercolor style',False),
    ('语文','人物使用统一手绘风格，沿河行走。','讲述治水故事',True),
    ('数学','显示公式与函数曲线。','不要故事、不要人物，只展示公式与函数图像',False),
    ('语文','逐笔演示汉字的书写顺序。','讲解汉字笔顺',False),
    ('数学','Display the graph and formula.','Use a graph to teach the history of the coordinate system',False),
])
def test_default_pixel_story_references_keep_graphics_and_explicit_styles(subject,content,teacher_text,pixel):
    from app.videos.quality import resolve_style
    from app.videos.skill_guidance import animation_guidance
    result=animation_guidance({'subject':subject,'narration':content,'teacher_request':teacher_text},resolve_style({'subject':subject}))
    assert any(d['path'].endswith('/pixel-art-reference.md') for d in result['documents'])==pixel
    assert len(json.dumps(result,ensure_ascii=False))<24000


def test_mixed_story_keeps_pixel_and_diagram_references_within_budget():
    from app.videos.quality import resolve_style
    from app.videos.skill_guidance import animation_guidance
    result=animation_guidance({'subject':'物理','teacher_request':'科学家探索浮力的故事',
                               'visuals':'人物在水边做实验，清晰标注浮力公式'},resolve_style({'subject':'物理'}))
    assert 'diagram-animation' in result['skill_ids']
    assert any(d['path'].endswith('/pixel-art-reference.md') for d in result['documents'])
    assert len(json.dumps(result,ensure_ascii=False)) <= 23500


def test_motion_only_revision_keeps_default_pixel_story_references():
    from app.videos.quality import resolve_style
    from app.videos.skill_guidance import animation_guidance
    result=animation_guidance({'subject':'语文','teacher_request':'讲述人物故事',
                               'teacher_visual_instruction':'动作不要太卡通夸张，走慢一点'},resolve_style({'subject':'语文'}))
    assert any(d['path'].endswith('/pixel-art-reference.md') for d in result['documents'])
