"""Static checks on segment code. Pure Python so the renderer image can import it.

Every frame must be a pure function of time, so segment code may not read clocks, use
randomness, touch the network or reach into global browser state. Patterns tolerate
whitespace between tokens (``Math . random (``). Matches inside string literals are
reported too; that is deliberate, the checker is not a JS parser.
"""
from __future__ import annotations

import re

# Not preceded by an identifier character or a dot, so `ctx.top.y` and `stop.x` pass.
_BARE = r'(?<![\w$.])'

BANNED_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (label, re.compile(pattern)) for label, pattern in (
        ('setTimeout', rf'{_BARE}setTimeout\b'),
        ('setInterval', rf'{_BARE}setInterval\b'),
        ('requestAnimationFrame', rf'{_BARE}requestAnimationFrame\b'),
        ('Date.now', rf'{_BARE}Date\s*\.\s*now\b'),
        ('new Date', rf'{_BARE}new\s+Date\b'),
        ('performance.now', rf'{_BARE}performance\s*\.\s*now\b'),
        ('Math.random', rf'{_BARE}Math\s*\.\s*random\b'),
        ('fetch', rf'{_BARE}fetch\b'),
        ('XMLHttpRequest', rf'{_BARE}XMLHttpRequest\b'),
        ('WebSocket', rf'{_BARE}WebSocket\b'),
        ('EventSource', rf'{_BARE}EventSource\b'),
        ('import(', rf'{_BARE}import\s*\('),
        ('eval', rf'{_BARE}eval\b'),
        ('new Function', rf'{_BARE}new\s+Function\b'),
        ('localStorage', rf'{_BARE}localStorage\b'),
        ('sessionStorage', rf'{_BARE}sessionStorage\b'),
        ('indexedDB', rf'{_BARE}indexedDB\b'),
        ('window.', rf'{_BARE}window\s*\.'),
        ('parent.', rf'{_BARE}parent\s*\.'),
        ('top.', rf'{_BARE}top\s*\.'),
        ('document.querySelector', rf'{_BARE}document\s*\.\s*querySelector'),
        ('document.body', rf'{_BARE}document\s*\.\s*body\b'),
        ('gsap.ticker', rf'{_BARE}gsap\s*\.\s*ticker\b'),
        ('gsap.globalTimeline', rf'{_BARE}gsap\s*\.\s*globalTimeline\b'),
    )
)


def lint_segment(code: str) -> list[str]:
    """One message per banned construct that appears at least once in `code`."""
    return [f'{label} 不允许使用' for label, pattern in BANNED_PATTERNS if pattern.search(code)]
