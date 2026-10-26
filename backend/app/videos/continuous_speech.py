"""Bounded continuous synthesis and lossless, subtitle-confirmed paragraph cuts."""
import io
import math
import re
import wave

from .media_assets import align_audio
from .speech import Narration, verified_captions
from .timing import spoken

PROTOCOL = 'continuous-narration-1'
MAX_CHARACTERS = 300
MAX_PARAGRAPHS = 3
CONTINUITY_INSTRUCTION = (
    '把全部正文作为一次连续的课堂讲解，优先遵循指定的语速语气，保持同一人的声线与音量；'
    '在相邻内容间自然承接、适当停顿，中途不要重新开场，不要增加、改写或省略正文。'
)


class UnsplittableNarration(ValueError):
    """Use individual paragraphs rather than guess where a spoken word ends."""


def _complete(text):
    return bool(re.search(r'[。！？!?][”’\"\u0027）)]*\s*$',text))


def plan_blocks(texts, instructions, reusable, *, enabled=True, force_single=(), topics=None):
    if not len(texts) == len(instructions) == len(reusable):
        raise ValueError('配音段落映射不一致')
    if topics is not None and len(topics)!=len(texts):raise ValueError('配音章节映射不一致')
    blocks=[]
    for index, text in enumerate(texts):
        previous=blocks[-1] if blocks else ()
        # Reserve room for the next paragraph of the same chapter, rather than
        # filling an unrelated preceding block and splitting that chapter apart.
        reserve_next=(topics is not None and previous and index+1<len(texts)
            and topics[index] and topics[index]!=topics[previous[-1]] and topics[index]==topics[index+1]
            and not reusable[index+1] and index+1 not in force_single
            and instructions[index]==instructions[index+1] and _complete(text) and _complete(texts[index+1])
            and len(text)+len(texts[index+1])<=MAX_CHARACTERS
            and (len(previous)+2>MAX_PARAGRAPHS
                 or sum(len(texts[i]) for i in previous)+len(text)+len(texts[index+1])>MAX_CHARACTERS))
        if (enabled and previous and not reusable[index] and index not in force_single
                and previous[-1] not in force_single
                and not reusable[previous[0]] and len(previous)<MAX_PARAGRAPHS
                and instructions[previous[0]]==instructions[index]
                and _complete(texts[previous[-1]]) and _complete(text) and not reserve_next
                and sum(len(texts[i]) for i in previous)+len(text)<=MAX_CHARACTERS):
            blocks[-1]=(*previous,index)
        else:
            blocks.append((index,))
    return blocks


def split_narration(narration, texts):
    """Keep all PCM and pauses; split only in confirmed silence on frame edges."""
    try:
        return _split(narration, texts)
    except (ValueError,TypeError,KeyError,IndexError,wave.Error,EOFError) as exc:
        raise UnsplittableNarration('连续配音缺少可安全分段的字幕边界，改用逐段配音') from exc


def _split(narration, texts):
    if len(texts)<2 or any(not spoken(text) for text in texts):
        raise ValueError('配音段落无效')
    captions=verified_captions({'sentences':[
        {'start_time':c['start']*1000,'end_time':c['end']*1000,'text':c['text']}
        for c in narration.captions
    ]},''.join(texts))
    with wave.open(io.BytesIO(narration.audio),'rb') as source:
        duration=source.getnframes()/source.getframerate()
        if source.getsampwidth()!=2 or not 0<duration<=120:
            raise ValueError('配音采样格式或时长无效')
        expected=source.getnframes()*source.getnchannels()*source.getsampwidth()
        if len(source.readframes(source.getnframes()))!=expected:
            raise ValueError('配音采样数据被截断')
    if any(not spoken(c['text']) or c['end']>duration+1e-8 for c in captions):
        raise ValueError('字幕超出音轨')
    data=align_audio(narration.audio)
    with wave.open(io.BytesIO(data),'rb') as source:
        params=source.getparams();rate=source.getframerate();frame_samples=rate//30
        total_frames=source.getnframes();pcm=source.readframes(total_frames)
    caption_ends=[];offset=0
    for caption in captions:
        offset+=len(spoken(caption['text']));caption_ends.append(offset)
    cuts=[0];ranges=[0];offset=0
    for text in texts[:-1]:
        offset+=len(spoken(text))
        # A caption spanning both paragraphs cannot locate their phonetic boundary.
        boundary=caption_ends.index(offset)+1
        left,right=captions[boundary-1]['end'],captions[boundary]['start']
        first=math.ceil(left*30-1e-8);last=math.floor(right*30+1e-8)
        if first>last:raise ValueError('段落间没有帧对齐的字幕停顿')
        cut=((first+last)//2)*frame_samples
        if not cuts[-1]<cut<total_frames:raise ValueError('段落音轨边界无效')
        cuts.append(cut);ranges.append(boundary)
    cuts.append(total_frames);ranges.append(len(captions))
    parts=[];sample_bytes=params.nchannels*params.sampwidth
    for index, text in enumerate(texts):
        start,end=cuts[index:index+2];seconds=start/rate
        subtitle=[{**c,'start':max(0.,c['start']-seconds),'end':c['end']-seconds}
                  for c in captions[ranges[index]:ranges[index+1]]]
        if spoken(''.join(c['text'] for c in subtitle))!=spoken(text):
            raise ValueError('段落字幕映射不一致')
        stream=io.BytesIO()
        with wave.open(stream,'wb') as target:
            target.setparams(params);target.writeframes(pcm[start*sample_bytes:end*sample_bytes])
        parts.append(Narration(stream.getvalue(),subtitle))
    return parts
