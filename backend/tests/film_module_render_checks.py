"""Offline browser verification of modular scenes, transitions and unchanged frames."""
import unittest
from copy import deepcopy
from direct_determinism_checks import request
from app.videos.film_modules import assemble_film,patch_film
from app.videos.direct_render import film_page,inspect,pixels,same_pixels,check_page


def fixture():
    targets=[{'id':f's{i}','render_key':f's{i}','start':i*2.,'end':(i+1)*2.} for i in range(4)]
    bundle={'shared_html':'<style>svg{width:1280px;height:720px}text{font:36px sans-serif}</style>',
        'shared_code':'return {ease:p=>p*p*(3-2*p)};',
        'segments':[{'id':f's{i}','html':f'<svg viewBox="0 0 1280 720"><rect width="1280" height="720" fill="#eee8d0"/><circle id="actor" cx="200" cy="300" r="60" fill="#287a68"/><text x="100" y="100">场景{i}</text></svg>',
            'code':"root.querySelector('#actor').setAttribute('cx',String(200+400*shared.ease(progress)));"} for i in range(4)],
        'transitions':[{'from_id':f's{i}','to_id':f's{i+1}','duration':.6,
            'code':'outgoing.style.opacity=String(1-progress);incoming.style.opacity=String(progress);'} for i in range(3)]}
    return bundle,targets


class FilmModuleChecks(unittest.IsolatedAsyncioTestCase):
    async def test_compiled_modules_play_and_seek_with_smooth_boundary_frames(self):
        bundle,targets=fixture()
        async with film_page(request(assemble_film(bundle,targets),8.)) as (page,errors):
            await check_page(page,errors,8.)
            for t in (1.7,1.85,2.,2.15,2.3):
                await inspect(page,t)
                styles=await page.frames[1].evaluate("Array.from(document.querySelectorAll('[data-edu-segment]')).slice(0,2).map(e=>({display:e.style.display,opacity:Number(e.style.opacity)}))")
                self.assertTrue(all(s['display']=='block' for s in styles))
                progress=(t-1.7)/.6
                fade=progress*progress*(3-2*progress)
                self.assertAlmostEqual(styles[0]['opacity'],1.-fade,places=5)
                self.assertAlmostEqual(styles[1]['opacity'],1.,places=5)
            self.assertEqual(errors,[])

    async def test_crossfade_does_not_expose_backdrop_or_brighten_unchanged_scene(self):
        import numpy as np
        bundle,targets=fixture()
        for scene in bundle['segments']:
            scene['html']='<svg viewBox="0 0 1280 720"><rect width="1280" height="720" fill="#284c60"/></svg>'
            scene['code']=';'
        for code in (';', 'const q=progress*progress*(3-2*progress);outgoing.style.opacity=String(1-q);incoming.style.opacity=String(q);'):
            for transition in bundle['transitions']:
                transition['code']=code
            async with film_page(request(assemble_film(bundle,targets),8.)) as (page,errors):
                await inspect(page,0.5)
                reference=await pixels(page)
                for t in (1.7,1.85,2.,2.15,2.3,4.,6.,2.,1.85):
                    await inspect(page,t)
                    current=await pixels(page)
                    difference=np.abs(reference[:310]-current[:310])
                    self.assertLessEqual(float(difference.max()),1.,f'Transition changed constant scene brightness at {t}')
                self.assertEqual(errors,[])

    async def test_transition_blends_both_scenes_without_exposing_stage_background(self):
        import numpy as np
        bundle,targets=fixture()
        colors=('#d04030','#2850d0','#30a050','#d0a030')
        for scene,color in zip(bundle['segments'],colors):
            scene['html']=f'<svg viewBox="0 0 1280 720"><rect width="1280" height="720" fill="{color}"/></svg>'
            scene['code']=';'
        for transition in bundle['transitions']:
            transition['code']='const q=progress*progress*(3-2*progress);outgoing.style.opacity=String(1-q);incoming.style.opacity=String(q);'
        async with film_page(request(assemble_film(bundle,targets),8.)) as (page,errors):
            await inspect(page,2.)
            frame=await pixels(page)
            pixel=frame[100,100,:3].astype(np.float32)
            expected=(np.array([208,64,48])+np.array([40,80,208]))/2
            self.assertTrue(np.all(np.abs(pixel-expected)<=2),f'Expected a smooth red/blue blend, got {pixel}')
            self.assertEqual(errors,[])

    async def test_local_revision_preserves_other_scenes_and_nonadjacent_transition_pixels(self):
        bundle,targets=fixture();original=deepcopy(bundle)
        revised_scene={**bundle['segments'][1],'html':bundle['segments'][1]['html'].replace('#287a68','#d48937')}
        revised=patch_film(bundle,{'segments':[revised_scene],'transitions':bundle['transitions'][:2]},['s1'],targets)
        self.assertEqual(bundle,original)
        self.assertEqual(revised['transitions'][2],bundle['transitions'][2])
        before={};changed=None
        async with film_page(request(assemble_film(bundle,targets),8.)) as (page,errors):
            for t in (.4,4.4,5.85,6.,6.15,7.6):
                await inspect(page,t);before[t]=await pixels(page)
            await inspect(page,3.);changed=await pixels(page)
            self.assertEqual(errors,[])
        async with film_page(request(assemble_film(revised,targets),8.)) as (page,errors):
            await check_page(page,errors,8.)
            for t,expected in before.items():
                await inspect(page,t);self.assertTrue(same_pixels(expected,await pixels(page)),f'Unselected frame changed at {t}')
            await inspect(page,3.);self.assertFalse(same_pixels(changed,await pixels(page)))
            self.assertEqual(errors,[])

    async def test_continuous_scene_uses_one_opaque_layer_without_container_motion(self):
        bundle,targets=fixture()
        for scene in bundle['segments']:
            scene['code']="root.querySelector('#actor').setAttribute('cx',String(200+20*t));"
        # Even a stale model bridge must not fade or move a continuous canvas.
        for transition in bundle['transitions']:
            transition.update(mode='continuous',code="outgoing.style.opacity='.5';incoming.style.transform='translateX(200px)';")
        async with film_page(request(assemble_film(bundle,targets),8.)) as (page,errors):
            for t,expected in ((1.8,'s0'),(2.,'s1'),(2.2,'s1'),(6.,'s3'),(0.,'s0')):
                await inspect(page,t)
                layers=await page.frames[1].evaluate("Array.from(document.querySelectorAll('[data-edu-segment]')).filter(e=>e.style.display==='block').map(e=>({id:e.dataset.eduSegment,opacity:e.style.opacity,transform:e.style.transform}))")
                self.assertEqual(layers,[{'id':expected,'opacity':'1','transform':'none'}])
            self.assertEqual(errors,[])

    async def test_continuous_seams_reject_a_teleport_instead_of_hiding_it_with_a_fade(self):
        bundle,targets=fixture()
        for transition in bundle['transitions']:transition.update(mode='continuous',code=';')
        # Actor moves 600 -> 200 at each boundary: deterministic but discontinuous.
        async with film_page(request(assemble_film(bundle,targets),8.)) as (page,errors):
            with self.assertRaisesRegex(ValueError,'连续场景.*s0.*s1'):
                await check_page(page,errors,8.)

    async def test_continuous_seams_keep_exact_scene_state_with_retimed_audio(self):
        bundle,targets=fixture()
        for scene in bundle['segments']:
            scene['html']=scene['html'].replace('场景'+scene['id'][1:],'连续画布')
            scene['code']="root.querySelector('#actor').setAttribute('cx',String(200+20*t));"
        for transition in bundle['transitions']:transition.update(mode='continuous',code=';')
        req=request(assemble_film(bundle,targets),4.)
        req.manifest.update(source_duration=8.,clock=[{'t':0.,'source':0.},{'t':4.,'source':8.}])
        async with film_page(req) as (page,errors):
            await check_page(page,errors,4.)
            self.assertEqual(errors,[])

    async def test_shadow_dom_autonomous_animation_is_rejected_before_capture(self):
        bundle,targets=fixture()
        bundle['shared_html']+='<style>@keyframes pulse{to{opacity:.3}}#actor{animation:pulse 1s linear infinite}</style>'
        async with film_page(request(assemble_film(bundle,targets),8.)) as (page,errors):
            with self.assertRaisesRegex(Exception,'绝对时钟'):
                await inspect(page,1.)

    async def test_filtered_svg_in_shadow_dom_remains_deterministic(self):
        from renderer.capture import stable_svg_capture
        bundle,targets=fixture()
        bundle['shared_html']+='<svg width="0" height="0"><defs><filter id="blur"><feGaussianBlur stdDeviation="2"/></filter></defs></svg>'
        for scene in bundle['segments']:
            scene['html']=scene['html'].replace('id="actor"','id="actor" filter="url(#blur)"')
            scene['code']+="root.querySelector('#actor').setAttribute('opacity',String(.6+.3*progress));"
        async with stable_svg_capture(),film_page(request(assemble_film(bundle,targets),8.)) as (page,errors):
            await check_page(page,errors,8.)


if __name__=='__main__':
    from renderer.resources import limit_cpu_affinity
    limit_cpu_affinity()
    unittest.main()
