/* EduStudio: deterministic motion runtime for studio segments.
 * Every frame is a pure function of time. Timelines are paused and only move by seek;
 * the GSAP ticker never drives playback. Interface reference: API.md next to this file. */
(function () {
  'use strict';
  if (typeof gsap === 'undefined') throw new Error('edu_motion.js 需要先加载 gsap');
  var NS = 'http://www.w3.org/2000/svg';
  var SHAPE_ATTRS = ['d', 'points', 'x', 'y', 'width', 'height', 'cx', 'cy', 'r', 'rx', 'ry',
    'x1', 'y1', 'x2', 'y2', 'transform'];

  // Determinism: nothing advances on its own.
  ['DrawSVGPlugin', 'MorphSVGPlugin', 'MotionPathPlugin', 'SplitText'].forEach(function (name) {
    if (window[name]) gsap.registerPlugin(window[name]);
  });
  gsap.config({autoSleep: 0, force3D: false, nullTargetWarn: false});
  gsap.defaults({overwrite: false, lazy: false});
  gsap.globalTimeline.pause();
  gsap.ticker.sleep();
  // With the global timeline paused GSAP would defer gsap.set() forever; keep its usual
  // "apply now" meaning.
  var gsapSet = gsap.set.bind(gsap);
  gsap.set = function (targets, vars) {
    return gsapSet(targets, Object.assign({immediateRender: true}, vars));
  };

  var diagnostics = window.studioDiagnostics = window.studioDiagnostics || [];
  // Each entry is {segment: id or null, message}; the message already names the segment.
  function diag(message, segment) {
    if (diagnostics.some(function (d) { return d.message === message; })) return;
    diagnostics.push({segment: segment === undefined ? null : segment, message: message});
  }

  var segments = new Map();
  var characters = new Map();

  function defineSegment(id, build) {
    if (typeof id !== 'string' || typeof build !== 'function') throw new Error('defineSegment(id, build) 参数不对');
    if (segments.has(id)) throw new Error('段 id 重复：' + id);
    segments.set(id, build);
  }

  function defineCharacter(name, factory) {
    if (typeof name !== 'string' || !name || typeof factory !== 'function') {
      throw new Error('defineCharacter(name, factory) 参数不对');
    }
    if (characters.has(name)) throw new Error('角色重复定义：' + name);
    characters.set(name, factory);
  }

  // ---- small pure helpers -------------------------------------------------------------
  function hash32(text, seed, prime) {
    var h = seed >>> 0;
    for (var i = 0; i < text.length; i++) h = Math.imul(h ^ text.charCodeAt(i), prime);
    return h >>> 0;
  }
  function hashString(text) {
    var a = hash32(text, 0x811c9dc5, 16777619).toString(16);
    var b = hash32(text, 0x9e3779b9, 2246822519).toString(16);
    return ('00000000' + a).slice(-8) + ('00000000' + b).slice(-8);
  }
  function mulberry32(seed) {
    var a = seed >>> 0;
    return function () {
      a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function round(value) {
    return (Math.round(value * 10000) / 10000) || 0;
  }
  function matrixOf(el) {
    if (el instanceof SVGElement) {
      var m = new DOMMatrix();
      var list = el.transform && el.transform.baseVal;
      if (list) {
        for (var i = 0; i < list.numberOfItems; i++) {
          var t = list.getItem(i).matrix;
          m = m.multiply(new DOMMatrix([t.a, t.b, t.c, t.d, t.e, t.f]));
        }
      }
      return m;
    }
    var css = getComputedStyle(el).transform;
    return css && css !== 'none' ? new DOMMatrix(css) : new DOMMatrix();
  }
  // True when the part's own transform is a pure rotation about its pivot (px, py):
  // matrix(cos, sin, -sin, cos, px - px*cos + py*sin, py - px*sin - py*cos).
  var LINEAR_EPS = 1e-3, OFFSET_EPS = 0.02;  // GSAP rounds the written matrix
  function rotatesAboutPivot(part) {
    var m = matrixOf(part.el), px = part.pivot[0], py = part.pivot[1];
    if (Math.abs(m.a - m.d) > LINEAR_EPS || Math.abs(m.b + m.c) > LINEAR_EPS) return false;
    if (Math.abs(m.a * m.d - m.b * m.c - 1) > LINEAR_EPS) return false;
    return Math.abs(m.e - (px - px * m.a + py * m.b)) <= OFFSET_EPS &&
      Math.abs(m.f - (py - px * m.b - py * m.a)) <= OFFSET_EPS;
  }
  function svgEl(tag, attrs) {
    var el = document.createElementNS(NS, tag);
    for (var k in attrs) el.setAttribute(k, attrs[k]);
    return el;
  }
  function htmlEl(className, css) {
    var el = document.createElement('div');
    el.className = className;
    el.style.cssText = css;
    return el;
  }

  // ---- effects (ctx.motion) -----------------------------------------------------------
  // Every effect only adds tweens/sets to ctx.tl, or a ctx.paint painter that redraws from
  // tweened plain objects and the live DOM. Nothing visible is driven by callbacks.
  var INK = '#1a202c', ACCENT = '#c53030';
  var PALETTE = ['#2b6cb0', '#c53030', '#2f855a', '#d69e2e', '#6b46c1', '#dd6b20'];
  var FONT = '"Noto Sans SC", sans-serif';
  var GRAPHIC = 'path,line,polyline,polygon,rect,circle,ellipse,text';
  var BIG = 999999;

  function makeMotion(env) {
    var ctx = env.ctx, tl = env.tl, root = env.root, svg = env.svg;
    var fail = env.fail, finite = env.finite, at = env.at, onlyKeys = env.onlyKeys;
    var fx = null;

    // Decorations live in their own top-most <svg> inside ctx.root: they follow the camera,
    // sit above HTML formulas and actors, and are never touched by actors.
    function fxLayer() {
      if (fx) return fx;
      root.style.isolation = 'isolate';
      fx = svgEl('svg', {width: env.W, height: env.H, viewBox: '0 0 ' + env.W + ' ' + env.H, 'class': 'edu-fx'});
      fx.style.cssText = 'position:absolute;left:0;top:0;overflow:visible;pointer-events:none;z-index:10';
      root.appendChild(fx);
      return fx;
    }
    function targets(target, fn) {
      if (typeof target === 'string') {
        var found = Array.prototype.slice.call(root.querySelectorAll(target));
        if (!found.length) throw fail(fn + ' 找不到目标 ' + target);
        return found;
      }
      if (target instanceof Element) return [target];
      if (Array.isArray(target) && target.length && target.every(function (e) { return e instanceof Element; })) {
        return target.slice();
      }
      throw fail(fn + ' 的目标必须是元素或选择器，实际是 ' + target);
    }
    function one(target, fn) { return targets(target, fn)[0]; }
    function opts(o, allowed, fn) {
      if (o === undefined) return {};
      onlyKeys(o, allowed, fn);
      return o;
    }
    function dur(value, fallback, label) {
      return value === undefined ? fallback : at(value, label || '时长 dur');
    }
    function label(el, id) {
      if (id !== undefined) {
        if (typeof id !== 'string' || !id) throw fail('id 必须是非空字符串');
        el.setAttribute('data-edu-id', id);
      }
      return el;
    }
    // Union of the targets' boxes in root (stage) coordinates, measured now.
    function boxOf(els) {
      var ref = svg.getBoundingClientRect();
      if (!ref.width) return null;
      var k = env.W / ref.width, box = null;
      els.forEach(function (el) {
        var r = el.getBoundingClientRect();
        if (!r.width && !r.height) return;
        var b = {x: (r.left - ref.left) * k, y: (r.top - ref.top) * k, w: r.width * k, h: r.height * k};
        if (!box) { box = b; return; }
        var x2 = Math.max(box.x + box.w, b.x + b.w), y2 = Math.max(box.y + box.h, b.y + b.h);
        box.x = Math.min(box.x, b.x); box.y = Math.min(box.y, b.y);
        box.w = x2 - box.x; box.h = y2 - box.y;
      });
      return box;
    }
    function record(kind, target, start) {
      var labels = [];
      targets(target, kind).forEach(function (el) {
        var owner = el.closest('[data-edu-id]');
        var name = owner && owner.getAttribute('data-edu-id');
        if (name && labels.indexOf(name) < 0) labels.push(name);
      });
      var text = typeof target === 'string' ? target : labels.length ? '[data-edu-id="' + labels[0] + '"]' :
        (target instanceof Element ? target.tagName.toLowerCase() : 'elements');
      ctx.__highlights.push({target: text, at: start, segment: ctx.id, kind: kind, labels: labels});
    }
    // Ends an effect at `end` unless that would run past the segment; then it just holds.
    function fadeOut(target, vars, end, len) {
      if (end + len <= ctx.duration + 1e-9) tl.to(target, Object.assign({duration: len, ease: 'power1.in'}, vars), end);
    }

    // Stroke reveal: one dash of L+1 then a long gap. Offset 0 shows the whole stroke; the
    // hidden offset also moves the dash end a stroke width before the start, so a round cap
    // never shows as a dot before drawing begins.
    function strokeLength(el) {
      return typeof el.getTotalLength === 'function' ? el.getTotalLength() : 0;
    }
    function revealTween(el, start, length, ease) {
      var L = strokeLength(el);
      if (!(L > 0)) return;
      var dash = (L + 1) + 'px ' + BIG + 'px';
      var hidden = L + 1 + (parseFloat(getComputedStyle(el).strokeWidth) || 1);
      tl.fromTo(el, {strokeDasharray: dash, strokeDashoffset: hidden},
        {strokeDasharray: dash, strokeDashoffset: 0, duration: length, ease: ease, immediateRender: true}, start);
    }
    // A decoration path whose shape follows its targets' current box; drawn by `state.p`.
    function decoration(els, shape, color, width) {
      var path = svgEl('path', {fill: 'none', stroke: color, 'stroke-width': width,
        'stroke-linecap': 'round', 'stroke-linejoin': 'round'});
      path.style.visibility = 'hidden';
      fxLayer().appendChild(path);
      var state = {p: 0, o: 1};
      ctx.paint(function () {
        var box = state.p > 0 && state.o > 0 ? boxOf(els) : null;
        if (!box) { path.style.visibility = 'hidden'; return; }
        path.setAttribute('d', shape(box));
        var L = path.getTotalLength();
        path.style.strokeDasharray = (L + 1) + 'px ' + BIG + 'px';
        path.style.strokeDashoffset = ((L + 1) * (1 - state.p)) + 'px';
        path.setAttribute('opacity', String(state.o));
        path.style.visibility = 'visible';
      });
      return {path: path, state: state};
    }
    function rectShape(pad, r) {
      return function (b) {
        var x = b.x - pad, y = b.y - pad, w = b.w + 2 * pad, h = b.h + 2 * pad;
        r = Math.min(r, w / 2, h / 2);
        return 'M' + (x + r) + ',' + y + 'H' + (x + w - r) + 'Q' + (x + w) + ',' + y + ' ' + (x + w) + ',' + (y + r) +
          'V' + (y + h - r) + 'Q' + (x + w) + ',' + (y + h) + ' ' + (x + w - r) + ',' + (y + h) +
          'H' + (x + r) + 'Q' + x + ',' + (y + h) + ' ' + x + ',' + (y + h - r) +
          'V' + (y + r) + 'Q' + x + ',' + y + ' ' + (x + r) + ',' + y + 'Z';
      };
    }
    function underlineShape(b) {
      var y = b.y + b.h + 6;
      return 'M' + (b.x - 4) + ',' + (y + 2) + 'Q' + (b.x + b.w / 2) + ',' + (y - 3) + ' ' + (b.x + b.w + 4) + ',' + y;
    }
    // A hand-drawn loop: 1.1 turns of an ellipse with a smooth seeded wobble and a slight
    // outward drift, so the end overshoots the start. Fixed at build time.
    function loopShape() {
      var n = 72, turns = 1.1, phase = ctx.random() * Math.PI * 2, wobble = [];
      var p2 = ctx.random() * Math.PI * 2, p3 = ctx.random() * Math.PI * 2;
      for (var i = 0; i <= n; i++) {
        var th = turns * Math.PI * 2 * i / n;
        wobble.push(1 + 0.035 * Math.sin(2 * th + p2) + 0.025 * Math.sin(3 * th + p3) + 0.07 * i / n);
      }
      return function (b) {
        var cx = b.x + b.w / 2, cy = b.y + b.h / 2, rx = b.w / 2 * 1.25 + 10, ry = b.h / 2 * 1.35 + 10, d = '';
        for (var i = 0; i <= n; i++) {
          var a = phase + turns * Math.PI * 2 * i / n;
          d += (i ? 'L' : 'M') + round(cx + rx * wobble[i] * Math.cos(a)) + ',' + round(cy + ry * wobble[i] * Math.sin(a));
        }
        return d;
      };
    }
    // Per-element glow state, so several glows on one element never fight over `filter`.
    var glows = new Map();
    function glowOn(el, color) {
      var entry = glows.get(el);
      if (!entry) {
        entry = {original: el.style.filter, layers: []};
        glows.set(el, entry);
        ctx.paint(function () {
          var best = null;
          entry.layers.forEach(function (g) { if (g.v > 0 && (!best || g.v > best.v)) best = g; });
          el.style.filter = best ? 'drop-shadow(0 0 ' + round(10 * best.v) + 'px ' + best.color + ')' : entry.original;
        });
      }
      var layer = {v: 0, color: color};
      entry.layers.push(layer);
      return layer;
    }
    function colorTargets(els) {
      var list = [];
      els.forEach(function (el) {
        if (!(el instanceof SVGElement)) { list.push([el, 'color']); return; }
        var leaves = el.matches(GRAPHIC) ? [el] : Array.prototype.slice.call(el.querySelectorAll(GRAPHIC));
        leaves.forEach(function (leaf) {
          var css = getComputedStyle(leaf);
          var prop = leaf.matches('text') || css.fill !== 'none' ? 'fill' : 'stroke';
          if (/^rgba?\(/.test(css[prop])) list.push([leaf, prop]);
        });
      });
      return list;
    }

    var motion = {};

    motion.tex = function (latex, o) {
      o = opts(o, ['x', 'y', 'size', 'id', 'color'], 'tex');
      if (typeof latex !== 'string' || !latex) throw fail('tex 需要一段 LaTeX 字符串');
      var size = o.size === undefined ? 48 : finite(o.size, 'tex 的 size');
      var el = document.createElement('div');
      el.style.cssText = 'position:absolute;left:' + finite(o.x === undefined ? env.W / 2 : o.x, 'tex 的 x') +
        'px;top:' + finite(o.y === undefined ? env.H / 2 : o.y, 'tex 的 y') + 'px;font-size:' + size +
        'px;white-space:nowrap;line-height:1;color:' + (o.color || INK);
      label(el, o.id);
      root.appendChild(el);
      try {
        katex.render(latex, el, {
          displayMode: true, output: 'html', throwOnError: true, strict: 'ignore',
          trust: function (context) { return context.command === '\\htmlClass'; }
        });
      } catch (error) {
        el.remove();
        throw fail('tex 公式写错了：' + (error && error.message || error));
      }
      Array.prototype.forEach.call(el.querySelectorAll('.katex-display'), function (d) { d.style.margin = '0'; });
      gsap.set(el, {xPercent: -50, yPercent: -50});
      return el;
    };

    motion.highlight = function (target, start, o) {
      o = opts(o, ['dur', 'color', 'style'], 'highlight');
      start = at(start);
      var hold = dur(o.dur, 0.6);
      var color = o.color || ACCENT, style = o.style || 'glow';
      var STYLES = ['glow', 'underline', 'box', 'color'];
      if (STYLES.indexOf(style) < 0) throw fail('highlight 的 style 只能是 ' + STYLES.join('、'));
      var els = targets(target, 'highlight');
      record('highlight', target, start);
      var end = start + hold;
      if (style === 'underline' || style === 'box') {
        var deco = decoration(els, style === 'box' ? rectShape(8, 8) : underlineShape, color, style === 'box' ? 4 : 5);
        tl.to(deco.state, {p: 1, duration: Math.min(0.35, Math.max(hold, 0.05)), ease: 'power2.out'}, start);
        fadeOut(deco.state, {o: 0}, end, 0.2);
        return deco.path;
      }
      var list = colorTargets(els);
      if (!list.length) throw fail('highlight 的目标 ' + target + ' 没有可以变色的文字或图形');
      list.forEach(function (pair) {
        var original = getComputedStyle(pair[0])[pair[1]], to = {}, back = {};
        to[pair[1]] = color; back[pair[1]] = original;
        tl.to(pair[0], Object.assign({duration: 0.15, ease: 'power1.out'}, to), start);
        fadeOut(pair[0], back, end, 0.2);
      });
      if (style === 'glow') {
        els.forEach(function (el) {
          var layer = glowOn(el, color);
          tl.to(layer, {v: 1, duration: 0.15, ease: 'power1.out'}, start);
          fadeOut(layer, {v: 0}, end, 0.2);
        });
      }
      return els[0];
    };

    motion.spotlight = function (target, start, length, o) {
      o = opts(o, ['dim', 'pad'], 'spotlight');
      start = at(start);
      length = dur(length, 1);
      var dim = o.dim === undefined ? 0.25 : finite(o.dim, 'spotlight 的 dim');
      if (dim < 0 || dim > 1) throw fail('spotlight 的 dim 必须在 0 到 1 之间');
      var pad = o.pad === undefined ? 16 : finite(o.pad, 'spotlight 的 pad');
      var els = targets(target, 'spotlight');
      record('spotlight', target, start);
      var shade = svgEl('path', {fill: '#000', 'fill-rule': 'evenodd'});
      shade.style.visibility = 'hidden';
      var layer = fxLayer();
      layer.insertBefore(shade, layer.firstChild);
      var hole = rectShape(pad, 14);
      var state = {o: 0};
      ctx.paint(function () {
        var box = state.o > 0 ? boxOf(els) : null;
        if (!box) { shade.style.visibility = 'hidden'; return; }
        var big = 10 * Math.max(env.W, env.H);
        shade.setAttribute('d', 'M' + (-big) + ',' + (-big) + 'H' + big + 'V' + big + 'H' + (-big) + 'Z' + hole(box));
        shade.setAttribute('opacity', String(round(state.o * (1 - dim))));
        shade.style.visibility = 'visible';
      });
      tl.to(state, {o: 1, duration: 0.3, ease: 'power1.out'}, start);
      fadeOut(state, {o: 0}, start + length, 0.3);
      return shade;
    };

    motion.circle = function (target, start, length, o) {
      o = opts(o, ['color', 'width'], 'circle');
      start = at(start);
      length = dur(length, 0.8);
      var els = targets(target, 'circle');
      record('circle', target, start);
      var deco = decoration(els, loopShape(), o.color || ACCENT, o.width === undefined ? 5 : finite(o.width, 'circle 的 width'));
      tl.to(deco.state, {p: 1, duration: Math.max(length, 0.05), ease: 'power1.inOut'}, start);
      return deco.path;
    };

    motion.drawPath = function (target, start, length, o) {
      o = opts(o, ['ease'], 'drawPath');
      start = at(start);
      length = dur(length, 1);
      var shapes = [];
      targets(target, 'drawPath').forEach(function (el) {
        var all = el.matches(GRAPHIC) ? [el] : Array.prototype.slice.call(el.querySelectorAll(GRAPHIC));
        all.forEach(function (s) {
          if (!s.matches('text') && getComputedStyle(s).stroke !== 'none') shapes.push(s);
        });
      });
      if (!shapes.length) throw fail('drawPath 的目标里没有带描边（stroke）的图形');
      shapes.forEach(function (s) { revealTween(s, start, length, o.ease || 'power1.inOut'); });
      return shapes;
    };

    motion.plot = function (fn, o) {
      onlyKeys(o, ['xRange', 'yRange', 'box', 'samples', 'id', 'color', 'width'], 'plot');
      if (typeof fn !== 'function') throw fail('plot 的第一个参数必须是函数 x => y');
      function range(r, name) {
        if (!Array.isArray(r) || r.length !== 2 || !isFinite(r[0]) || !isFinite(r[1]) || !(r[0] < r[1])) {
          throw fail('plot 的 ' + name + ' 必须是 [最小, 最大]，且最小小于最大，实际是 ' + JSON.stringify(r));
        }
        return r;
      }
      var xr = range(o.xRange, 'xRange'), yr = range(o.yRange, 'yRange');
      var box = o.box || {};
      onlyKeys(box, ['x', 'y', 'w', 'h'], 'plot 的 box');
      ['x', 'y', 'w', 'h'].forEach(function (k) { finite(box[k], 'plot 的 box.' + k); });
      if (!(box.w > 0 && box.h > 0)) throw fail('plot 的 box.w 和 box.h 必须大于 0');
      var samples = o.samples === undefined ? 200 : o.samples;
      if (!Number.isInteger(samples) || samples < 2) throw fail('plot 的 samples 必须是不小于 2 的整数');
      function toScreen(x, y) {
        return {x: box.x + box.w * (x - xr[0]) / (xr[1] - xr[0]), y: box.y + box.h * (yr[1] - y) / (yr[1] - yr[0])};
      }
      var d = '', prev = null;
      function inside(y) { return y >= yr[0] && y <= yr[1]; }
      function edge(a, b) {  // where the segment a -> b crosses yRange's boundary
        var lim = (b.y > yr[1] || a.y > yr[1]) ? yr[1] : yr[0];
        var k = (lim - a.y) / (b.y - a.y);
        return {x: a.x + (b.x - a.x) * k, y: lim};
      }
      function put(cmd, p) { var s = toScreen(p.x, p.y); d += cmd + round(s.x) + ',' + round(s.y); }
      for (var i = 0; i <= samples; i++) {
        var x = xr[0] + (xr[1] - xr[0]) * i / samples, y = fn(x);
        var cur = typeof y === 'number' && isFinite(y) ? {x: x, y: y} : null;
        if (cur && prev) {
          var a = inside(prev.y), b = inside(cur.y);
          if (a && b) put('L', cur);
          else if (a) put('L', edge(prev, cur));
          else if (b) { put('M', edge(prev, cur)); put('L', cur); }
        } else if (cur && inside(cur.y)) put('M', cur);
        prev = cur;
      }
      if (!d) throw fail('plot 的函数在 xRange 里没有落在 yRange 内的点');
      var path = svgEl('path', {d: d, fill: 'none', stroke: o.color || '#2b6cb0',
        'stroke-width': o.width === undefined ? 4 : finite(o.width, 'plot 的 width'),
        'stroke-linecap': 'round', 'stroke-linejoin': 'round'});
      label(path, o.id);
      svg.appendChild(path);
      return {path: path, toScreen: toScreen, box: {x: box.x, y: box.y, w: box.w, h: box.h}};
    };

    motion.follow = function (target, pathEl, start, length, o) {
      o = opts(o, ['rotate', 'ease'], 'follow');
      var el = one(target, 'follow'), path = one(pathEl, 'follow 的路径');
      if (!(path instanceof SVGPathElement)) throw fail('follow 的路径必须是 <path>');
      start = at(start);
      length = dur(length, 1);
      tl.to(el, {motionPath: {path: path, autoRotate: !!o.rotate}, duration: length,
        ease: o.ease || 'power1.inOut'}, start);
    };

    motion.morph = function (fromEl, toShape, start, length, o) {
      o = opts(o, ['ease'], 'morph');
      var el = one(fromEl, 'morph');
      if (!(el instanceof SVGPathElement)) throw fail('morph 的起始图形必须是 <path>');
      var shape = toShape;
      if (typeof toShape === 'string' && !/^\s*[Mm]/.test(toShape)) shape = one(toShape, 'morph 的目标图形');
      else if (!(typeof toShape === 'string' || toShape instanceof SVGElement)) {
        throw fail('morph 的目标图形必须是 path 的 d 字符串、SVG 元素或选择器');
      }
      tl.to(el, {morphSVG: shape, duration: dur(length, 1), ease: o.ease || 'power1.inOut'}, at(start));
    };

    motion.splitText = function (target, start, o) {
      o = opts(o, ['stagger'], 'splitText');
      start = at(start);
      var stagger = o.stagger === undefined ? 0.04 : at(o.stagger, 'splitText 的 stagger');
      var el = one(target, 'splitText'), chars;
      if (el instanceof SVGElement) {
        if (!el.matches('text') || el.children.length) throw fail('splitText 只能拆只有文字的 <text>');
        var text = Array.from(el.textContent);
        el.textContent = '';
        chars = text.map(function (ch) {
          var span = svgEl('tspan', {});
          span.textContent = ch;
          el.appendChild(span);
          return span;
        });
        tl.fromTo(chars, {fillOpacity: 0, strokeOpacity: 0}, {fillOpacity: 1, strokeOpacity: 1, duration: 0.2,
          stagger: stagger, ease: 'none', immediateRender: true}, start);
      } else {
        chars = new SplitText(el, {type: 'words,chars'}).chars;
        tl.fromTo(chars, {opacity: 0}, {opacity: 1, duration: 0.2, stagger: stagger, ease: 'none',
          immediateRender: true}, start);
      }
      return chars;
    };

    motion.rough = function (kind, args, o) {
      var COUNTS = {line: 4, rect: 4, circle: 3, path: 1};
      if (!(kind in COUNTS)) throw fail('rough 的种类只能是 line、rect、circle、path');
      if (!Array.isArray(args) || args.length !== COUNTS[kind]) {
        throw fail('rough(\'' + kind + '\') 的参数要写成 ' + COUNTS[kind] + ' 项的数组');
      }
      if (kind === 'path') {
        if (typeof args[0] !== 'string') throw fail('rough(\'path\') 的参数是 [d 字符串]');
      } else {
        args.forEach(function (v, i) { finite(v, 'rough 的第 ' + (i + 1) + ' 个参数'); });
      }
      o = Object.assign({}, o || {});
      var id = o.id;
      delete o.id;
      if (o.seed === undefined) o.seed = 1 + Math.floor(ctx.random() * 2147483646);
      var rc = rough.svg(svg), node;
      if (kind === 'line') node = rc.line(args[0], args[1], args[2], args[3], o);
      else if (kind === 'rect') node = rc.rectangle(args[0], args[1], args[2], args[3], o);
      else if (kind === 'circle') node = rc.circle(args[0], args[1], args[2] * 2, o);
      else node = rc.path(args[0], o);
      label(node, id);
      svg.appendChild(node);
      return node;
    };

    function textEl(parent, x, y, content, size, color, weight) {
      var t = svgEl('text', {x: round(x), y: round(y), 'text-anchor': 'middle', 'font-size': size,
        fill: color, 'font-family': FONT});
      if (weight) t.setAttribute('font-weight', weight);
      t.textContent = content;
      parent.appendChild(t);
      return t;
    }
    function group(id) {
      var g = svgEl('g', {});
      label(g, id);
      svg.appendChild(g);
      return g;
    }

    motion.timeline = function (items, start, length, o) {
      o = opts(o, ['x', 'y', 'w', 'color', 'id'], 'timeline');
      if (!Array.isArray(items) || !items.length) throw fail('timeline 需要至少一项');
      start = at(start);
      length = dur(length, 2);
      var x0 = o.x === undefined ? 140 : finite(o.x, 'timeline 的 x');
      var y = o.y === undefined ? env.H - 140 : finite(o.y, 'timeline 的 y');
      var w = o.w === undefined ? env.W - 280 : finite(o.w, 'timeline 的 w');
      var color = o.color || PALETTE[0];
      var g = group(o.id);
      g.appendChild(svgEl('line', {x1: x0, y1: y, x2: x0 + w, y2: y, stroke: '#cbd5e0', 'stroke-width': 6,
        'stroke-linecap': 'round'}));
      var bar = svgEl('line', {x1: x0, y1: y, x2: x0 + w, y2: y, stroke: color, 'stroke-width': 6,
        'stroke-linecap': 'round'});
      g.appendChild(bar);
      tl.fromTo(bar, {scaleX: 0, svgOrigin: x0 + ' ' + y}, {scaleX: 1, svgOrigin: x0 + ' ' + y,
        duration: length, ease: 'none', immediateRender: true}, start);
      var pop = Math.min(0.3, length / 2);
      items.forEach(function (item, i) {
        if (typeof item === 'string') item = {label: item};
        onlyKeys(item, ['time', 'label'], 'timeline 的每一项');
        var f = items.length === 1 ? 1 : i / (items.length - 1);
        var x = x0 + w * f, when = start + (length - pop) * f;
        var parts = svgEl('g', {});
        parts.appendChild(svgEl('circle', {cx: round(x), cy: y, r: 12, fill: '#fff', stroke: color, 'stroke-width': 5}));
        if (item.time !== undefined) textEl(parts, x, y - 30, String(item.time), 26, color, 700);
        if (item.label !== undefined) textEl(parts, x, y + 48, String(item.label), 28, INK);
        g.appendChild(parts);
        tl.fromTo(parts, {opacity: 0, scale: 0.4, svgOrigin: round(x) + ' ' + y},
          {opacity: 1, scale: 1, svgOrigin: round(x) + ' ' + y, duration: pop, ease: 'back.out(2)',
            immediateRender: true}, when);
      });
      return g;
    };

    motion.mapRoute = function (points, start, length, o) {
      o = opts(o, ['color', 'width', 'id'], 'mapRoute');
      if (!Array.isArray(points) || points.length < 2) throw fail('mapRoute 至少需要两个点');
      start = at(start);
      length = dur(length, 2);
      var pts = points.map(function (p, i) {
        if (Array.isArray(p)) p = {x: p[0], y: p[1]};
        onlyKeys(p, ['x', 'y', 'label'], 'mapRoute 的点');
        return {x: finite(p.x, 'mapRoute 第 ' + (i + 1) + ' 个点的 x'), y: finite(p.y, 'mapRoute 第 ' + (i + 1) + ' 个点的 y'),
          label: p.label};
      });
      var color = o.color || ACCENT;
      var g = group(o.id);
      var d = pts.map(function (p, i) { return (i ? 'L' : 'M') + p.x + ',' + p.y; }).join('');
      var route = svgEl('path', {d: d, fill: 'none', stroke: color,
        'stroke-width': o.width === undefined ? 5 : finite(o.width, 'mapRoute 的 width'),
        'stroke-linecap': 'round', 'stroke-linejoin': 'round'});
      g.appendChild(route);
      var lengths = [0];
      for (var i = 1; i < pts.length; i++) {
        lengths.push(lengths[i - 1] + Math.hypot(pts[i].x - pts[i - 1].x, pts[i].y - pts[i - 1].y));
      }
      var total = lengths[lengths.length - 1] || 1;
      revealTween(route, start, length, 'none');
      var pop = Math.min(0.25, length / 2);
      pts.forEach(function (p, i) {
        var parts = svgEl('g', {});
        parts.appendChild(svgEl('circle', {cx: p.x, cy: p.y, r: 9, fill: '#fff', stroke: color, 'stroke-width': 4}));
        if (p.label !== undefined) textEl(parts, p.x, p.y - 22, String(p.label), 28, INK, 700);
        g.appendChild(parts);
        var when = Math.max(start, start + length * lengths[i] / total - pop);
        tl.fromTo(parts, {opacity: 0}, {opacity: 1, duration: pop, ease: 'none', immediateRender: true}, when);
      });
      var head = svgEl('circle', {cx: 0, cy: 0, r: 11, fill: color});
      g.appendChild(head);
      gsap.set(head, {x: pts[0].x, y: pts[0].y, opacity: 0});
      tl.set(head, {opacity: 1}, start);
      tl.to(head, {motionPath: {path: route}, duration: length, ease: 'none'}, start);
      return g;
    };

    motion.scaleCompare = function (items, start, length, o) {
      o = opts(o, ['x', 'y', 'w', 'h', 'shape', 'unit', 'id'], 'scaleCompare');
      if (!Array.isArray(items) || !items.length) throw fail('scaleCompare 需要至少一项');
      start = at(start);
      length = dur(length, 2);
      var x0 = o.x === undefined ? 200 : finite(o.x, 'scaleCompare 的 x');
      var base = o.y === undefined ? env.H - 160 : finite(o.y, 'scaleCompare 的 y');
      var w = o.w === undefined ? env.W - 400 : finite(o.w, 'scaleCompare 的 w');
      var h = o.h === undefined ? 360 : finite(o.h, 'scaleCompare 的 h');
      var shape = o.shape || 'bar';
      if (shape !== 'bar' && shape !== 'circle') throw fail('scaleCompare 的 shape 只能是 bar 或 circle');
      var unit = o.unit === undefined ? '' : String(o.unit);
      var list = items.map(function (item, i) {
        onlyKeys(item, ['label', 'value', 'color'], 'scaleCompare 的每一项');
        if (!(finite(item.value, 'scaleCompare 第 ' + (i + 1) + ' 项的 value') > 0)) {
          throw fail('scaleCompare 的 value 必须大于 0');
        }
        return item;
      });
      var max = Math.max.apply(null, list.map(function (it) { return it.value; }));
      var col = w / list.length, g = group(o.id), step = length / list.length;
      g.appendChild(svgEl('line', {x1: x0, y1: base, x2: x0 + w, y2: base, stroke: '#a0aec0', 'stroke-width': 3}));
      list.forEach(function (item, i) {
        var cx = x0 + col * (i + 0.5), color = item.color || PALETTE[i % PALETTE.length], el, top;
        if (shape === 'bar') {
          var bh = h * item.value / max, bw = Math.min(col * 0.6, 160);
          el = svgEl('rect', {x: round(cx - bw / 2), y: round(base - bh), width: round(bw), height: round(bh), rx: 6, fill: color});
          top = base - bh;
          g.appendChild(el);
          tl.fromTo(el, {scaleY: 0, svgOrigin: round(cx) + ' ' + base}, {scaleY: 1, svgOrigin: round(cx) + ' ' + base,
            duration: step, ease: 'power2.out', immediateRender: true}, start + step * i);
        } else {
          var r = Math.min(col * 0.45, h / 2) * Math.sqrt(item.value / max);
          el = svgEl('circle', {cx: round(cx), cy: round(base - r), r: round(r), fill: color});
          top = base - 2 * r;
          g.appendChild(el);
          tl.fromTo(el, {scale: 0, svgOrigin: round(cx) + ' ' + round(base - r)},
            {scale: 1, svgOrigin: round(cx) + ' ' + round(base - r), duration: step, ease: 'power2.out',
              immediateRender: true}, start + step * i);
        }
        var value = textEl(g, cx, top - 14, item.value + unit, 26, INK, 700);
        if (item.label !== undefined) textEl(g, cx, base + 40, String(item.label), 28, INK);
        tl.fromTo(value, {opacity: 0}, {opacity: 1, duration: Math.min(0.3, step / 2), ease: 'none',
          immediateRender: true}, start + step * i + step * 0.5);
      });
      return g;
    };

    return motion;
  }

  // ---- one segment instance -----------------------------------------------------------
  function createSegment(meta, host, size) {
    var id = meta.id;
    var build = segments.get(id);
    if (!build) throw new Error('第 ' + id + ' 段没有定义（缺少 EduStudio.defineSegment）');
    var W = size.width, H = size.height;
    var where = '第 ' + id + ' 段';
    function fail(message) {
      var error = new Error(where + '：' + message);
      error.segment = id;
      return error;
    }
    function note(message) { diag(where + '：' + message, id); }
    function finite(value, label) {
      if (typeof value !== 'number' || !isFinite(value)) throw fail(label + ' 必须是有限数字，实际是 ' + value);
      return value;
    }
    function at(value, label) {
      finite(value, label || '开始时间 at');
      if (value < 0) throw fail((label || '开始时间 at') + ' 不能是负数');
      return value;
    }
    function onlyKeys(obj, allowed, label) {
      if (!obj || typeof obj !== 'object') throw fail(label + ' 必须是对象');
      Object.keys(obj).forEach(function (k) {
        if (allowed.indexOf(k) < 0) throw fail(label + ' 不认识的参数 ' + k + '（只能用 ' + allowed.join('、') + '）');
      });
    }

    var layer = htmlEl('edu-layer', 'position:absolute;left:0;top:0;width:' + W + 'px;height:' + H + 'px;overflow:hidden');
    layer.setAttribute('data-segment', id);
    var cam = htmlEl('edu-camera', 'position:absolute;left:0;top:0;width:' + W + 'px;height:' + H + 'px;transform-origin:' + (W / 2) + 'px ' + (H / 2) + 'px');
    var root = htmlEl('edu-world', 'position:absolute;left:0;top:0;width:' + W + 'px;height:' + H + 'px');
    var svg = svgEl('svg', {width: W, height: H, viewBox: '0 0 ' + W + ' ' + H});
    svg.style.cssText = 'position:absolute;left:0;top:0;overflow:visible';
    root.appendChild(svg);
    cam.appendChild(root);
    layer.appendChild(cam);
    host.appendChild(layer);

    var tl = gsap.timeline({paused: true});
    var startState = meta.start_state || {camera: {x: W / 2, y: H / 2, zoom: 1}, actors: {}, keep: []};
    var narration = meta.narration || '';
    var words = meta.words || [];
    var actors = new Map();
    var keep = [];
    var painters = [];

    // Camera: `cam` zooms about the stage centre, `root` pans so (x, y) lands at the centre.
    function cameraVars(target) {
      var pan = {}, zoom = {};
      if ('x' in target) pan.x = W / 2 - finite(target.x, '镜头 x');
      if ('y' in target) pan.y = H / 2 - finite(target.y, '镜头 y');
      if ('zoom' in target) {
        if (!(finite(target.zoom, '镜头 zoom') > 0)) throw fail('镜头 zoom 必须大于 0');
        zoom.scale = target.zoom;
      }
      return {pan: pan, zoom: zoom};
    }

    var camera = {
      shot: function (target, start, dur, ease) {
        onlyKeys(target, ['x', 'y', 'zoom'], 'camera.shot');
        var vars = cameraVars(target);
        start = at(start);
        dur = dur === undefined ? 1 : at(dur, '时长 dur');
        ease = ease || 'power2.inOut';
        [[root, vars.pan], [cam, vars.zoom]].forEach(function (pair) {
          if (!Object.keys(pair[1]).length) return;
          if (dur === 0) tl.set(pair[0], pair[1], start);
          else tl.to(pair[0], Object.assign({duration: dur, ease: ease}, pair[1]), start);
        });
      }
    };
    function measureCamera() {
      var z = matrixOf(cam), p = matrixOf(root);
      return {x: round(W / 2 - p.e), y: round(H / 2 - p.f), zoom: round(Math.hypot(z.a, z.b))};
    }

    // Characters: outer <g> = position, flip <g> = mirror, scale <g> = size, then the parts.
    function actor(name, params) {
      if (actors.has(name)) throw fail('角色 ' + name + ' 已经创建过');
      var factory = characters.get(name);
      if (!factory) throw fail('没有定义角色 ' + name + '（需要 EduStudio.defineCharacter）');
      var outer = svgEl('g', {'data-actor': name});
      var flipG = svgEl('g', {});
      var scaleG = svgEl('g', {});
      flipG.appendChild(scaleG);
      outer.appendChild(flipG);
      svg.appendChild(outer);
      factory(scaleG, params || {});
      var parts = new Map();
      Array.prototype.forEach.call(scaleG.querySelectorAll('[data-part]'), function (el) {
        var partName = el.getAttribute('data-part');
        var pivot = (el.getAttribute('data-pivot') || '0,0').split(',').map(Number);
        if (parts.has(partName)) throw fail('角色 ' + name + ' 的零件 ' + partName + ' 重复');
        if (pivot.length !== 2 || !isFinite(pivot[0]) || !isFinite(pivot[1])) {
          throw fail('角色 ' + name + ' 的零件 ' + partName + ' 的 data-pivot 必须写成 "x,y"');
        }
        parts.set(partName, {el: el, pivot: pivot, origin: pivot[0] + ' ' + pivot[1]});
      });
      if (!parts.size) throw fail('角色 ' + name + ' 没有任何零件（data-part）');
      function part(partName) {
        var p = parts.get(partName);
        if (!p) throw fail('角色 ' + name + ' 没有零件 ' + partName + '（有：' + Array.from(parts.keys()).join('、') + '）');
        return p;
      }
      function shapeString() {
        var out = [];
        parts.forEach(function (p, partName) {
          // A part group may only rotate about its pivot; scale, skew or offset change its shape.
          out.push(partName + (rotatesAboutPivot(p) ? ':rigid' : ':deformed'));
          Array.prototype.forEach.call(p.el.querySelectorAll('*'), function (node) {
            out.push(partName + '>' + node.tagName);
            SHAPE_ATTRS.forEach(function (attr) {
              if (attr === 'transform' && node.hasAttribute('data-part')) return;  // pose moves parts
              var value = node.getAttribute(attr);
              if (value !== null) out.push(attr + '=' + value);
            });
          });
        });
        return out.join(';');
      }
      function setAt(start, target, vars) {
        if (start === 0) gsap.set(target, vars);
        else tl.set(target, vars, start);
      }
      function placeVars(p) {
        var list = [];
        if ('x' in p || 'y' in p) {
          var pos = {svgOrigin: '0 0'};
          if ('x' in p) pos.x = finite(p.x, '角色 x');
          if ('y' in p) pos.y = finite(p.y, '角色 y');
          list.push([outer, pos]);
        }
        if ('flip' in p) list.push([flipG, {scaleX: p.flip ? -1 : 1, scaleY: 1, svgOrigin: '0 0'}]);
        if ('scale' in p) {
          if (!(finite(p.scale, '角色 scale') > 0)) throw fail('角色 scale 必须大于 0');
          list.push([scaleG, {scale: p.scale, svgOrigin: '0 0'}]);
        }
        return list;
      }

      var api = {
        el: outer,
        part: function (partName) { return part(partName).el; },
        place: function (p, start) {
          onlyKeys(p, ['x', 'y', 'scale', 'flip'], 'place');
          start = start === undefined ? 0 : at(start);
          placeVars(p).forEach(function (pair) { setAt(start, pair[0], pair[1]); });
        },
        moveTo: function (p, start, dur, ease) {
          onlyKeys(p, ['x', 'y'], 'moveTo');
          start = at(start);
          dur = dur === undefined ? 1 : at(dur, '时长 dur');
          var vars = placeVars(p)[0];
          if (!vars) return;
          if (dur === 0) tl.set(vars[0], vars[1], start);
          else tl.to(vars[0], Object.assign({duration: dur, ease: ease || 'power1.inOut'}, vars[1]), start);
        },
        face: function (flip, start) {
          setAt(start === undefined ? 0 : at(start), flipG, placeVars({flip: !!flip})[0][1]);
        },
        pose: function (angles, start, dur, ease) {
          if (!angles || typeof angles !== 'object') throw fail('pose 需要 {零件: 角度}');
          start = at(start);
          dur = dur === undefined ? 0.4 : at(dur, '时长 dur');
          Object.keys(angles).forEach(function (partName) {
            var p = part(partName);
            var vars = {rotation: finite(angles[partName], '零件 ' + partName + ' 的角度'), svgOrigin: p.origin};
            if (dur === 0) tl.set(p.el, vars, start);
            else tl.to(p.el, Object.assign({duration: dur, ease: ease || 'power1.inOut'}, vars), start);
          });
        },
        expression: function (exprName, start) {
          start = start === undefined ? 0 : at(start);
          var faces = Array.prototype.slice.call(scaleG.querySelectorAll('[data-expression]'));
          if (!faces.some(function (f) { return f.getAttribute('data-expression') === exprName; })) {
            throw fail('角色 ' + name + ' 没有表情 ' + exprName);
          }
          faces.forEach(function (f) {
            setAt(start, f, {visibility: f.getAttribute('data-expression') === exprName ? 'visible' : 'hidden'});
          });
        }
      };

      gsap.set(outer, {x: 0, y: 0, svgOrigin: '0 0'});
      gsap.set(flipG, {scaleX: 1, scaleY: 1, svgOrigin: '0 0'});
      gsap.set(scaleG, {scale: 1, svgOrigin: '0 0'});
      parts.forEach(function (p) { gsap.set(p.el, {rotation: 0, svgOrigin: p.origin}); });
      var initial = (startState.actors || {})[name] || {x: W / 2, y: H / 2};
      placeVars({x: initial.x, y: initial.y, scale: initial.scale === undefined ? 1 : initial.scale,
        flip: !!initial.flip}).forEach(function (pair) { gsap.set(pair[0], pair[1]); });
      Object.keys(initial.pose || {}).forEach(function (partName) {
        var p = part(partName);
        gsap.set(p.el, {rotation: finite(initial.pose[partName], '零件 ' + partName + ' 的角度'), svgOrigin: p.origin});
      });
      parts.forEach(function (p, partName) {
        if (!rotatesAboutPivot(p)) {
          throw fail('角色 ' + name + ' 的零件 ' + partName + ' 的 <g> 上有平移或缩放，位置要写在里面的形状上');
        }
      });

      actors.set(name, {
        api: api,
        baseline: hashString(shapeString()),
        reported: false,
        shapeString: shapeString,
        measure: function () {
          var m = matrixOf(outer).multiply(matrixOf(flipG)).multiply(matrixOf(scaleG));
          var pose = {};
          parts.forEach(function (p, partName) {
            var pm = matrixOf(p.el);
            pose[partName] = round(Math.atan2(pm.b, pm.a) * 180 / Math.PI);
          });
          return {x: round(m.e), y: round(m.f), scale: round(Math.hypot(m.c, m.d)),
            flip: m.a * m.d - m.b * m.c < 0, pose: pose};
        }
      });
      return api;
    }

    // Word cues: the n-th occurrence of `phrase` in the narration -> covering words.
    function cueSpan(phrase, occurrence) {
      occurrence = occurrence === undefined ? 1 : occurrence;
      var missing = fail('旁白里找不到第 ' + occurrence + ' 处"' + phrase + '"');
      if (typeof phrase !== 'string' || !phrase || !Number.isInteger(occurrence) || occurrence < 1) throw missing;
      var index = -1;
      for (var n = 0; n < occurrence; n++) {
        index = narration.indexOf(phrase, index + 1);
        if (index < 0) throw missing;
      }
      var begin = Array.from(narration.slice(0, index)).length;  // code points, like Python
      var end = begin + Array.from(phrase).length;
      var hit = words.filter(function (w) { return w.char_start < end && w.char_end > begin; });
      if (!hit.length) throw missing;
      return [Math.min.apply(null, hit.map(function (w) { return w.start; })),
        Math.max.apply(null, hit.map(function (w) { return w.end; }))];
    }

    var ctx = {
      id: id,
      root: root,
      svg: svg,
      width: W,
      height: H,
      tl: tl,
      duration: meta.duration,
      startState: startState,
      cue: function (phrase, occurrence) { return cueSpan(phrase, occurrence)[0]; },
      cueEnd: function (phrase, occurrence) { return cueSpan(phrase, occurrence)[1]; },
      random: mulberry32(hash32(id, 0x811c9dc5, 16777619)),
      $: function (selector) {
        var found = Array.prototype.slice.call(root.querySelectorAll(selector));
        if (!found.length) throw fail('找不到元素 ' + selector);
        return found;
      },
      camera: camera,
      actor: actor,
      paint: function (painter) {
        if (typeof painter !== 'function') throw fail('ctx.paint 需要一个函数');
        painters.push(painter);
      },
      __highlights: [],
      __probes: {},
      endState: function (end) {
        onlyKeys(end, ['keep'], 'endState');
        var labels = end.keep || [];
        if (!Array.isArray(labels) || labels.some(function (k) { return typeof k !== 'string'; })) {
          throw fail('endState 的 keep 必须是字符串数组');
        }
        keep = labels.slice();
      }
    };

    ctx.motion = makeMotion({ctx: ctx, tl: tl, root: root, svg: svg, W: W, H: H,
      fail: fail, finite: finite, at: at, onlyKeys: onlyKeys});

    function checkGeometry() {
      actors.forEach(function (a, name) {
        if (!a.reported && hashString(a.shapeString()) !== a.baseline) {
          a.reported = true;
          note('角色零件形状被修改（' + name + '），角色只能整体移动、翻转、缩放或转动零件');
        }
      });
    }
    function paint() {
      var local = Math.min(Math.max(tl.time(), 0), meta.duration);
      painters.forEach(function (painter) { painter(local); });
    }

    var before = new Set(gsap.globalTimeline.getChildren(false, true, true));
    try {
      var startCam = cameraVars(Object.assign({x: W / 2, y: H / 2, zoom: 1}, startState.camera || {}));
      gsap.set(root, startCam.pan);
      gsap.set(cam, startCam.zoom);
      var result = build(ctx);
      if (result && typeof result.then === 'function') note('build 必须同步执行，不能返回 Promise');
      gsap.globalTimeline.getChildren(false, true, true).forEach(function (child) {
        if (!before.has(child) && child !== tl && child.duration() > 0) {
          note('有动画没放进 ctx.tl（直接用了 gsap.to/from 等），它不会随时间播放');
          child.kill();
        }
      });
      keep.forEach(function (label) {
        if (!root.querySelector('[data-edu-id="' + CSS.escape(label) + '"]')) {
          note('endState 里保留的 ' + label + ' 找不到对应的 data-edu-id 元素');
        }
      });
      if (tl.duration() > meta.duration + 1e-3) {
        note('动画长 ' + round(tl.duration()) + ' 秒，超过了本段时长 ' + meta.duration + ' 秒');
      } else {
        tl.set({}, {}, meta.duration);
      }
      // Initialise every tween in time order once, so recorded start values never depend on
      // which time is visited first. Events stay suppressed here and on every later seek:
      // callbacks fire only when crossed, so they must never drive what is drawn.
      tl.seek(tl.duration(), true);
      checkGeometry();
      tl.seek(0, true);
      paint();
    } catch (error) {
      tl.kill();
      layer.remove();
      var message = String(error && error.message || error);
      if (message.indexOf(where + '：') === 0) message = message.slice(where.length + 1);
      throw fail('构建失败：' + message);
    }

    var api = {
      id: id,
      layer: layer,
      tl: tl,
      ctx: ctx,
      checkGeometry: checkGeometry,
      paint: paint,
      api: {
        id: id,
        tl: tl,
        duration: meta.duration,
        root: root,
        cue: ctx.cue,
        cueEnd: ctx.cueEnd,
        state: function (t) {
          tl.seek(t === undefined ? tl.time() : at(t, '时间 t'), true);
          paint();
          var measured = {};
          actors.forEach(function (a, name) { measured[name] = a.measure(); });
          return {camera: measureCamera(), actors: measured, keep: keep.slice()};
        },
        highlights: function () {
          return ctx.__highlights.map(function (h) { return Object.assign({}, h, {labels: h.labels.slice()}); });
        },
        geometryDigest: function () {
          var all = [];
          actors.forEach(function (a, name) { all.push(name + ':' + a.shapeString()); });
          return hashString(all.join('|'));
        },
        destroy: function () { tl.kill(); layer.remove(); }
      }
    };
    // Checks only: functions a fixture put on ctx.__probes appear on instantiate()'s result.
    Object.keys(ctx.__probes).forEach(function (name) {
      if (!(name in api.api) && typeof ctx.__probes[name] === 'function') api.api[name] = ctx.__probes[name];
    });
    return api;
  }

  window.EduStudio = {
    defineSegment: defineSegment,
    defineCharacter: defineCharacter,
    _createSegment: createSegment,
    _diag: diag
  };
})();
