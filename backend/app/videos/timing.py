"""Estimated sentence cues for absolute-time HTML."""
import math
import re
import unicodedata
TIMING_PROTOCOL="direct-html-sentence-1"

def spoken(text):
    return ''.join(c for c in text if not c.isspace() and not unicodedata.category(c).startswith('P'))


def estimated_cues(text, duration):
    if not math.isfinite(duration) or not 0 < duration <= 120 or not spoken(text):
        raise ValueError('动画预估讲稿或时长无效')
    sentences = re.findall(r'[^。！？!?]*[。！？!?]+|[^。！？!?]+$', text)
    # Keep punctuation/whitespace exactly; tiny pause slots let real pauses map
    # to holds rather than forcing all actions into one global speed ratio.
    merged = []
    for sentence in sentences:
        if not spoken(sentence) and merged:
            merged[-1] += sentence
        else:
            merged.append(sentence)
    sentences = merged
    pause = min(.25, duration / (len(sentences) * 10))
    available = duration - pause * (len(sentences) - 1)
    weights = [max(1, len(spoken(s))) for s in sentences]
    cues = []; cursor = 0.
    for sentence, weight in zip(sentences, weights):
        end = cursor + available * weight / sum(weights)
        cues.append({'start': cursor, 'end': end, 'text': sentence})
        cursor = end + pause
    cues[-1]['end'] = duration
    return cues


