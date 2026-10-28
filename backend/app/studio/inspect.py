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
# A text box is the font's whole ascent-to-descent area, much taller than the glyphs: lines
# at line-height 1.2 already touch. For overlap only, each box is cut to its core band by
# this share of its height at the top and at the bottom.
OVERLAP_CORE_INSET = 0.15
BOX_TOLERANCE = 0.5  # px
SAMPLES_PER_SEGMENT = 10  # equal parts: 11 points with both ends
END_EPSILON = 1e-4  # s: "the last frame" of a segment, still inside its own slot
MAX_DETERMINISM_REPORTS = 3  # per segment

# Instantiate one segment in the sandbox: measured states, cue times of the scripted
# highlights and the recorded emphasis calls. Always destroyed again.
_COLLECT = r'''(spec) => {
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
}'''

# Draw one film time and (when asked) measure every visible text in that segment's layer on
# the real stage: SVG <text>, KaTeX formulas, [data-edu-text], and every HTML element with a
# text node of its own (measured over that text, so a wide block is not mistaken for it).
# Each box comes twice: on screen (after the camera) and in stage coordinates before the
# camera (inside .edu-world). Captions live outside the layers. New diagnostics are returned.
_SAMPLE = r'''(s) => {
  const diags = window.studioDiagnostics;
  const before = diags.length;
  window.renderFrame(s.t);
  const fresh = diags.slice(before).map((d) => d.message);
  if (!s.measure) return {fresh: fresh, boxes: null};
  const stage = document.querySelector('.edu-stage');
  const layer = stage.querySelector('.edu-layer[data-segment="' + CSS.escape(s.segment) + '"]');
  if (!layer || getComputedStyle(layer).visibility === 'hidden') return {fresh: fresh, boxes: null};
  const world = layer.querySelector('.edu-world');
  const ref = stage.getBoundingClientRect();
  const wr = world.getBoundingClientRect();
  const kx = wr.width / world.offsetWidth, ky = wr.height / world.offsetHeight;
  const camera = Math.abs(kx - 1) > 1e-3 || Math.abs(ky - 1) > 1e-3 ||
    Math.abs(wr.left - ref.left) > 0.5 || Math.abs(wr.top - ref.top) > 0.5;
  const SPECIAL = 'text, .katex, [data-edu-text]';
  const SKIP = 'script, style, defs, title, desc, .edu-caption, .edu-subtitles';
  function ownText(el) {
    return Array.from(el.childNodes).filter((n) => n.nodeType === 3 && n.nodeValue.trim());
  }
  const candidates = [];
  layer.querySelectorAll('*').forEach((el) => {
    if (el.closest(SKIP)) return;
    const special = el.matches(SPECIAL);
    if (!special && !ownText(el).length) return;
    const outer = el.parentElement && el.parentElement.closest(SPECIAL);
    if (outer && layer.contains(outer)) return;  // measured as part of its text or formula
    candidates.push({el: el, special: special});
  });
  function visible(el) {
    for (let n = el; n && n !== layer.parentNode; n = n.parentElement) {
      const css = getComputedStyle(n);
      if (css.display === 'none' || css.visibility === 'hidden' || parseFloat(css.opacity) === 0) return false;
    }
    return true;
  }
  function rectOf(c) {
    if (c.special) return c.el.getBoundingClientRect();
    let box = null;
    ownText(c.el).forEach((node) => {
      const range = document.createRange();
      range.selectNodeContents(node);
      const r = range.getBoundingClientRect();
      if (!(r.width > 0 && r.height > 0)) return;
      if (!box) { box = {left: r.left, top: r.top, right: r.right, bottom: r.bottom}; return; }
      box.left = Math.min(box.left, r.left); box.top = Math.min(box.top, r.top);
      box.right = Math.max(box.right, r.right); box.bottom = Math.max(box.bottom, r.bottom);
    });
    return box ? {left: box.left, top: box.top, width: box.right - box.left, height: box.bottom - box.top} : null;
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
    return named && layer.contains(named) ? '[data-edu-id="' + named.getAttribute('data-edu-id') + '"] 里的 ' + what : what;
  }
  const kept = candidates.filter((c) => visible(c.el));
  const boxes = [];
  kept.forEach((c, i) => {
    const r = rectOf(c);
    if (!r || !(r.width > 0 && r.height > 0)) return;
    const inside = [];
    kept.forEach((other, j) => { if (j !== i && other.el.contains(c.el)) inside.push(j); });
    boxes.push({i: i, x: r.left - ref.left, y: r.top - ref.top, w: r.width, h: r.height,
      wx: (r.left - wr.left) / kx, wy: (r.top - wr.top) / ky, ww: r.width / kx, wh: r.height / ky,
      camera: camera, offstage: !!c.el.closest('[data-edu-offstage]'), label: label(c.el), inside: inside});
  });
  return {fresh: fresh, boxes: boxes};
}'''


def _fmt(value: float) -> str:
    return f'{value:.2f}'.rstrip('0').rstrip('.') if value % 1 else f'{value:.0f}'


def _when(segment: str, t: float, local: float) -> str:
    return f'第 {segment} 段：在 {_fmt(t)} 秒（本段 {_fmt(local)} 秒）'


# ---- pure analysis ------------------------------------------------------------------------

def _on_canvas(b: dict, width: int, height: int) -> bool:
    return b['x'] < width and b['x'] + b['w'] > 0 and b['y'] < height and b['y'] + b['h'] > 0


def _core(b: dict) -> tuple[float, float, float, float]:
    inset = b['h'] * OVERLAP_CORE_INSET
    return b['x'], b['y'] + inset, b['w'], b['h'] - 2 * inset


def _bounds_problems(b: dict, width: int, height: int, caption_top: int) -> list[tuple[str, str]]:
    """Off-canvas is judged in stage coordinates before the camera (``wx``..), so a camera
    push-in that crops text is fine; the subtitle zone after the camera (``x``..), for boxes
    still visible on the canvas."""
    problems = []
    wx, wy = b.get('wx', b['x']), b.get('wy', b['y'])
    wr, wb = wx + b.get('ww', b['w']), wy + b.get('wh', b['h'])
    sides = [] if b.get('offstage') else [
        name for name, over in (('左', -wx), ('上', -wy), ('右', wr - width), ('下', wb - height))
        if over > BOX_TOLERANCE]
    if sides:
        problems.append(('canvas', (
            f'（镜头移动前的外框 x {_fmt(wx)}–{_fmt(wr)}，y {_fmt(wy)}–{_fmt(wb)}）超出画布（{"、".join(sides)}边），'
            f'请移回 {width}×{height} 的画布里；如果是故意放在画外再移进来或移出去的文字，'
            '请给它加 data-edu-offstage')))
    right, bottom = b['x'] + b['w'], b['y'] + b['h']
    on_canvas = _on_canvas(b, width, height)
    if on_canvas and bottom > caption_top + BOX_TOLERANCE:
        camera = '镜头移动后，' if b.get('camera') else ''
        problems.append(('captions', (
            f'（画面上的外框 x {_fmt(b["x"])}–{_fmt(right)}，y {_fmt(b["y"])}–{_fmt(bottom)}）{camera}'
            f'压进了底部字幕区（y {caption_top} 以下是字幕区），'
            + (f'请调整镜头或把文字往上放，让它在画面上停在 y {caption_top} 以上' if camera
               else f'请往上放到 y {caption_top} 以上'))))
    return problems


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
                for kind, text in _bounds_problems(b, width, height, caption_top):
                    key = ('bounds', segment, b['label'], kind)
                    if key in seen:
                        continue
                    seen.add(key)
                    issues.append(Issue(code='bounds', segment=segment, t=t, element=b['label'],
                                        message=f'{_when(segment, t, local)}，{b["label"]}{text}'))
        if 'overlap' in checks:
            for i, a in enumerate(boxes):
                for b in boxes[i + 1:]:
                    if a['i'] in b['inside'] or b['i'] in a['inside']:
                        continue
                    if not (_on_canvas(a, width, height) and _on_canvas(b, width, height)):
                        continue  # parked beyond the canvas: nobody sees it
                    ax, ay, aw, ah = _core(a)
                    bx, by, bw, bh = _core(b)
                    w = min(ax + aw, bx + bw) - max(ax, bx)
                    h = min(ay + ah, by + bh) - max(ay, by)
                    if w <= 0 or h <= 0:
                        continue
                    share = w * h / min(aw * ah, bw * bh)
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


def diagnostic_issues(diagnostics: list[dict], errors: list[str],
                      first_seen: dict[str, float] | None = None) -> list[Issue]:
    """``studioDiagnostics`` entries (``geometry`` for changed character parts, else
    ``runtime``) and page errors, as issues; ``first_seen`` gives the film time of a message."""
    first_seen = first_seen or {}
    issues = []
    for d in diagnostics:
        message = str(d.get('message', ''))
        issues.append(Issue(code='geometry' if GEOMETRY_MARK in message else 'runtime',
                            segment=d.get('segment'), t=first_seen.get(message), element=None,
                            message=message))
    for error in dict.fromkeys(errors):
        issues.append(Issue(code='runtime', segment=None, t=None, element=None,
                            message=f'页面脚本出错：{str(error)[:500]}'))
    return issues


def timeout_issue(segment: str | None, phase: str | None, t: float | None, seconds: float) -> Issue:
    """The page stopped answering; ``segment``/``phase`` come from ``window.__studioBusy``."""
    if segment:
        what = '构建' if phase == 'build' else '绘制'
        where = '' if t is None else f'（整片 {_fmt(t)} 秒）'
        message = (f'第 {segment} 段：{what}超时，可能有死循环：{what}{where}超过 {seconds:g} 秒没有结束，'
                   '已被强制停止。请检查 while/for 循环的结束条件'
                   + ('，以及 ctx.paint 里的绘制函数' if what == '绘制' else ''))
    else:
        message = (f'整片超过 {seconds:g} 秒没有响应，可能有死循环，已被强制停止'
                   '（没能确定是哪一段）。请检查各段代码里 while/for 循环的结束条件')
    return Issue(code='runtime', segment=segment, t=t if segment else None, element=None, message=message)


def from_timeout(error) -> list[Issue]:
    """Issues for a ``page.StudioTimeout``: what the runtime had reported, then the timeout."""
    return (diagnostic_issues(error.diagnostics, error.errors)
            + [timeout_issue(error.segment, error.phase, error.t, error.seconds)])


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


async def _step(page, awaitable, t: float | None = None):
    """One bounded page step; a timeout says which film time was being drawn."""
    from app.studio.page import StudioTimeout, bounded
    try:
        return await bounded(page, awaitable)
    except StudioTimeout as error:
        error.t = t
        raise


async def _screenshot(page, t: float) -> bytes:
    await _step(page, page.evaluate('t => window.renderFrame(t)', t), t)
    return await _step(page, page.screenshot(type='png'), t)


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


def _samples(segment: dict, start: float, collected: dict) -> list[dict]:
    local = set(_local_points(segment['duration']))
    local.update(r['at'] for r in collected.get('records', []) if r.get('kind') == 'highlight')
    local.update(q['cue'] for q in collected.get('cues', []) if 'cue' in q)
    out = []
    for t in sorted(x for x in local if 0 <= x <= segment['duration']):
        t = min(t, segment['duration'] - END_EPSILON)
        out.append({'segment': segment['id'], 't': round(start + t, 6), 'local': round(t, 6)})
    return out


async def inspect_film(req: InspectRequest) -> InspectResult:
    """All requested checks on one page. A page that stops answering (an endless loop in a
    segment's build or painter) is stopped and reported as a ``runtime`` issue; the issues
    and frames found until then are kept."""
    from app.studio.page import StudioTimeout, film_needs_webgl, studio_page

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
    first_seen: dict[str, float] = {}
    measure = bool(checks & {'bounds', 'overlap'})
    measured: list[dict] = []

    try:
        async with studio_page(req.html, width=width, height=height,
                               webgl=film_needs_webgl(req.html)) as (page, errors):
            boot = await _step(page, page.evaluate('window.studioDiagnostics.map(d => d.segment)'))
            collected: dict[str, dict] = {}
            for s in segments:
                sid = s['id']
                spec = {'id': sid, 'duration': s['duration'],
                        'highlights': [h.model_dump() for h in wanted[sid]]}
                c = collected[sid] = await _step(page, page.evaluate(_COLLECT, spec))
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
                    start_state = StageState.model_validate(c['start'])
                    end_state = StageState.model_validate(c['end'])
                    states[sid] = SegmentStates(start=start_state, end=end_state)
                    if 'states' in checks:
                        issues += state_issues(sid, s, start_state, end_state, start_t=starts[sid], end_t=end_t)
                if 'highlights' in checks:
                    issues += highlight_issues(sid, wanted[sid], c['cues'], c['records'], start=starts[sid])

            if 'determinism' in checks:
                issues += await _determinism_issues(page, segments, starts)

            if checks & {'bounds', 'overlap', 'geometry'}:
                for s in segments:
                    for sample in _samples(s, starts[s['id']], collected[s['id']]):
                        got = await _step(page, page.evaluate(_SAMPLE, {**sample, 'measure': measure}), sample['t'])
                        for message in got['fresh']:
                            first_seen.setdefault(message, sample['t'])
                        if got['boxes'] is not None:
                            measured.append({**sample, 'boxes': got['boxes']})
                issues += box_issues(measured, checks, width, height)
                measured = []  # counted

            for t in req.frame_times:
                frames.append({'t': t, 'png_base64': _review_png(await _screenshot(page, t))})

            diagnostics = await _step(page, page.evaluate('window.studioDiagnostics'))
            runtime = diagnostic_issues(diagnostics, list(errors), first_seen)
    except StudioTimeout as error:
        runtime = [i.model_copy(update={'t': first_seen.get(i.message, i.t)}) for i in from_timeout(error)]
        issues += box_issues(measured, checks, width, height)  # what the sweep measured before it
    return InspectResult(issues=runtime + issues, frames=frames, states=states)
