"""Bounded CJK line breaks without isolated punctuation or split teaching terms."""
CLOSING=set('。，；：、！？）】》％%.,;:!?)]}')
OPENING=set('（【《([{')
TERMS=('光合作用','二氧化碳','叶绿体','化学能','有机物','主要场所','场所','禁止','隔水加热','蓝黑色','遮光区','见光区')

def wrap_text(value,width):
    if width<4:raise ValueError('line width must be at least four')
    lines=[]
    for paragraph in value.splitlines():
        remaining=paragraph
        while len(remaining)>width:
            def allowed(cut):
                if remaining[cut] in CLOSING or remaining[cut-1] in OPENING or len(remaining)-cut==1:return False
                for term in TERMS:
                    start=remaining.find(term)
                    while start>=0:
                        if start<cut<start+len(term):return False
                        start=remaining.find(term,start+1)
                return True
            candidates=[n for n in range(width,max(1,width//2)-1,-1) if allowed(n)]
            breaks=[n for n in candidates if remaining[n-1] in '。；;！？!?']
            cut=breaks[0] if breaks else candidates[0] if candidates else width
            lines.append(remaining[:cut]);remaining=remaining[cut:]
        if remaining:lines.append(remaining)
    return lines
