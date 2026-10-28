"""Word-level timing helpers. Pure Python so the renderer image can import them."""
import re
from dataclasses import dataclass

# Spoken numerals Edge may return for ASCII digits (0-10 only on purpose).
_DIGITS = {c: str(i) for i, chars in enumerate(('零〇', '一', '二两', '三', '四', '五', '六', '七', '八', '九')) for c in chars}
_SENTENCE_END = '。！？!?；;'


@dataclass(frozen=True)
class Word:
    text: str
    start: float
    end: float
    char_start: int
    char_end: int


def _canon(ch):
    return _DIGITS.get(ch, ch.lower())


def _match(text, pos, spoken):
    """Match `spoken` at the first spoken character at/after `pos`, skipping
    punctuation and whitespace on both sides. Returns (start, end) or None."""
    i, first, last = pos, None, None
    for ch in spoken:
        if not ch.isalnum():
            continue
        while i < len(text) and not text[i].isalnum():
            i += 1
        if i >= len(text) or _canon(text[i]) != _canon(ch):
            return None
        first = i if first is None else first
        i += 1
        last = i
    return None if first is None else (first, last)


def align_words(text, events):
    words, cursor = [], 0
    for event in events:
        try:
            start = float(event['offset']) / 10000000
            end = start + float(event['duration']) / 10000000
            spoken = event['text']
            if not 0 <= start <= end or end - start > 1e6:
                raise ValueError
        except (KeyError, TypeError, ValueError):
            raise ValueError('配音逐词时间戳无效') from None
        if not any(ch.isalnum() for ch in spoken):
            continue
        span = _match(text, cursor, spoken)
        if span is None:
            raise ValueError(f'配音逐词时间与旁白对不上：{spoken}')
        words.append(Word(spoken, start, end, *span))
        cursor = span[1]
    return words


def cue(words, text, phrase, occurrence=1):
    """Start and end seconds of the words covering the n-th occurrence of `phrase`."""
    missing = ValueError(f'高亮词"{phrase}"在旁白中找不到第 {occurrence} 处')
    if not phrase or occurrence < 1:
        raise missing
    index = -1
    for _ in range(occurrence):
        index = text.find(phrase, index + 1)
        if index < 0:
            raise missing
    end = index + len(phrase)
    hit = [w for w in words if w.char_start < end and w.char_end > index]
    if not hit:
        raise missing
    return min(w.start for w in hit), max(w.end for w in hit)


def sentence_captions(text, words):
    captions = []
    for match in re.finditer(f'[^{_SENTENCE_END}]*(?:[{_SENTENCE_END}]+|$)', text):
        start, end = match.span()
        sentence = text[start:end].strip()
        inside = [w for w in words if start <= w.char_start < end]
        if sentence and inside:
            captions.append({'text': sentence, 'start': min(w.start for w in inside),
                             'end': max(w.end for w in inside)})
    return captions
