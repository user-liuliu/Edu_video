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

  // Ask for every font face the stage actually uses, with the text it shows, so the right
  // unicode-range subsets are loaded before the first frame.
  function loadFonts() {
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
    master.seek(t, false);
    var active = layers[0];
    layers.forEach(function (item) { if (item.start <= t) active = item; });
    layers.forEach(function (item) {
      var on = item === active;
      item.instance.layer.style.visibility = on ? 'visible' : 'hidden';
      item.instance.layer.style.opacity = on ? '1' : '0';
      item.instance.checkGeometry();
    });
  }

  function boot() {
    try {
      film = readFilm();
      var size = {width: film.width, height: film.height};
      stage = box('edu-stage', 'position:relative;width:' + film.width + 'px;height:' + film.height + 'px;overflow:hidden');
      if (!getComputedStyle(stage).backgroundColor || getComputedStyle(stage).backgroundColor === 'rgba(0, 0, 0, 0)') {
        stage.style.backgroundColor = '#ffffff';
      }
      sandbox = box('edu-sandbox', 'position:absolute;left:0;top:0;width:' + film.width + 'px;height:' + film.height + 'px;overflow:hidden;opacity:0;visibility:hidden;pointer-events:none;z-index:-1');
      var starts = {};
      film.timeline.forEach(function (item) { if (item.id !== undefined) starts[item.id] = item.start; });
      master = gsap.timeline({paused: true});
      film.segments.forEach(function (meta) {
        var instance;
        try {
          instance = EduStudio._createSegment(meta, stage, size);
        } catch (error) {
          diag(error.message);
          instance = emptySegment(meta);
        }
        instance.tl.paused(false);
        master.add(instance.tl, starts[meta.id]);
        layers.push({id: meta.id, start: starts[meta.id], instance: instance});
      });
      master.set({}, {}, film.duration);
      master.seek(film.duration, true);
      master.seek(0, true);
      renderFrame(0);
      void stage.offsetHeight;
      loadFonts().catch(function (error) {
        diag('字体加载失败：' + (error && error.message || error));
      }).then(function () {
        renderFrame(0);
        resolveReady(true);
      });
    } catch (error) {
      diag('影片启动失败：' + (error && error.message || error));
      rejectReady(error);
    }
  }

  function emptySegment(meta) {
    var layer = document.createElement('div');
    layer.className = 'edu-layer';
    layer.setAttribute('data-segment', meta.id);
    layer.style.cssText = 'position:absolute;left:0;top:0;width:100%;height:100%';
    stage.appendChild(layer);
    var tl = gsap.timeline({paused: true});
    tl.set({}, {}, meta.duration);
    return {id: meta.id, layer: layer, tl: tl, checkGeometry: function () {}};
  }

  // Checks only: a fresh, isolated copy of one segment, built in an invisible sandbox.
  function instantiate(id) {
    if (!film) throw new Error('影片还没有启动');
    var meta = film.segments.filter(function (s) { return s.id === id; })[0];
    if (!meta) throw new Error('没有这一段：' + id);
    return EduStudio._createSegment(meta, sandbox, {width: film.width, height: film.height}).api;
  }

  window.renderFrame = renderFrame;
  window.EduFilm = {boot: boot, instantiate: instantiate};
})();
