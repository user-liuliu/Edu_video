"""Word-level timing helpers. Pure Python so the renderer image can import them."""
import re
from dataclasses import dataclass

# Spoken numerals Edge may return for ASCII digits (0-10 only on purpose).
_DIGITS = {c: str(i) for i, chars in enumerate(('零〇', '一', '二两', '三', '四', '五', '六', '七', '八', '九')) for c in chars}
_SENTENCE_END = '。！？!?；;'
_CLAUSE_BREAK = '，、；：,;:'  # where an over-long sentence is preferably cut


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


def _core_length(piece):
    """Characters a caption piece shows, not counting trailing punctuation or spaces."""
    end = len(piece)
    while end and not piece[end - 1].isalnum():
        end -= 1
    return end


def _split_points(text, start, end, words, max_chars):
    """Cut positions in text[start:end] so every piece's core length is <= max_chars.

    A piece ends after the last clause mark within the limit, else at the last word end
    within the limit (never inside a word), else after the first word (a single word longer
    than the limit stays whole). Punctuation after the cut stays with the piece before it."""
    inner = [w for w in words if start <= w.char_start < end]
    def in_word(pos):
        return any(w.char_start < pos < w.char_end for w in inner)
    cuts, cursor = [], start
    while _core_length(text[cursor:end]) > max_chars:
        cut = None
        for pos in range(cursor + 1, end):
            if text[pos - 1] in _CLAUSE_BREAK and not in_word(pos) and _core_length(text[cursor:pos]) <= max_chars:
                cut = pos
        if cut is None:
            fits = [w.char_end for w in inner if w.char_end > cursor and w.char_end - cursor <= max_chars]
            cut = max(fits) if fits else min((w.char_end for w in inner if w.char_end > cursor), default=end)
        while cut < end and not text[cut].isalnum():
            cut += 1
        if cut >= end:
            break
        cuts.append(cut)
        cursor = cut
    return cuts


def sentence_captions(text, words, max_chars=24):
    """Captions for `text`: one per sentence, and a sentence whose shown length exceeds
    `max_chars` is cut into pieces (see _split_points). Each piece starts when its first word
    starts; inside a sentence it lasts until the next piece starts, the last until its last
    word ends."""
    captions = []
    for match in re.finditer(f'[^{_SENTENCE_END}]*(?:[{_SENTENCE_END}]+|$)', text):
        start, end = match.span()
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        bounds = [start, *_split_points(text, start, end, words, max_chars), end]
        pieces = []
        for left, right in zip(bounds, bounds[1:]):
            inside = [w for w in words if left <= w.char_start < right]
            piece = text[left:right].strip()
            if piece and inside:
                pieces.append({'text': piece, 'start': min(w.start for w in inside),
                               'end': max(w.end for w in inside)})
        for a, b in zip(pieces, pieces[1:]):
            a['end'] = b['start']
        captions.extend(pieces)
    return captions
