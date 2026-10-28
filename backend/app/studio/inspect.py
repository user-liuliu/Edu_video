"""Per-segment checks of a studio film in headless Chromium, for the model that wrote the code.

``inspect_film`` opens ONE page (``studio_page``) and runs every requested check on it. Issue
messages are fed back to that model, so each names the segment, the film time, the element
and what is wrong, in Chinese. The JavaScript only measures; the decisions are made by the
pure helpers below (``box_issues``, ``highlight_issues``, ``state_issues``).
"""
from __future__ import annotations

import base64
import io

from app.studio.contract import Highlight, StageState, state_diff
from app.studio.render_contract import (REVIEW_SIZE, InspectRequest, InspectResult, Issue,
                                        SegmentStates, check_film, film_data)

GEOMETRY_MARK = '角色零件形状被修改'
CUE_TOLERANCE = 0.15  # s: a scripted highlight must start this close to its cue
OVERLAP_SHARE = 0.15  # of the smaller box
BOX_TOLERANCE = 0.5  # px
SAMPLES_PER_SEGMENT = 10  # equal parts: 11 points with both ends
END_EPSILON = 1e-4  # s: "the last frame" of a segment, still inside its own slot
MAX_DETERMINISM_REPORTS = 3  # per segment

# Instantiate each segment in the sandbox once: measured states, cue times of the scripted
# highlights and the recorded emphasis calls. Everything is destroyed again.
_COLLECT = r'''(specs) => specs.map((spec) => {
  const out = {id: spec.id};
  let f;
  try { f = EduFilm.instantiate(spec.id); } catch (e) { out.error = String(e && e.message || e); return out; }
  try {
    try { out.start = f.state(0); out.end = f.state(spec.duration); }
    catch (e) { out.stateError = String(e && e.message || e); }
    out.cues = spec.highlights.map((h) => {
      try { return {cue: f.cue(h.phrase, h.occurrence)}; }
      catch (e) { return {error: String(e && e.message || e)}; }
    });
    out.records = f.highlights();
  } finally { f.destroy(); }
  return out;
})'''

# Visit each (segment, film time) and measure the visible text and formula boxes in that
# segment's layer on the real stage (captions live outside the layers). Diagnostics that
# first appear while visiting a time get that time.
_SWEEP = r'''(args) => {
  const [samples, measure] = args;
  const diags = window.studioDiagnostics;
  const firstSeen = {};
  const stage = document.querySelector('.edu-stage');
  const SELECTOR = 'text, .katex, [data-edu-text]';
  function visible(el, layer) {
    for (let n = el; n && n !== layer.parentNode; n = n.parentElement) {
      const css = getComputedStyle(n);
      if (css.display === 'none' || css.visibility === 'hidden' || parseFloat(css.opacity) === 0) return false;
    }
    return true;
  }
  function snippet(el) {
    const source = el.classList && el.classList.contains('katex') && el.querySelector('.katex-html') || el;
    return (source.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 20);
  }
  function label(el) {
    const own = el.getAttribute('data-edu-id');
    if (own) return '[data-edu-id="' + own + '"]';
    const kind = el.classList && el.classList.contains('katex') ? '公式' : el.tagName.toLowerCase();
    const named = el.parentElement && el.parentElement.closest('[data-edu-id]');
    const what = kind + '「' + snippet(el) + '」';
    return named ? '[data-edu-id="' + named.getAttribute('data-edu-id') + '"] 里的 ' + what : what;
  }
  const out = [];
  for (const s of samples) {
    const before = diags.length;
    window.renderFrame(s.t);
    for (let i = before; i < diags.length; i++) {
      if (!(diags[i].message in firstSeen)) firstSeen[diags[i].message] = s.t;
    }
    if (!measure) continue;
    const layer = stage.querySelector('.edu-layer[data-segment="' + CSS.escape(s.segment) + '"]');
    if (!layer || getComputedStyle(layer).visibility === 'hidden') continue;
    const ref = stage.getBoundingClientRect();
    const els = Array.from(layer.querySelectorAll(SELECTOR)).filter((el) =>
      !el.closest('[data-edu-offstage]') && visible(el, layer));
    const boxes = [];
    els.forEach((el, i) => {
      const r = el.getBoundingClientRect();
      if (!(r.width > 0 && r.height > 0)) return;
      const inside = [];
      els.forEach((other, j) => { if (j !== i && other.contains(el)) inside.push(j); });
      boxes.push({i: i, x: r.left - ref.left, y: r.top - ref.top, w: r.width, h: r.height,
        label: label(el), inside: inside});
    });
    out.push({segment: s.segment, t: s.t, local: s.local, boxes: boxes});
  }
  return {samples: out, firstSeen: firstSeen};
}'''


def _fmt(value: float) -> str:
    return f'{value:.2f}'.rstrip('0').rstrip('.') if value % 1 else f'{value:.0f}'


def _when(segment: str, t: float, local: float) -> str:
    return f'第 {segment} 段：在 {_fmt(t)} 秒（本段 {_fmt(local)} 秒）'


# ---- pure analysis ------------------------------------------------------------------------

def box_issues(samples: list[dict], checks: set[str], width: int, height: int) -> list[Issue]:
    """``bounds`` and ``overlap`` issues from measured boxes; one issue per element (pair)
    and kind of problem, at the first time it was seen."""
    caption_top = round(height * 625 / 720)
    issues: list[Issue] = []
    seen: set[tuple] = set()
    for sample in samples:
        segment, t, local, boxes = sample['segment'], sample['t'], sample['local'], sample['boxes']
        if 'bounds' in checks:
            for b in boxes:
                right, bottom = b['x'] + b['w'], b['y'] + b['h']
                sides = [name for name, over in (('左', -b['x']), ('上', -b['y']), ('右', right - width),
                                                  ('下', bottom - height)) if over > BOX_TOLERANCE]
                where = (f'（外框 x {_fmt(b["x"])}–{_fmt(right)}，y {_fmt(b["y"])}–{_fmt(bottom)}）')
                problems = []
                if sides:
                    problems.append(('canvas', f'超出画布（{"、".join(sides)}边），请移回 {width}×{height} 的画布里'))
                if bottom > caption_top + BOX_TOLERANCE and b['y'] < height:
                    problems.append(('captions', f'压进了底部字幕区（y {caption_top} 以下是字幕区），请往上放到 y {caption_top} 以上'))
                for kind, text in problems:
                    key = ('bounds', segment, b['label'], kind)
                    if key in seen:
                        continue
                    seen.add(key)
                    issues.append(Issue(code='bounds', segment=segment, t=t, element=b['label'],
                                        message=f'{_when(segment, t, local)}，{b["label"]}{where}{text}'))
        if 'overlap' in checks:
            for i, a in enumerate(boxes):
                for b in boxes[i + 1:]:
                    if a['i'] in b['inside'] or b['i'] in a['inside']:
                        continue
                    w = min(a['x'] + a['w'], b['x'] + b['w']) - max(a['x'], b['x'])
                    h = min(a['y'] + a['h'], b['y'] + b['h']) - max(a['y'], b['y'])
                    if w <= 0 or h <= 0:
                        continue
                    share = w * h / min(a['w'] * a['h'], b['w'] * b['h'])
                    if share <= OVERLAP_SHARE:
                        continue
                    key = ('overlap', segment) + tuple(sorted((a['label'], b['label'])))
                    if key in seen:
                        continue
                    seen.add(key)
                    issues.append(Issue(
                        code='overlap', segment=segment, t=t, element=a['label'],
                        message=(f'{_when(segment, t, local)}，{a["label"]} 和 {b["label"]} 的文字重叠，'
                                 f'交叠面积是较小者的 {round(share * 100)}%（不能超过 15%），请把它们分开放')))
    return issues


def _matches(target: str, record: dict) -> bool:
    return (record.get('target') == target or record.get('target') == f'[data-edu-id="{target}"]'
            or target in (record.get('labels') or []))


def highlight_issues(segment: str, wanted: list[Highlight], cues: list[dict], records: list[dict],
                     start: float = 0.0) -> list[Issue]:
    """Every scripted highlight needs a ``motion.highlight`` on its target within
    ±CUE_TOLERANCE of ``cue(phrase, occurrence)``. ``start`` is the segment's film time."""
    issues: list[Issue] = []
    marks = [r for r in records if r.get('kind') == 'highlight']
    for h, cue in zip(wanted, cues):
        what = f'高亮"{h.phrase}"（第 {h.occurrence} 处，目标 {h.target}）'
        if 'error' in cue:
            reason = str(cue['error'])
            prefix = f'第 {segment} 段：'
            if reason.startswith(prefix):
                reason = reason[len(prefix):]
            issues.append(Issue(code='highlights', segment=segment, t=None, element=h.target,
                                message=f'{prefix}{what}的时间找不到：{reason}'))
            continue
        at = cue['cue']
        on_target = [r for r in marks if _matches(h.target, r)]
        if any(abs(r['at'] - at) <= CUE_TOLERANCE for r in on_target):
            continue
        hint = ''
        if on_target:
            hint = '；这个目标的高亮在本段 ' + '、'.join(_fmt(r['at']) for r in on_target) + ' 秒，时间没对上'
        selector = h.target if h.target[:1] in '.#[' else f'[data-edu-id="{h.target}"]'
        occurrence = f', {h.occurrence}' if h.occurrence != 1 else ''
        issues.append(Issue(
            code='highlights', segment=segment, t=start + at, element=h.target,
            message=(f'第 {segment} 段：脚本要求的{what}应在本段 {_fmt(at)} 秒（整片 {_fmt(start + at)} 秒）'
                     f'前后 {CUE_TOLERANCE:g} 秒内开始，但没有找到对应的 motion.highlight 调用{hint}。'
                     f"请写 ctx.motion.highlight('{selector}', ctx.cue('{h.phrase}'{occurrence}))")))
    return issues


def state_issues(segment: str, declared: dict, start: StageState, end: StageState, *,
                 start_t: float, end_t: float) -> list[Issue]:
    """Measured first/last-frame states against the declared ``start_state``/``end_state``.
    ``keep`` is not compared at the start: there it is what the previous segment left."""
    want_start = StageState.model_validate(declared['start_state'])
    want_end = StageState.model_validate(declared['end_state'])
    start = start.model_copy(update={'keep': want_start.keep})
    issues: list[Issue] = []
    for name, want, got, t in (('开头', want_start, start, start_t), ('结束', want_end, end, end_t)):
        diffs = state_diff(want, got)
        if diffs:
            issues.append(Issue(
                code='states', segment=segment, t=t, element=None,
                message=(f'第 {segment} 段：{name}（整片 {_fmt(t)} 秒）实测的画面状态与声明的 '
                         f'{"start_state" if name == "开头" else "end_state"} 不一致'
                         f'（前一个是声明值，后一个是实测值）：' + '；'.join(diffs))))
    return issues


# ---- browser side -------------------------------------------------------------------------

def _review_png(png: bytes) -> str:
    from PIL import Image
    image = Image.open(io.BytesIO(png)).convert('RGB').resize(REVIEW_SIZE, Image.LANCZOS)
    out = io.BytesIO()
    image.save(out, format='PNG')
    return base64.b64encode(out.getvalue()).decode()


def _same_png(first: bytes, second: bytes) -> bool:
    import numpy as np
    from PIL import Image
    from app.videos.direct_render import same_pixels

    def decode(data):
        return np.asarray(Image.open(io.BytesIO(data)).convert('RGB')).astype('int16')
    return same_pixels(decode(first), decode(second))


async def _screenshot(page, t: float) -> bytes:
    await page.evaluate('t => window.renderFrame(t)', t)
    return await page.screenshot(type='png')


def _local_points(duration: float) -> list[float]:
    # The last point is a hair before the end so it falls in this segment's own slot.
    return [min(duration * k / SAMPLES_PER_SEGMENT, duration - END_EPSILON)
            for k in range(SAMPLES_PER_SEGMENT + 1)]


async def _determinism_issues(page, segments: list[dict], starts: dict[str, float]) -> list[Issue]:
    points = []
    for s in segments:
        for share in (0, 0.5, 1):
            local = min(s['duration'] * share, s['duration'] - END_EPSILON)
            points.append((round(starts[s['id']] + local, 6), s['id'], local))
    points.sort()
    forward = {t: await _screenshot(page, t) for t, _, _ in points}
    issues: list[Issue] = []
    reported: dict[str, int] = {}
    for t, segment, local in reversed(points):
        if _same_png(forward[t], await _screenshot(page, t)):
            continue
        if reported.get(segment, 0) >= MAX_DETERMINISM_REPORTS:
            continue
        reported[segment] = reported.get(segment, 0) + 1
        issues.append(Issue(
            code='determinism', segment=segment, t=t, element=None,
            message=(f'{_when(segment, t, local)}，正向定位和倒序定位得到的画面不一样：这一帧取决于之前定位过哪些时间。'
                     '请检查 ctx.paint 是否累积了上一帧的结果、tl.call/onUpdate 等回调是否改了画面，'
                     '以及是否用了 Math.random、Date 或定时器；画面只能由时间决定')))
    return issues


async def inspect_film(req: InspectRequest) -> InspectResult:
    from app.studio.page import studio_page

    data = film_data(req.html)
    check_film(data, req.duration)
    checks = set(req.checks)
    width, height = int(data['width']), int(data['height'])
    segments = data['segments']
    starts = {item['id']: float(item['start']) for item in data['timeline'] if 'id' in item}
    wanted = {s['id']: [Highlight.model_validate(h) for h in s.get('highlights', [])] for s in segments}
    issues: list[Issue] = []
    states: dict[str, SegmentStates] = {}
    frames: list[dict] = []

    async with studio_page(req.html, width=width, height=height) as (page, errors):
        specs = [{'id': s['id'], 'duration': s['duration'],
                  'highlights': [h.model_dump() for h in wanted[s['id']]]} for s in segments]
        collected = {c['id']: c for c in await page.evaluate(_COLLECT, specs)}
        boot = await page.evaluate('window.studioDiagnostics.map(d => d.segment)')

        for s in segments:
            sid, c = s['id'], collected[s['id']]
            if 'error' in c:
                if sid not in boot:  # otherwise the boot diagnostic already says why
                    issues.append(Issue(code='runtime', segment=sid, t=None, element=None,
                                        message=f'第 {sid} 段：检查用的重新构建失败：{c["error"]}'))
                continue
            end_t = starts[sid] + s['duration']
            if 'stateError' in c:
                issues.append(Issue(code='runtime', segment=sid, t=None, element=None,
                                    message=f'第 {sid} 段：测量开头和结尾的画面状态时出错：{c["stateError"]}'))
            else:
                start_state, end_state = StageState.model_validate(c['start']), StageState.model_validate(c['end'])
                states[sid] = SegmentStates(start=start_state, end=end_state)
                if 'states' in checks:
                    issues += state_issues(sid, s, start_state, end_state, start_t=starts[sid], end_t=end_t)
            if 'highlights' in checks:
                issues += highlight_issues(sid, wanted[sid], c['cues'], c['records'], start=starts[sid])

        if 'determinism' in checks:
            issues += await _determinism_issues(page, segments, starts)

        first_seen: dict[str, float] = {}
        if checks & {'bounds', 'overlap', 'geometry'}:
            samples = []
            for s in segments:
                sid, c = s['id'], collected[s['id']]
                local = set(_local_points(s['duration']))
                local.update(r['at'] for r in c.get('records', []) if r.get('kind') == 'highlight')
                local.update(q['cue'] for q in c.get('cues', []) if 'cue' in q)
                for t in sorted(x for x in local if 0 <= x <= s['duration']):
                    t = min(t, s['duration'] - END_EPSILON)
                    samples.append({'segment': sid, 't': round(starts[sid] + t, 6), 'local': round(t, 6)})
            swept = await page.evaluate(_SWEEP, [samples, bool(checks & {'bounds', 'overlap'})])
            first_seen = swept['firstSeen']
            issues += box_issues(swept['samples'], checks, width, height)

        for t in req.frame_times:
            frames.append({'t': t, 'png_base64': _review_png(await _screenshot(page, t))})

        diagnostics = await page.evaluate('window.studioDiagnostics')
        page_errors = list(errors)

    runtime: list[Issue] = []
    for d in diagnostics:
        message = str(d.get('message', ''))
        code = 'geometry' if GEOMETRY_MARK in message else 'runtime'
        runtime.append(Issue(code=code, segment=d.get('segment'), t=first_seen.get(message),
                             element=None, message=message))
    for error in dict.fromkeys(page_errors):
        runtime.append(Issue(code='runtime', segment=None, t=None, element=None,
                             message=f'页面脚本出错：{error[:500]}'))
    return InspectResult(issues=runtime + issues, frames=frames, states=states)
