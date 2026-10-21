import math
import re


def split_narration(text: str, limit: int = 180) -> list[str]:
    text = text.strip()
    if not text:
        raise ValueError('讲稿不能为空')
    sentences = re.findall(r'[^。！？!?]+[。！？!?]*', text)
    result = []
    for sentence in sentences:
        while len(sentence) > limit:
            cut = max(sentence.rfind('，', 0, limit), sentence.rfind('；', 0, limit))
            cut = cut + 1 if cut > limit // 3 else limit
            result.append(sentence[:cut]); sentence = sentence[cut:]
        if sentence:
            result.append(sentence)
    return result


SEGMENTATION_VERSION = 2
NARRATION_CHUNK_LIMIT = 300


def narration_chunks(text: str, limit: int = NARRATION_CHUNK_LIMIT) -> list[str]:
    """Keep connected sentences in one continuous narration and action window."""
    if limit < 1:
        raise ValueError('讲稿片段长度无效')
    if not text.strip():
        raise ValueError('讲稿不能为空')
    if len(text) <= limit:
        return [text]
    # Keep every character, including paragraph breaks; avoid orphaned closing lines.
    sentences = re.findall(r'[^。！？!?]*[。！？!?]+|[^。！？!?]+$', text)
    units = [s[i:i+limit] for s in sentences for i in range(0,len(s),limit)]
    chunks=[]
    grouped=[]
    for sentence in units:
        if chunks and len(chunks[-1])+len(sentence)<=limit:
            chunks[-1]+=sentence
            grouped[-1].append(sentence)
        else:
            chunks.append(sentence)
            grouped.append([sentence])
    if len(chunks)>1 and len(chunks[-1])<limit/3:
        while len(grouped[-2])>1 and len(chunks[-1])<limit/3:
            last=grouped[-2][-1]
            if len(last)+len(chunks[-1])>limit: break
            grouped[-2].pop();chunks[-2]=chunks[-2][:-len(last)]
            chunks[-1]=last+chunks[-1]
        if len(chunks[-1])<limit/3:
            combined=chunks[-2]+chunks[-1]
            cut=(len(combined)+1)//2
            chunks[-2:]=[combined[:cut],combined[cut:]]
    return chunks


def caption_timeline(sentences: list[str], durations: list[float]) -> list[dict]:
    if not sentences or len(sentences) != len(durations):
        raise ValueError('字幕与配音数量不一致')
    current = 0.0
    entries = []
    for text, duration in zip(sentences, durations):
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError('配音时长无效')
        end = round(current + duration, 6)
        entries.append({'start': current, 'end': end, 'text': text})
        current = end
    return entries


def locate_segment(entries: list[dict], time: float) -> dict:
    if not math.isfinite(time) or not entries or time < 0 or time > entries[-1]['end']:
        raise ValueError('播放时间超出当前视频版本')
    for entry in entries:
        if entry['start'] <= time < entry['end']:
            return entry
    if time == entries[-1]['end']:
        return entries[-1]
    raise ValueError('播放时间不在片段内')
