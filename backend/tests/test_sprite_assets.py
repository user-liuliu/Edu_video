import json
import shutil
import pytest


def test_story_catalog_is_semantic_and_poses_are_not_animation_cycles():
    from app.videos.sprite_assets import sprite_guidance
    guide=sprite_guidance()
    assert guide['characters'] and guide['environment']
    assert guide['actions']['walk']['frames']==8
    assert guide['actions']['pose']['loop'] is False
    assert 'emotes' not in guide['actions']
    assert len(json.dumps(guide,ensure_ascii=False))<16000
    assert 'base64' not in json.dumps(guide)
    assert 'tree' in guide['environment'] and 'house' in guide['environment']
    assert guide['environment']['dirt']['width']==32
    from PIL import Image
    from app.videos.sprite_assets import ASSET_ROOT
    with Image.open(ASSET_ROOT/'grass.png') as image:
        assert image.convert('RGBA').getchannel('A').getextrema()==(0,255)
    with Image.open(ASSET_ROOT/'water_ripple.png') as image:
        assert image.convert('RGBA').getchannel('A').getextrema()==(0,255)


def test_only_local_pinned_assets_are_embedded_and_source_code_stays_deterministic():
    from app.videos.sprite_assets import assemble_sprites
    from app.videos.direct_html import validate_html
    source='<html><head></head><body><canvas id="c"></canvas><script>window.renderFrame=t=>EduSprites.drawActor(document.getElementById("c").getContext("2d"),{variant:"ochre",x:20,y:40,action:"idle",direction:"down",frame:0,scale:1});</script></body></html>'
    result=assemble_sprites(source,enabled=True)
    assert 'data:image/png;base64,' in result
    assert 'original-local-pixel-art' in result
    assert validate_html(result)==result
    assert len(result.encode())<1_500_000
    assert assemble_sprites(result,enabled=True)==result
    assert assemble_sprites(source,enabled=False)==source
    from app.videos.sprite_assets import model_source
    assert model_source(result)==source
    assert 'base64' not in model_source(result)


def test_corrupt_and_unsafe_asset_entries_are_rejected(tmp_path):
    from app.videos.sprite_assets import ASSET_ROOT,load_bundle
    root=tmp_path/'assets';shutil.copytree(ASSET_ROOT,root)
    manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    first=next(iter(manifest['files']))
    (root/first).write_bytes(b'corrupt')
    with pytest.raises(ValueError,match='素材'):load_bundle(root=root)
    manifest['files']['../outside.png']=manifest['files'].pop(first)
    (root/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
    with pytest.raises(ValueError,match='素材'):load_bundle(root=root)


def test_html_request_never_adds_sprite_catalog_for_new_generation():
    from app.videos.direct_pipeline import html_generation_request
    from app.videos.quality import resolve_style
    def request(subject,prompt,narration,local=''):
        snapshot={'title':'测试','prompt':prompt,'form_values':{'subject':subject},'film_expression':{'visual_prompt':'连续画面'},'outline':{},'style':resolve_style({'subject':subject})}
        return html_generation_request(snapshot,[{'narration':narration,'teacher_visual_instruction':local}],3.)
    story=request('语文','讲述两个人相互帮助的故事','两个人走近并交流。')
    assert 'sprite_library' not in story
    assert '故事演绎中的人物' in story['animation_reference_adapter']
    assert 'sprite_library' not in request('数学','讲解二次函数','抛物线经过原点。')
    assert 'sprite_library' not in request('语文','不要像素风，采用水墨讲述故事','两个人走近并交流。')
    assert 'sprite_library' not in request('语文','像素风故事','两个人走近并交流。','改为水墨风')
    assert 'sprite_library' not in request('语文','像素风故事','两个人走近并交流。','水墨风')
    assert 'sprite_library' not in request('语文','像素风故事','两个人走近并交流。','改用水墨')


async def test_model_html_is_packaged_by_actual_generation_boundary(monkeypatch):
    import httpx
    from app.videos.direct_html import generate_html
    from app.videos.sprite_assets import sprite_guidance
    source='<html><head></head><body><canvas id="c"></canvas><script>window.renderFrame=t=>EduSprites.drawActor(document.getElementById("c").getContext("2d"),{variant:"ochre",x:20,y:40,action:"idle",direction:"down",scale:1});</script></body></html>'
    async def response(*args,**kwargs):return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps({'html':source})}}]})
    monkeypatch.setattr('app.videos.model_stream.animation_response',response)
    config=type('Config',(),{'base_url':'https://example.invalid/v1','api_key':'test','model':'test'})()
    async with httpx.AsyncClient() as http:result=await generate_html(config,{'sprite_library':sprite_guidance()},http)
    assert 'data:image/png;base64,' in result and 'EduSprites' in result


async def test_no_sprite_generation_and_repair_keep_original_contract(monkeypatch):
    import httpx
    from app.videos.direct_html import generate_html
    from app.videos.sprite_assets import sprite_guidance
    source='<html><head></head><body><canvas id="c"></canvas><script>window.renderFrame=t=>{};</script></body></html>'
    calls=[]
    async def response(*args,**kwargs):
        calls.append(args)
        html='<html>bad</html>' if len(calls)==1 else source
        return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps({'html':html})}}]})
    monkeypatch.setattr('app.videos.model_stream.animation_response',response)
    config=type('Config',(),{'base_url':'https://example.invalid/v1','api_key':'test','model':'test'})()
    async with httpx.AsyncClient() as http:
        result=await generate_html(config,{'sprite_library':sprite_guidance()},http,feedback='fix test')
        assert 'edu-sprites-runtime' in result and len(calls)==2
        plain=await generate_html(config,{},http)
        assert plain==source


async def test_runtime_repair_context_omits_program_owned_base64(monkeypatch):
    import httpx
    from app.videos.direct_html import generate_html
    from app.videos.sprite_assets import sprite_guidance,assemble_sprites
    source='<html><head></head><body><canvas id="c"></canvas><script>window.renderFrame=t=>{};</script></body></html>'
    previous=assemble_sprites(source,enabled=True,required=True)
    async def response(http,url,headers,payload):
        request=json.loads(payload['messages'][1]['content'])
        assert request['previous_html']==source
        assert 'base64' not in request['previous_html']
        return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps({'html':source})}}]})
    monkeypatch.setattr('app.videos.model_stream.animation_response',response)
    config=type('Config',(),{'base_url':'https://example.invalid/v1','api_key':'test','model':'test'})()
    async with httpx.AsyncClient() as http:
        result=await generate_html(config,{'sprite_library':sprite_guidance(),'previous_html':previous},http,feedback='runtime failure')
    assert result==previous


def test_asset_file_changes_and_runtime_change_compiler_identity(monkeypatch,tmp_path):
    from app.videos import direct_html,sprite_assets
    before=direct_html.direct_digest()
    original=sprite_assets.load_bundle
    def changed():
        manifest,files,digest=original()
        return manifest,files,'changed'+digest
    monkeypatch.setattr(sprite_assets,'load_bundle',changed)
    assert before!=direct_html.direct_digest()


def test_declared_dimensions_are_verified_and_rehashed_corruption_is_not_a_png(tmp_path):
    from app.videos.sprite_assets import ASSET_ROOT,load_bundle
    import hashlib
    root=tmp_path/'assets';shutil.copytree(ASSET_ROOT,root)
    manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    item=next(iter(manifest['catalog'].values()));file=item['file']
    (root/file).write_bytes(b'not png')
    manifest['files'][file]=hashlib.sha256(b'not png').hexdigest()
    (root/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
    with pytest.raises(ValueError,match='素材'):load_bundle(root=root)


def test_supported_pose_contacts_touch_real_atlas_pixels():
    import subprocess,shutil
    from pathlib import Path
    from PIL import Image
    from app.videos.sprite_assets import ASSET_ROOT
    node=shutil.which('node')
    if not node:pytest.skip('Node required for JS atlas contact check')
    script=Path(__file__).with_name('sprite_motion.cjs')
    contacts=json.loads(subprocess.check_output([node,str(script),'--contacts'],text=True,encoding='utf-8'))
    rows={'up':0,'left':1,'down':2,'right':3}
    manifest=json.loads((ASSET_ROOT/'manifest.json').read_text(encoding='utf-8'))
    sheets={}
    for key,spec in manifest['characters'].items():
        with Image.open(ASSET_ROOT/spec['file']) as image:
            sheets[key]=image.convert('RGBA')
    for contact in contacts:
        pixel=sheets[contact['variant']].getpixel((contact['frame']*64+contact['x'],(manifest['actions'][contact['action']]['row']+rows[contact['direction']])*64+contact['y']))
        assert pixel[3]>240,contact
