"""Run in isolated renderer image; no database or model credentials."""
import asyncio
import base64
import io
import json
from pathlib import Path
import wave
from app.videos.direct_html import direct_digest,join_audio
from app.videos.direct_render import validate_direct,render_direct,film_page
from app.videos.render_contract import DirectRenderRequest


async def main():
    out=Path('/tmp/direct-checks');out.mkdir(exist_ok=True)
    tiny='<!doctype html><html><body><svg width="1280" height="720"><circle id="c" r="25" cy="200"/></svg><script>window.renderFrame=t=>document.getElementById("c").setAttribute("cx",100+t*40);</script></body></html>'
    wav=io.BytesIO()
    with wave.open(wav,'wb') as w:w.setparams((1,2,48000,0,'NONE','not compressed'));w.writeframes(bytes(48000*2))
    manifest={'duration':1.,'source_duration':1.,'clock':[{'t':0.,'source':0.},{'t':1.,'source':1.}], 'captions':[{'start':0.,'end':1.,'text':'测试字幕'}]}
    request=DirectRenderRequest(compiler_digest=direct_digest(),html=tiny,manifest=manifest,audio_base64=base64.b64encode(wav.getvalue()).decode())
    assert await validate_direct(request)=={'validated':True}
    metadata=await render_direct(request,out/'tiny.mp4')
    assert abs(metadata['duration']-1)<.1
    print('TINY_RENDER_PASS',flush=True)
    bad=tiny.replace('<svg width="1280" height="720"><circle id="c" r="25" cy="200"/></svg>','<canvas id="c" width="1280" height="720"></canvas>').replace('window.renderFrame=t=>document.getElementById("c").setAttribute("cx",100+t*40);','let n=0;window.renderFrame=t=>{const c=document.getElementById("c").getContext("2d");c.fillStyle=(++n%2)?"red":"blue";c.fillRect(0,0,1280,720);};')
    nondeterministic=request.model_copy(update={'html':bad})
    try:await validate_direct(nondeterministic)
    except ValueError:pass
    else:raise AssertionError('Canvas drawing with hidden cumulative state must fail runtime validation')
    for kind in ('science','story'):
        folder=Path('/samples')/kind
        old=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
        manifest={k:old[k] for k in ('duration','source_duration','clock','captions')}
        audio=join_audio([(folder/f'{i}-audio.wav').read_bytes() for i in range(4)])
        request=DirectRenderRequest(compiler_digest=direct_digest(),html=(folder/'generated.html').read_text(encoding='utf-8'),manifest=manifest,audio_base64=base64.b64encode(audio).decode())
        result=await validate_direct(request)
        print(kind.upper()+'_RUNTIME_PASS '+str(result),flush=True)
        if '--full' in __import__('sys').argv:
            metadata=await render_direct(request,out/(kind+'.mp4'))
            print(kind.upper()+'_EXPORT_PASS '+json.dumps(metadata),flush=True)
    (out/'passed.json').write_text(json.dumps({'tiny':True,'sample_runtime':['science','story'],'speech_provider_calls':0}),encoding='utf-8')


if __name__=='__main__':asyncio.run(main())
