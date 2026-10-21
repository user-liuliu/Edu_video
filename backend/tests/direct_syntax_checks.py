"""Browser regression checks; run in the isolated renderer, without credentials."""
import base64
import io
import unittest
import wave
from app.videos.direct_html import direct_digest
from app.videos.render_contract import DirectHtmlRuntimeError, DirectRenderRequest
from renderer.worker import validate_direct
from app.videos.checked_render import check_syntax


def request(script, prefix=''):
    audio=io.BytesIO()
    with wave.open(audio,'wb') as wav:
        wav.setparams((1,2,48000,0,'NONE','not compressed'))
        wav.writeframes(bytes(96000))
    html='<!doctype html>\n<html><body><div id=stage></div>\n'+prefix+'<script>\n'+script+'\n</script></body></html>'
    return DirectRenderRequest(compiler_digest=direct_digest(),html=html,
        audio_base64=base64.b64encode(audio.getvalue()).decode(),
        manifest={'duration':1.,'source_duration':1.,'clock':[{'t':0.,'source':0.},{'t':1.,'source':1.}],'captions':[]})


class SyntaxChecks(unittest.IsolatedAsyncioTestCase):
    async def test_reports_original_syntax_error_instead_of_missing_interface(self):
        with self.assertRaises(DirectHtmlRuntimeError) as caught:
            await validate_direct(request('window.renderFrame=t=>{};\nconst broken = );'))
        message=str(caught.exception)
        self.assertIn('SyntaxError',message)
        self.assertIn("Unexpected token ')'",message)
        self.assertIn('script 1',message)
        self.assertIn('HTML line 5',message)
        self.assertNotIn('缺少renderFrame',message)

    async def test_ignores_data_script_and_accepts_complex_javascript(self):
        script='const r=/[(){}]/g; const s=`value ${[1,2].map(x=>x*2).join("/")}`; window.renderFrame=t=>{document.getElementById("stage").textContent=s+String(t).replace(r,"");};'
        self.assertEqual(await validate_direct(request(script,'<script type="application/json">{"not javascript":")"}</script>')),{'validated':True})

    async def test_later_script_syntax_error_is_not_hidden_by_valid_interface(self):
        with self.assertRaises(DirectHtmlRuntimeError) as caught:
            await validate_direct(request('window.renderFrame=t=>{};</script><script>const broken = );'))
        self.assertIn('SyntaxError',str(caught.exception))
        self.assertIn('script 2',str(caught.exception))

    async def test_syntax_check_compiles_without_running_generated_code(self):
        await check_syntax('<html><script>throw new Error("MUST NOT EXECUTE"); while(true){}; window.renderFrame=t=>{};</script></html>')


if __name__=='__main__':unittest.main()
