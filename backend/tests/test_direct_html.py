import io
import wave

import pytest

HTML = '<!doctype html><html><body><svg width=1280 height=720><circle id=c r=20/></svg><script>window.renderFrame=t=>document.getElementById("c").setAttribute("cx",100+t*10);</script></body></html>'


def test_direct_html_contract_and_sealed_player_escape_code():
    from app.videos.direct_html import validate_html, seal_html, DIRECT_PROTOCOL
    assert validate_html(HTML) == HTML
    manifest = {'duration':2., 'source_duration':3., 'clock':[{'t':0.,'source':0.},{'t':2.,'source':3.}],
                'captions':[{'start':0.,'end':2.,'text':'</script><img src=x>'}]}
    sealed = seal_html(HTML, manifest, (1280,720))
    assert 'sandbox="allow-scripts"' in sealed
    assert '</script><img src=x>' not in sealed
    assert DIRECT_PROTOCOL in sealed
    assert 'connect-src' in sealed and 'edu-preview:seek' in sealed


@pytest.mark.parametrize('extra', [
    '<script src="https://evil.invalid/a.js"></script>', '<iframe src=x></iframe>',
    '<img src="https://evil.invalid/a.png">', '<meta http-equiv=refresh content="0;url=https://evil.invalid">',
    '<style>body{background:url(https://evil.invalid/a)}</style>',
    '<script>fetch("/api/private")</script>', '<script>setInterval(()=>{},1)</script>',
    '<script>parent.location="https://evil.invalid"</script>', '<script>eval("alert(1)")</script>',
])
def test_direct_html_rejects_external_resources_and_autonomous_playback(extra):
    from app.videos.direct_html import validate_html
    with pytest.raises(ValueError): validate_html(HTML.replace('</body>', extra+'</body>'))


def test_whole_clock_aligns_provider_subtitle_splits_and_keeps_pauses_monotone():
    from app.videos.direct_html import align_clock
    cues=[{'start':0.,'end':2.,'text':'观察直线。'},{'start':2.5,'end':4.,'text':'比较斜率。'}]
    captions=[{'start':.1,'end':.8,'text':'观察'},{'start':.8,'end':1.5,'text':'直线。'},
              {'start':2.,'end':3.,'text':'比较斜率。'}]
    clock=align_clock(cues,captions,4.,3.1)
    assert clock[0]=={'t':0.,'source':0.}
    assert clock[-1]=={'t':3.1,'source':4.}
    assert all(a['t']<b['t'] and a['source']<=b['source'] for a,b in zip(clock,clock[1:]))
    with pytest.raises(ValueError): align_clock(cues,[{**captions[0],'text':'错字'}],4.,3.)


def test_join_audio_rejects_inconsistent_format_and_keeps_exact_pcm():
    from app.videos.direct_html import join_audio
    def wav(rate, sample):
        out=io.BytesIO()
        with wave.open(out,'wb') as w:
            w.setparams((1,2,rate,0,'NONE','not compressed'));w.writeframes(sample*480)
        return out.getvalue()
    first,second=wav(48000,b'\x01\x00'),wav(48000,b'\x02\x00')
    result=join_audio([first,second])
    with wave.open(io.BytesIO(result),'rb') as w:
        assert w.readframes(w.getnframes())==b'\x01\x00'*480+b'\x02\x00'*480
    with pytest.raises(ValueError): join_audio([first,wav(24000,b'\x01\x00')])


def test_manifest_sealing_survives_json_database_key_order():
    import json
    from app.videos.direct_html import seal_html
    manifest={'source_duration':2.,'duration':1.,'clock':[{'source':0.,'t':0.},{'source':2.,'t':1.}],
              'captions':[{'text':'讲解','end':1.,'start':0.}]}
    assert seal_html(HTML,manifest,(1280,720))==seal_html(HTML,json.loads(json.dumps(manifest,sort_keys=True)),(1280,720))


def test_local_parent_drawing_parameter_is_allowed():
    from app.videos.direct_html import validate_html
    source=HTML.replace('<script>','<script>function add(parent,node){parent.appendChild(node);}')
    assert validate_html(source)==source


async def test_upstream_authentication_error_is_not_misreported_as_html_structure():
    import httpx
    from app.outline.model_client import ModelCallError
    from app.videos.direct_html import generate_html
    config=type('Config',(),{'base_url':'https://example.invalid/v1','api_key':'fake','model':'test'})()
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req:httpx.Response(401,json={'error':{'code':'invalid_api_key'}}))) as http:
        with pytest.raises(ModelCallError) as caught:await generate_html(config,{},http)
    assert caught.value.category=='authentication'
