import io
import wave

import pytest

from app.videos.speech import Narration


def wav(seconds=2.0, rate=48000, channels=1):
    frames=int(seconds*rate)
    pcm=b''.join(((i % 2000)-1000).to_bytes(2,'little',signed=True)*channels for i in range(frames))
    stream=io.BytesIO()
    with wave.open(stream,'wb') as w:
        w.setparams((channels,2,rate,0,'NONE','not compressed'));w.writeframes(pcm)
    return stream.getvalue()


def pcm(data):
    with wave.open(io.BytesIO(data),'rb') as w:
        return w.readframes(w.getnframes())


def narration(seconds=2.0, captions=None, **kwargs):
    return Narration(wav(seconds,**kwargs),captions or [
        {'start':0.1,'end':.8,'text':'第一段。'},
        {'start':1.2,'end':1.9,'text':'第二段。'},
    ])


def test_complete_adjacent_paragraphs_share_a_bounded_synthesis_block():
    from app.videos.continuous_speech import plan_blocks
    assert plan_blocks(['第一段。','第二段。'],['',''],[False,False])==[(0,1)]
    assert plan_blocks(['段落。']*4,['']*4,[False]*4)==[(0,1,2),(3,)]
    assert plan_blocks(['甲'*149+'。']*3,['']*3,[False]*3)==[(0,1),(2,)]


@pytest.mark.parametrize('instructions,reusable,expected',[
    (['','',''],[False,True,False],[(0,),(1,),(2,)]),
    (['','','放慢语速'],[False]*3,[(0,1),(2,)]),
    (['放慢语速','自然','自然'],[False]*3,[(0,),(1,2)]),
])
def test_cached_audio_and_distinct_voice_edit_instructions_are_hard_boundaries(instructions,reusable,expected):
    from app.videos.continuous_speech import plan_blocks
    assert plan_blocks(['第一段。','第二段。','第三段。'],instructions,reusable)==expected


def test_fragments_and_system_voice_keep_the_existing_single_request_path():
    from app.videos.continuous_speech import plan_blocks
    assert plan_blocks(['尚未说完','下一段。'],['',''],[False]*2)==[(0,),(1,)]
    assert plan_blocks(['第一段。','第二段。'],['',''],[False]*2,enabled=False)==[(0,),(1,)]


def test_an_incoming_fragment_is_not_appended_to_a_complete_paragraph():
    from app.videos.continuous_speech import plan_blocks
    assert plan_blocks(['完整句。','未完片段'],['',''],[False]*2)==[(0,),(1,)]


def test_fallback_positions_remain_single_even_when_the_cached_prefix_changes():
    from app.videos.continuous_speech import plan_blocks
    assert plan_blocks(['第一段。','第二段。','第三段。'],['']*3,[True,False,False],force_single={0,1,2})==[(0,),(1,),(2,)]


def test_keep_adjacent_paragraphs_in_the_same_topic_together_instead_of_filling_the_previous_block():
    from app.videos.continuous_speech import plan_blocks
    texts=['甲'*100+'。','乙'*100+'。','丙'*100+'。']
    assert plan_blocks(texts,['']*3,[False]*3,topics=['一次函数','二次函数','二次函数'])==[(0,),(1,2)]
    assert plan_blocks(texts,['']*3,[False,False,True],topics=['一次函数','二次函数','二次函数'])==[(0,1),(2,)]
    assert plan_blocks(texts,['','','慢一些'],[False]*3,topics=['一次函数','二次函数','二次函数'])==[(0,1),(2,)]


@pytest.mark.parametrize('channels',[1,2])
def test_split_preserves_pcm_exactly_and_offsets_subtitles_without_duplicate_pause(channels):
    from app.videos.continuous_speech import split_narration
    source=narration(channels=channels)
    parts=split_narration(source,['第一段。','第二段。'])
    assert len(parts)==2
    assert b''.join(pcm(p.audio) for p in parts)==pcm(source.audio)
    assert parts[0].captions==[{'start':.1,'end':.8,'text':'第一段。'}]
    assert parts[1].captions[0]['start']==pytest.approx(.2)
    assert parts[1].captions[0]['end']==pytest.approx(.9)
    for part in parts:
        with wave.open(io.BytesIO(part.audio),'rb') as w:
            assert w.getnframes()%(w.getframerate()//30)==0


def test_split_handles_punctuation_and_whitespace_with_the_existing_caption_contract():
    from app.videos.continuous_speech import split_narration
    source=narration(captions=[{'start':.1,'end':.8,'text':'第一段！'}, {'start':1.2,'end':1.9,'text':'第 二段。'}])
    parts=split_narration(source,['第一段。\n','第二段。'])
    assert b''.join(pcm(p.audio) for p in parts)==pcm(source.audio)


@pytest.mark.parametrize('captions',[
    [{'start':.1,'end':1.9,'text':'第一段。第二段。'}],
    [{'start':.1,'end':1.001,'text':'第一段。'},{'start':1.002,'end':1.9,'text':'第二段。'}],
    [{'start':.1,'end':1.3,'text':'第一段。'},{'start':1.2,'end':1.9,'text':'第二段。'}],
    [{'start':.1,'end':.8,'text':'第一段。'},{'start':1.2,'end':2.1,'text':'第二段。'}],
    [{'start':.1,'end':.8,'text':'第一段。'},{'start':1.2,'end':1.9,'text':'漏读。'}],
])
def test_never_guess_a_cut_through_a_caption_or_invalid_timestamps(captions):
    from app.videos.continuous_speech import split_narration,UnsplittableNarration
    with pytest.raises(UnsplittableNarration):split_narration(narration(captions=captions),['第一段。','第二段。'])


def test_tail_frame_padding_is_added_only_once_for_the_whole_block():
    from app.videos.continuous_speech import split_narration
    source=narration(seconds=2.005)
    parts=split_narration(source,['第一段。','第二段。'])
    joined=b''.join(pcm(p.audio) for p in parts)
    original=pcm(source.audio)
    assert joined.startswith(original)
    assert joined[len(original):]==bytes(len(joined)-len(original))
    assert 0<len(joined)-len(original)<48000*2/30


def test_non_frame_aligned_sample_rate_is_rejected():
    from app.videos.continuous_speech import split_narration,UnsplittableNarration
    with pytest.raises(UnsplittableNarration):split_narration(narration(rate=22051),['第一段。','第二段。'])


@pytest.mark.parametrize('seconds',[2.,2.005])
def test_truncated_pcm_is_rejected_before_frame_padding(seconds):
    from app.videos.continuous_speech import split_narration,UnsplittableNarration
    source=narration(seconds=seconds)
    truncated=Narration(source.audio[:-48000],source.captions)
    with pytest.raises(UnsplittableNarration):split_narration(truncated,['第一段。','第二段。'])
