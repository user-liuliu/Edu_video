/* EduFilm: plays the film's segments, the seams between them and the captions as a pure
 * function of time. Every renderFrame(t) seeks each segment's own paused timeline to its
 * local time clamp(t - start, 0, duration) with events suppressed, so a layer held across a
 * seam is at its last (outgoing) or first (incoming) frame however t was reached; then every
 * visible layer is painted (painters and emphasis composition), and a transition seam lays
 * the two layer containers out with EduStudio.transitions[name](outgoing, incoming, p). */
(function () {
  'use strict';
  var diag = EduStudio._diag;
  var film = null;
  var booted = false;
  var stage = null;
  var sandbox = null;
  var captionEl = null;
  var layers = [];  // [{id, start, duration, instance, failed}] in film order
  var slots = [];   // timeline order: {start, end, layer} or {start, end, seam, kind, transition, from, to}

  var resolveReady, rejectReady;
  window.studioReady = new Promise(function (resolve, reject) { resolveReady = resolve; rejectReady = reject; });
  window.studioReady.catch(function () {});  // reported through studioDiagnostics too

  function readFilm() {
    var el = document.getElementById('edu-studio-film');
    if (!el) throw new Error('页面里缺少 #edu-studio-film');
    return JSON.parse(el.textContent);
  }

  function box(className, css) {
    var el = document.createElement('div');
    el.className = className;
    el.style.cssText = css;
    document.body.appendChild(el);
    return el;
  }

  // Text fonts shipped in fonts.css, and KaTeX's faces (whole files, no unicode-range).
  var TEXT_FAMILIES = ['Noto Sans SC', 'LXGW WenKai'];
  var KATEX_PREFIX = 'KaTeX_';

  // Before any segment is built: load every weight/style of the shipped text fonts for all
  // characters the film's inline scripts contain (segment code, character code, narration)
  // plus printable ASCII, and every KaTeX face (always: formulas may be drawn by runtime
  // helpers, so no script text tells whether they are used), so build-time measurements
  // already use the real metrics.
  function preloadFonts() {
    var sample = ' ';
    for (var c = 33; c < 127; c++) sample += String.fromCharCode(c);
    var seen = new Set(sample);
    Array.prototype.forEach.call(document.querySelectorAll('script:not([src])'), function (script) {
      Array.from(script.textContent).forEach(function (ch) {
        if (ch.trim() && !seen.has(ch)) { seen.add(ch); sample += ch; }
      });
    });
    var keys = new Set();
    document.fonts.forEach(function (face) {
      var family = face.family.replace(/^["']|["']$/g, '');
      if (TEXT_FAMILIES.indexOf(family) >= 0 || family.indexOf(KATEX_PREFIX) === 0) {
        keys.add(face.style + ' ' + face.weight + ' 16px "' + family + '"');
      }
    });
    var loads = [];
    keys.forEach(function (key) { loads.push(document.fonts.load(key, sample)); });
    return Promise.all(loads).then(function () { return document.fonts.ready; });
  }

  // After building: also request whatever font the stage text actually uses (e.g. a family
  // from style_css), with the text it shows, so the right unicode-range subsets are loaded.
  function loadStageFonts() {
    var wanted = new Map();
    var walker = document.createTreeWalker(stage, NodeFilter.SHOW_TEXT);
    for (var node = walker.nextNode(); node; node = walker.nextNode()) {
      var text = node.nodeValue.trim();
      if (!text || !node.parentElement) continue;
      var css = getComputedStyle(node.parentElement);
      var key = css.fontStyle + ' ' + css.fontWeight + ' 16px ' + css.fontFamily;
      wanted.set(key, (wanted.get(key) || '') + text);
    }
    var loads = [];
    wanted.forEach(function (text, key) { loads.push(document.fonts.load(key, text)); });
    return Promise.all(loads).then(function () { return document.fonts.ready; });
  }

  // ---- transitions ----------------------------------------------------------------------
  // transitions[name](outgoing, incoming, p): outgoing/incoming are the two layer containers
  // (<section class="edu-layer">, outside each segment's camera), p goes 0..1 across the seam.
  // Each sets only opacity, transform, transform-origin and clip-path on the containers (the
  // runtime clears those before every frame), from p alone: same p, same picture. At p = 0
  // the picture is the outgoing layer's last frame, at p = 1 the incoming layer's first.
  function ease(p) { return p * p * (3 - 2 * p); }
  function px(value) { return (Math.round(value * 1000) / 1000) + 'px'; }
  var touched = new Map();  // element -> {translate, scale} inline values before a match move

  var transitions = {
    push: function (outgoing, incoming, p) {
      var w = outgoing.offsetWidth, e = ease(p);
      outgoing.style.transform = 'translateX(' + px(-w * e) + ')';
      incoming.style.transform = 'translateX(' + px(w * (1 - e)) + ')';
    },
    wipe: function (outgoing, incoming, p) {
      // The incoming layer is revealed from the left; the two clips tile the frame exactly.
      var edge = Math.round(ease(p) * 100000) / 1000;
      outgoing.style.clipPath = 'inset(0 0 0 ' + edge + '%)';
      incoming.style.clipPath = 'inset(0 ' + (100 - edge) + '% 0 0)';
    },
    zoom: function (outgoing, incoming, p) {
      var e = ease(p);
      outgoing.style.transform = 'scale(' + (1 + 1.5 * e) + ')';
      outgoing.style.opacity = String(1 - e);
      incoming.style.transform = 'scale(' + (0.6 + 0.4 * e) + ')';
      incoming.style.opacity = String(e);
    },
    fade: function (outgoing, incoming, p) {
      var e = ease(p);
      outgoing.style.opacity = String(1 - e);
      incoming.style.opacity = String(e);
    },
    // Elements with the same data-edu-match value in both layers move and scale from where
    // the outgoing layer leaves them to where the incoming layer has them; everything else
    // cuts at p = 0.5 (each matched element shows its outgoing look before, incoming after).
    match: function (outgoing, incoming, p) {
      var cut = p >= 0.5;
      outgoing.style.opacity = cut ? '0' : '1';
      incoming.style.opacity = cut ? '1' : '0';
      var e = ease(p);
      if (e <= 0 || e >= 1) return;
      matchPairs(outgoing, incoming).forEach(function (pair) {
        var a = pair[0], b = pair[1];
        var cx = a.cx + (b.cx - a.cx) * e, cy = a.cy + (b.cy - a.cy) * e;
        var w = a.w + (b.w - a.w) * e, h = a.h + (b.h - a.h) * e;
        moveTo(cut ? b : a, cx, cy, w, h);
      });
    }
  };

  // Matched pairs per layer pair, measured once at the held frames (both layers are seeked
  // to them and carry no container style when this first runs), so later frames are pure.
  var matchCache = new Map();
  function matchPairs(outgoing, incoming) {
    var key = outgoing.getAttribute('data-segment') + '>' + incoming.getAttribute('data-segment');
    if (matchCache.has(key)) return matchCache.get(key);
    var pairs = [];
    var later = {};
    Array.prototype.forEach.call(incoming.querySelectorAll('[data-edu-match]'), function (el) {
      var name = el.getAttribute('data-edu-match');
      if (!(name in later)) later[name] = el;
    });
    var used = {};
    Array.prototype.forEach.call(outgoing.querySelectorAll('[data-edu-match]'), function (el) {
      var name = el.getAttribute('data-edu-match');
      if (used[name] || !later[name]) return;
      used[name] = true;
      var a = profile(el), b = profile(later[name]);
      if (a && b) pairs.push([a, b]);
    });
    matchCache.set(key, pairs);
    return pairs;
  }

  function rectOf(el) {
    var r = el.getBoundingClientRect();
    return {cx: r.left + r.width / 2, cy: r.top + r.height / 2, w: r.width, h: r.height};
  }
  function setMove(el, translate, scale) {
    if (!touched.has(el)) touched.set(el, {translate: el.style.translate, scale: el.style.scale});
    el.style.translate = translate;
    el.style.scale = scale;
  }
  // How the element's screen box answers to CSS `scale` and `translate` (both act in its own
  // parent's coordinates, under whatever camera and character transforms are above it).
  function profile(el) {
    setMove(el, '0px 0px', '1');
    var base = rectOf(el);
    if (!(base.w > 0 || base.h > 0)) { restoreMoves(); return null; }
    setMove(el, '0px 0px', '2');
    var scaled = rectOf(el);
    setMove(el, '100px 0px', '1');
    var ux = rectOf(el);
    setMove(el, '0px 100px', '1');
    var uy = rectOf(el);
    restoreMoves();
    var m = [(ux.cx - base.cx) / 100, (uy.cx - base.cx) / 100, (ux.cy - base.cy) / 100, (uy.cy - base.cy) / 100];
    var det = m[0] * m[3] - m[1] * m[2];
    if (!(Math.abs(det) > 1e-9)) return null;
    return {el: el, cx: base.cx, cy: base.cy, w: base.w, h: base.h,
      // centre shift per unit of extra scale, and the inverse of translate -> screen shift
      sx: scaled.cx - base.cx, sy: scaled.cy - base.cy,
      inv: [m[3] / det, -m[1] / det, -m[2] / det, m[0] / det]};
  }
  function moveTo(p, cx, cy, w, h) {
    var s = p.w > 0 && p.h > 0 ? Math.sqrt((w * h) / (p.w * p.h)) : p.w > 0 ? w / p.w : h / p.h;
    s = Math.min(Math.max(s, 0.01), 100);
    var dx = cx - (p.cx + p.sx * (s - 1)), dy = cy - (p.cy + p.sy * (s - 1));
    var tx = p.inv[0] * dx + p.inv[1] * dy, ty = p.inv[2] * dx + p.inv[3] * dy;
    setMove(p.el, px(tx) + ' ' + px(ty), String(Math.round(s * 100000) / 100000));
  }
  function restoreMoves() {
    touched.forEach(function (saved, el) {
      el.style.translate = saved.translate;
      el.style.scale = saved.scale;
    });
    touched.clear();
  }

  // ---- frames -----------------------------------------------------------------------------
  function slotAt(t) {
    var found = slots[0];
    slots.forEach(function (slot) { if (slot.start <= t) found = slot; });
    return found;
  }

  function clearLayer(item) {
    var s = item.instance.layer.style;
    s.visibility = 'hidden';
    s.opacity = '0';
    s.transform = '';
    s.transformOrigin = '';
    s.clipPath = '';
    s.zIndex = '';
  }

  function paintLayer(item) {
    if (item.failed) return false;
    try {
      item.instance.paint();
    } catch (error) {
      isolate(item, '第 ' + item.id + ' 段：绘制失败：' + (error && error.message || error));
      return false;
    }
    return true;
  }

  function show(item) {
    item.instance.layer.style.visibility = 'visible';
    item.instance.layer.style.opacity = '1';
  }

  function renderFrame(t) {
    if (!booted) throw new Error('影片还没有启动');
    if (typeof t !== 'number' || !isFinite(t)) throw new Error('renderFrame 的时间必须是有限数字');
    t = Math.min(Math.max(t, 0), film.duration);
    restoreMoves();
    // Every segment to its own clamped local time, events suppressed: callbacks never drive
    // the picture, and the held frame of a layer next to a seam never depends on history.
    layers.forEach(function (item) {
      clearLayer(item);
      item.instance.tl.seek(Math.min(Math.max(t - item.start, 0), item.duration), true);
    });
    var slot = slotAt(t);
    if (slot.layer) {
      if (paintLayer(slot.layer)) show(slot.layer);
    } else if (slot.kind === 'continue') {
      if (paintLayer(slot.from)) show(slot.from);  // the next segment starts from this frame
    } else {
      var p = slot.end > slot.start ? (t - slot.start) / (slot.end - slot.start) : 1;
      var from = paintLayer(slot.from), to = paintLayer(slot.to);
      if (from) show(slot.from);
      if (to) { show(slot.to); slot.to.instance.layer.style.zIndex = '1'; }
      var fn = transitions[slot.transition];
      try {
        if (typeof fn !== 'function') throw new Error('没有这种转场：' + slot.transition);
        fn(slot.from.instance.layer, slot.to.instance.layer, p);
      } catch (error) {
        diag('接缝 ' + slot.seam + ' 转场失败：' + (error && error.message || error), null);
        restoreMoves();
        clearLayer(slot.from);
        clearLayer(slot.to);
        var cut = p < 0.5 ? slot.from : slot.to;
        if (!cut.failed) show(cut);
      }
      // A failed layer stays empty whatever the transition set on its container.
      [slot.from, slot.to].forEach(function (item) { if (item.failed) clearLayer(item); });
    }
    layers.forEach(function (item) { item.instance.checkGeometry(); });
    drawCaption(t);
  }

  // Captions: the sentence whose [start, end) contains t, centred in the subtitle zone.
  function drawCaption(t) {
    var text = '';
    (film.captions || []).forEach(function (c) { if (c.start <= t && t < c.end) text = c.text; });
    if (captionEl.textContent !== text) captionEl.textContent = text;
    captionEl.style.display = text ? '' : 'none';
  }

  // A segment that failed draws nothing for the rest of the film.
  function isolate(item, message) {
    item.failed = true;
    item.instance.layer.style.visibility = 'hidden';
    item.instance.layer.style.opacity = '0';
    diag(message, item.id);
  }

  function fontProblem(error) {
    diag('字体加载失败：' + (error && error.message || error), null);
  }

  // The subtitle zone: the bottom 95/720 of the canvas, above every layer.
  function captionBox() {
    var zone = document.createElement('div');
    zone.className = 'edu-subtitles';
    var top = Math.round(film.height * 625 / 720);
    zone.style.cssText = 'position:absolute;left:0;top:' + top + 'px;width:100%;height:' + (film.height - top) +
      'px;display:flex;align-items:center;justify-content:center;z-index:100;pointer-events:none';
    captionEl = document.createElement('span');
    captionEl.className = 'edu-caption';
    captionEl.style.cssText = 'display:none;max-width:90%;box-sizing:border-box;padding:4px 18px;' +
      'border-radius:8px;background:rgba(0, 0, 0, 0.55);color:#ffffff;text-align:center;' +
      'font-family:"Noto Sans SC", sans-serif;font-weight:400;font-size:30px;line-height:1.35';
    zone.appendChild(captionEl);
    stage.appendChild(zone);
  }

  function build() {
    var size = {width: film.width, height: film.height};
    stage = box('edu-stage', 'position:relative;width:' + film.width + 'px;height:' + film.height + 'px;overflow:hidden');
    if (!getComputedStyle(stage).backgroundColor || getComputedStyle(stage).backgroundColor === 'rgba(0, 0, 0, 0)') {
      stage.style.backgroundColor = '#ffffff';
    }
    sandbox = box('edu-sandbox', 'position:absolute;left:0;top:0;width:' + film.width + 'px;height:' + film.height + 'px;overflow:hidden;opacity:0;visibility:hidden;pointer-events:none;z-index:-1');
    var byId = {};
    film.segments.forEach(function (meta) {
      var entry = film.timeline.filter(function (item) { return item.id === meta.id; })[0];
      if (!entry) throw new Error('时间线里没有第 ' + meta.id + ' 段');
      var instance;
      try {
        instance = EduStudio._createSegment(meta, stage, size);
      } catch (error) {
        var message = String(error && error.message || error);
        var where = '第 ' + meta.id + ' 段：';
        diag(message.indexOf(where) === 0 ? message : where + message, meta.id);
        instance = emptySegment(meta);
      }
      var item = {id: meta.id, start: entry.start, duration: meta.duration, instance: instance,
        failed: !!instance.failed};
      layers.push(item);
      byId[meta.id] = item;
    });
    film.timeline.forEach(function (entry) {
      if (entry.id !== undefined) {
        slots.push({start: entry.start, end: entry.end, layer: byId[entry.id]});
        return;
      }
      var from = layers[entry.seam], to = layers[entry.seam + 1];
      if (!from || !to) throw new Error('接缝 ' + entry.seam + ' 两边没有段');
      slots.push({start: entry.start, end: entry.end, seam: entry.seam, kind: entry.kind,
        transition: entry.transition, from: from, to: to});
    });
    captionBox();
    booted = true;
    renderFrame(0);
    void stage.offsetHeight;
    return loadStageFonts().catch(fontProblem);
  }

  function boot() {
    try {
      film = readFilm();
    } catch (error) {
      diag('影片启动失败：' + (error && error.message || error), null);
      rejectReady(error);
      return;
    }
    preloadFonts().catch(fontProblem).then(build).then(function () {
      renderFrame(0);
      resolveReady(true);
    }, function (error) {
      diag('影片启动失败：' + (error && error.message || error), null);
      rejectReady(error);
    });
  }

  function emptySegment(meta) {
    var layer = document.createElement('section');
    layer.className = 'edu-layer';
    layer.setAttribute('data-segment', meta.id);
    layer.style.cssText = 'position:absolute;left:0;top:0;width:100%;height:100%';
    stage.appendChild(layer);
    var tl = gsap.timeline({paused: true});
    tl.set({}, {}, meta.duration);
    return {id: meta.id, layer: layer, tl: tl, failed: true, paint: function () {},
      checkGeometry: function () {}};
  }

  // Checks only: a fresh, isolated copy of one segment, built in an invisible sandbox.
  function instantiate(id) {
    if (!booted) throw new Error('影片还没有启动');
    var meta = film.segments.filter(function (s) { return s.id === id; })[0];
    if (!meta) throw new Error('没有这一段：' + id);
    return EduStudio._createSegment(meta, sandbox, {width: film.width, height: film.height}).api;
  }

  EduStudio.transitions = transitions;
  window.renderFrame = renderFrame;
  window.EduFilm = {boot: boot, instantiate: instantiate};
})();
