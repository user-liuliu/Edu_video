"""Static checks on segment code. Pure Python so the renderer image can import it.

Every frame must be a pure function of time, so segment code may not read clocks, use
randomness, touch the network or reach into global browser state. Patterns tolerate
whitespace between tokens (``Math . random (``). Matches inside string literals are
reported too; that is deliberate, the checker is not a JS parser. Optional chaining
(``Math?.random``) counts as member access.

The lint is the first line only: code can still reach a clock or ``Math.random`` through an
alias it cannot see (``const M = Math; M['ran' + 'dom']()``), so the runtime also replaces
them with fixed, seeded stand-ins before any film code runs (``edu_motion.js``).
"""
from __future__ import annotations

import re

# Not preceded by an identifier character or a dot, so `ctx.top.y` and `stop.x` pass.
_BARE = r'(?<![\w$.])'
# Member access, plain or optional (`a.b`, `a?.b`); `?.5` is a conditional and a number.
_DOT = r'\s*(?:\?\.(?!\d)|\.)\s*'
# A call, plain or optional (`f(`, `f?.(`).
_CALL = r'\s*(?:\?\.\s*)?\('

BANNED_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (label, re.compile(pattern)) for label, pattern in (
        ('setTimeout', rf'{_BARE}setTimeout\b'),
        ('setInterval', rf'{_BARE}setInterval\b'),
        ('requestAnimationFrame', rf'{_BARE}requestAnimationFrame\b'),
        ('Date.now', rf'{_BARE}Date{_DOT}now\b'),
        ('new Date', rf'{_BARE}new\s+Date\b'),
        ('Date(', rf'{_BARE}Date{_CALL}'),
        ('performance.now', rf'{_BARE}performance{_DOT}now\b'),
        ('Math.random', rf'{_BARE}Math{_DOT}random\b'),
        ('fetch', rf'{_BARE}fetch\b'),
        ('XMLHttpRequest', rf'{_BARE}XMLHttpRequest\b'),
        ('WebSocket', rf'{_BARE}WebSocket\b'),
        ('EventSource', rf'{_BARE}EventSource\b'),
        ('import(', rf'{_BARE}import\s*\('),
        ('eval', rf'{_BARE}eval\b'),
        ('new Function', rf'{_BARE}new\s+Function\b'),
        ('Function(', rf'{_BARE}Function{_CALL}'),
        ('localStorage', rf'{_BARE}localStorage\b'),
        ('sessionStorage', rf'{_BARE}sessionStorage\b'),
        ('indexedDB', rf'{_BARE}indexedDB\b'),
        ('window.', rf'{_BARE}window{_DOT}'),
        ('self.', rf'{_BARE}self{_DOT}'),
        ('globalThis.', rf'{_BARE}globalThis{_DOT}'),
        ('parent.', rf'{_BARE}parent{_DOT}'),
        ('top.', rf'{_BARE}top{_DOT}'),
        ('document.querySelector', rf'{_BARE}document{_DOT}querySelector'),
        ('document.body', rf'{_BARE}document{_DOT}body\b'),
        ('document.write', rf'{_BARE}document{_DOT}write'),
        ('gsap.ticker', rf'{_BARE}gsap{_DOT}ticker\b'),
        ('gsap.globalTimeline', rf'{_BARE}gsap{_DOT}globalTimeline\b'),
    )
)


def lint_segment(code: str) -> list[str]:
    """One message per banned construct that appears at least once in `code`."""
    return [f'{label} 不允许使用' for label, pattern in BANNED_PATTERNS if pattern.search(code)]
