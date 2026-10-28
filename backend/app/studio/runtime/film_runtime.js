/* EduFilm: lays out the film's segments on one paused master timeline.
 * Minimal version: segments follow each other with no transition; at a segment's start
 * time its layer replaces the previous one. Seams, captions and per-segment error
 * isolation are added later. */
(function () {
  'use strict';
  var diag = EduStudio._diag;
  var film = null;
  var master = null;
  var stage = null;
  var sandbox = null;
  var layers = [];  // [{id, start, instance}]

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
  // plus printable ASCII, and every KaTeX face when the code calls katex, so build-time
  // measurements already use the real metrics.
  function preloadFonts() {
    var sample = ' ';
    for (var c = 33; c < 127; c++) sample += String.fromCharCode(c);
    var seen = new Set(sample);
    Array.prototype.forEach.call(document.querySelectorAll('script:not([src])'), function (script) {
      Array.from(script.textContent).forEach(function (ch) {
        if (ch.trim() && !seen.has(ch)) { seen.add(ch); sample += ch; }
      });
    });
    var usesKatex = /\bkatex\s*\./.test(Array.prototype.map.call(
      document.querySelectorAll('script:not([src])'), function (s) { return s.textContent; }).join('\n'));
    var keys = new Set();
    document.fonts.forEach(function (face) {
      var family = face.family.replace(/^["']|["']$/g, '');
      if (TEXT_FAMILIES.indexOf(family) >= 0 || (usesKatex && family.indexOf(KATEX_PREFIX) === 0)) {
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

  function renderFrame(t) {
    if (!master) throw new Error('影片还没有启动');
    if (typeof t !== 'number' || !isFinite(t)) throw new Error('renderFrame 的时间必须是有限数字');
    t = Math.min(Math.max(t, 0), film.duration);
    master.seek(t, true);  // events stay suppressed: callbacks never drive the picture
    var active = layers[0];
    layers.forEach(function (item) { if (item.start <= t) active = item; });
    if (!active.failed) {
      try {
        active.instance.paint();
      } catch (error) {
        isolate(active, '第 ' + active.id + ' 段：绘制失败：' + (error && error.message || error));
      }
    }
    layers.forEach(function (item) {
      var on = item === active && !item.failed;
      item.instance.layer.style.visibility = on ? 'visible' : 'hidden';
      item.instance.layer.style.opacity = on ? '1' : '0';
      item.instance.checkGeometry();
    });
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

  function build() {
    var size = {width: film.width, height: film.height};
    stage = box('edu-stage', 'position:relative;width:' + film.width + 'px;height:' + film.height + 'px;overflow:hidden');
    if (!getComputedStyle(stage).backgroundColor || getComputedStyle(stage).backgroundColor === 'rgba(0, 0, 0, 0)') {
      stage.style.backgroundColor = '#ffffff';
    }
    sandbox = box('edu-sandbox', 'position:absolute;left:0;top:0;width:' + film.width + 'px;height:' + film.height + 'px;overflow:hidden;opacity:0;visibility:hidden;pointer-events:none;z-index:-1');
    var starts = {};
    film.timeline.forEach(function (item) { if (item.id !== undefined) starts[item.id] = item.start; });
    var timeline = gsap.timeline({paused: true});
    film.segments.forEach(function (meta) {
      if (typeof starts[meta.id] !== 'number') throw new Error('时间线里没有第 ' + meta.id + ' 段');
      var instance;
      try {
        instance = EduStudio._createSegment(meta, stage, size);
      } catch (error) {
        diag(String(error && error.message || error), meta.id);
        instance = emptySegment(meta);
      }
      instance.tl.paused(false);
      timeline.add(instance.tl, starts[meta.id]);
      layers.push({id: meta.id, start: starts[meta.id], instance: instance, failed: !!instance.failed});
    });
    timeline.set({}, {}, film.duration);
    // Same preroll as each segment, with events suppressed.
    timeline.seek(film.duration, true);
    timeline.seek(0, true);
    master = timeline;
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
    var layer = document.createElement('div');
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
    if (!master) throw new Error('影片还没有启动');
    var meta = film.segments.filter(function (s) { return s.id === id; })[0];
    if (!meta) throw new Error('没有这一段：' + id);
    return EduStudio._createSegment(meta, sandbox, {width: film.width, height: film.height}).api;
  }

  window.renderFrame = renderFrame;
  window.EduFilm = {boot: boot, instantiate: instantiate};
})();
