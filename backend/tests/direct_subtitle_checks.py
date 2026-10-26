"""Offline browser regressions for stable subtitles across narration boundaries."""
import unittest
from direct_determinism_checks import request
from app.videos.direct_render import film_page,inspect

HTML='<html><body style="margin:0;background:#eee8d0"><script>window.renderFrame=function(t){};</script></body></html>'

def subtitle_request():
    value=request(HTML,5.)
    value.manifest['captions']=[
        {'start':.2,'end':1.,'text':'Previous sentence'},
        {'start':1.016,'end':2.,'text':'Next sentence'},
        {'start':2.038,'end':3.,'text':'Third sentence'},
        {'start':3.5,'end':4.8,'text':'After a longer pause'},
    ]
    return value

async def caption_state(page,t):
    await inspect(page,t)
    return await page.evaluate("(()=>{const c=document.getElementById('caption'),r=c.getBoundingClientRect();return {text:c.textContent,display:getComputedStyle(c).display,y:r.y,height:r.height}})()")

class SubtitleChecks(unittest.IsolatedAsyncioTestCase):
    async def test_subframe_gaps_do_not_hide_caption_or_its_background(self):
        async with film_page(subtitle_request()) as (page,errors):
            previous=await caption_state(page,.99)
            for t in (1.,1.008,1.0159):
                state=await caption_state(page,t)
                self.assertEqual(state,previous,f'Subtitle flashed off at {t}')
            self.assertEqual((await caption_state(page,1.016))['text'],'Next sentence')
            for t in (2.,2.02,2.0379):
                state=await caption_state(page,t)
                self.assertEqual(state['text'],'Next sentence')
                self.assertNotEqual(state['display'],'none')
            self.assertEqual((await caption_state(page,2.038))['text'],'Third sentence')
            self.assertEqual(errors,[])

    async def test_long_pauses_endpoints_and_reverse_seeking_preserve_caption_timing(self):
        samples=((0.,''),(3.1,''),(3.499,''),(3.5,'After a longer pause'),
                 (4.8,''),(5.,''),(2.5,'Third sentence'),(1.008,'Previous sentence'),
                 (.1,''),(2.02,'Next sentence'),(3.2,''),(1.5,'Next sentence'))
        async with film_page(subtitle_request()) as (page,errors):
            for t,text in samples:
                self.assertEqual((await caption_state(page,t))['text'],text,f'Wrong subtitle at {t}')
            self.assertEqual(errors,[])

if __name__=='__main__':
    from renderer.resources import limit_cpu_affinity
    limit_cpu_affinity()
    unittest.main()
