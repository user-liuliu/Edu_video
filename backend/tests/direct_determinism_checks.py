"""Offline Chromium checks for deterministic pixels and real state rejection."""
import base64
import io
import math
from pathlib import Path
import unittest
import wave
from app.videos.direct_html import direct_digest
from app.videos.direct_render import film_page, inspect, pixels, same_pixels
from app.videos.render_contract import DirectRenderRequest

SVG = Path(__file__).with_name("fixtures").joinpath("filtered_svg_scene.html").read_text(encoding="utf-8")


def request(html,duration=152.):
    audio=io.BytesIO()
    with wave.open(audio,'wb') as wav:
        wav.setparams((1,2,48000,0,'NONE','not compressed'))
        wav.writeframes(bytes(round(duration*48000)*2))
    return DirectRenderRequest(compiler_digest=direct_digest(),html=html,
        audio_base64=base64.b64encode(audio.getvalue()).decode(),
        manifest={'duration':duration,'source_duration':duration,
                  'clock':[{'t':0.,'source':0.},{'t':duration,'source':duration}],'captions':[]})


class DeterminismChecks(unittest.IsolatedAsyncioTestCase):
    async def test_filtered_svg_matches_when_seeking_back_across_opacity_and_transform_changes(self):
        duration=151.9941956570125
        times=sorted({0.,duration,duration*.25,duration*.5,duration*.75,*[float(i) for i in range(0,math.ceil(duration),2)]})
        from renderer.capture import stable_svg_capture
        async with stable_svg_capture(), film_page(request(SVG,duration)) as (page,errors):
            frames={};doms={}
            for t in times:
                doms[t]=await inspect(page,t);frames[t]=await pixels(page)
                self.assertEqual(await page.frames[1].evaluate('document.body.innerHTML'),doms[t])
            for t in reversed(times):
                self.assertEqual(await inspect(page,t),doms[t])
                self.assertTrue(same_pixels(frames[t],await pixels(page)),f'Pixels changed at {t}')
            self.assertEqual(errors,[])

    async def test_canvas_cumulative_state_remains_rejected(self):
        from app.videos.direct_render import validate_direct
        html='''<html><body><svg width="1" height="1"><defs><filter id="blur"><feGaussianBlur stdDeviation="3"/></filter></defs></svg><canvas id="c" width="1280" height="720"></canvas><script>let n=0;window.renderFrame=t=>{let c=document.getElementById('c').getContext('2d');c.fillStyle=(++n%2)?'red':'blue';c.fillRect(0,0,1280,720);};</script></body></html>'''
        from renderer.capture import stable_svg_capture
        async with stable_svg_capture():
            with self.assertRaisesRegex(ValueError,'累计状态'):
                await validate_direct(request(html,1.))


    async def test_dom_cumulative_state_remains_rejected(self):
        from app.videos.direct_render import validate_direct
        from renderer.capture import stable_svg_capture
        html='''<html><body><svg><defs><filter id="blur"><feGaussianBlur stdDeviation="3"/></filter></defs><text id="label">0</text></svg><script>let n=0;window.renderFrame=t=>document.getElementById('label').textContent=++n;</script></body></html>'''
        async with stable_svg_capture():
            with self.assertRaisesRegex(ValueError,'倒退定位'):
                await validate_direct(request(html,1.))

    async def test_autonomous_css_animation_remains_rejected(self):
        from app.videos.direct_render import validate_direct
        from renderer.capture import stable_svg_capture
        html='''<html><head><style>@keyframes spin{to{transform:rotate(360deg)}} svg{animation:spin 1s linear infinite}</style></head><body><svg width="200" height="200"><defs><filter id="blur"><feGaussianBlur stdDeviation="3"/></filter></defs><rect width="100" height="200" fill="red"/></svg><script>window.renderFrame=t=>{};</script></body></html>'''
        async with stable_svg_capture():
            with self.assertRaisesRegex(ValueError,'绝对时钟'):
                await validate_direct(request(html,1.))

    async def test_worker_exports_filtered_svg_through_real_encoder(self):
        import asyncio
        import json
        import sys
        import tempfile
        from app.videos.export import decode_check
        payload=request(SVG,4.).model_dump()
        payload['manifest'].update(source_duration=151.9941956570125,clock=[
            {'t':0.,'source':0.},{'t':.1,'source':120.},
            {'t':3.9,'source':126.},{'t':4.,'source':151.9941956570125}])
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name)
            (folder/'request.json').write_text(json.dumps(payload))
            process=await asyncio.create_subprocess_exec(sys.executable,'-m','renderer.worker','render-html',name,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
            stdout,stderr=await asyncio.wait_for(process.communicate(),120)
            self.assertEqual(process.returncode,0,stderr.decode()[-2000:])
            metadata=json.loads((folder/'metadata.json').read_text())
            self.assertAlmostEqual(metadata['duration'],4.,delta=.1)
            self.assertEqual((metadata['width'],metadata['height']),(1280,720))
            self.assertGreater((folder/'output.mp4').stat().st_size,1000)
            await asyncio.to_thread(decode_check,folder/'output.mp4')

if __name__=='__main__':
    from renderer.resources import limit_cpu_affinity
    limit_cpu_affinity()
    unittest.main()