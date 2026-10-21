import json
import importlib.util
from pathlib import Path
from PIL import Image


def test_original_catalog_has_distinct_age_and_costume_groups():
    from app.videos.sprite_assets import load_bundle, sprite_guidance, ASSET_ROOT
    manifest, files, _ = load_bundle()
    assert manifest.get('art_origin') == 'original-local-pixel-art'
    assert len(manifest['characters']) >= 20
    assert len(sprite_guidance()['characters']) >= 20
    assert {'child', 'adult', 'elder'} <= {x['age'] for x in manifest['characters'].values()}
    assert len({files[x['file']] for x in manifest['characters'].values()}) == len(manifest['characters'])
    assert len(json.dumps(sprite_guidance(), ensure_ascii=False)) < 16000
    for item in manifest['characters'].values():
        with Image.open(ASSET_ROOT / item['file']) as im:
            im = im.convert('RGBA')
            assert sum(im.getchannel('A').histogram()[1:255]) == 0
            assert im.getchannel('A').getextrema() == (0, 255)
            for action in ('idle', 'walk', 'run', 'wave', 'nod', 'talk', 'pickup', 'carry', 'sit', 'jump', 'work'):
                spec = manifest['actions'][action]
                frames = [im.crop((i*64, spec['row']*64, (i+1)*64, (spec['row']+1)*64)) for i in range(spec['frames'])]
                assert len({frame.tobytes() for frame in frames}) >= 2, (item['file'], action)
                for frame in frames:
                    box = frame.getbbox()
                    assert box and min(box[:2]) > 0 and box[2] < 64 and box[3] < 64


def test_original_sprite_payload_fits_existing_html_contract():
    from app.videos.sprite_assets import assemble_sprites
    from app.videos.direct_html import validate_html
    html = '<html><head></head><body><canvas></canvas><script>window.renderFrame=t=>{};</script></body></html>'
    result = assemble_sprites(html, enabled=True)
    assert validate_html(result) == result
    assert 'original-local-pixel-art' in result
    assert 'Lanea Zimmerman' not in result
    assert len(result.encode()) < 1_500_000


def test_backpack_and_apron_have_readable_back_and_side_views():
    source=Path(__file__).resolve().parents[2]/'pixel-art/original-cast/build.py'
    spec=importlib.util.spec_from_file_location('original_art_builder',source)
    builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
    traveler=next(c for c in builder.CAST if c['key']=='traveler')
    for direction in ('up','left','right'):
        image,_=builder.draw_character(traveler,'idle',0,direction)
        plain,_=builder.draw_character({**traveler,'accessory':''},'idle',0,direction)
        changed=sum(a!=b for a,b in zip(image.tobytes()[::4],plain.tobytes()[::4]))
        assert changed>15,(direction,changed)
    chef=next(c for c in builder.CAST if c['key']=='chef')
    back,_=builder.draw_character(chef,'idle',0,'up')
    front,_=builder.draw_character(chef,'idle',0,'down')
    assert front.getpixel((32,48)) != back.getpixel((32,48)), 'Apron front must become straps and ties on back'


def test_frozen_videos_keep_their_own_embedded_art_credits():
    from app.videos.sprite_assets import export_metadata,assemble_sprites
    html='<html><head></head><body><canvas></canvas><script>window.renderFrame=t=>{};</script></body></html>'
    original=assemble_sprites(html,enabled=True)
    metadata=export_metadata(original)
    assert 'original-local-pixel-art' in metadata['copyright']
    legacy='<!-- EDU-SPRITES '+'a'*64+'\nLPC assets; retained old artist credits; OGA-BY 3.0 -->\n<script id="edu-sprites-runtime">frozen</script>'
    old=export_metadata(legacy)
    assert old['copyright']=='LPC assets; retained old artist credits; OGA-BY 3.0'
    assert 'original' not in old['copyright']
    assert export_metadata(html)=={}
