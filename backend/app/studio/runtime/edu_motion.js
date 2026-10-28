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
  function diag(message) {
    if (diagnostics.indexOf(message) < 0) diagnostics.push(message);
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

  // ---- one segment instance -----------------------------------------------------------
  function createSegment(meta, host, size) {
    var id = meta.id;
    var build = segments.get(id);
    if (!build) throw new Error('第 ' + id + ' 段没有定义（缺少 EduStudio.defineSegment）');
    var W = size.width, H = size.height;
    var where = '第 ' + id + ' 段';
    function fail(message) { return new Error(where + '：' + message); }
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
    var startCam = cameraVars(Object.assign({x: W / 2, y: H / 2, zoom: 1}, startState.camera || {}));
    gsap.set(root, startCam.pan);
    gsap.set(cam, startCam.zoom);

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
      endState: function (end) {
        onlyKeys(end, ['keep'], 'endState');
        var labels = end.keep || [];
        if (!Array.isArray(labels) || labels.some(function (k) { return typeof k !== 'string'; })) {
          throw fail('endState 的 keep 必须是字符串数组');
        }
        keep = labels.slice();
      }
    };

    var before = new Set(gsap.globalTimeline.getChildren(false, true, true));
    var result;
    try {
      result = build(ctx);
    } catch (error) {
      tl.kill();
      layer.remove();
      throw fail('构建失败：' + (error && error.message || error));
    }
    if (result && typeof result.then === 'function') diag(where + '：build 必须同步执行，不能返回 Promise');
    gsap.globalTimeline.getChildren(false, true, true).forEach(function (child) {
      if (!before.has(child) && child !== tl && child.duration() > 0) {
        diag(where + '：有动画没放进 ctx.tl（直接用了 gsap.to/from 等），它不会随时间播放');
        child.kill();
      }
    });
    keep.forEach(function (label) {
      if (!root.querySelector('[data-edu-id="' + CSS.escape(label) + '"]')) {
        diag(where + '：endState 里保留的 ' + label + ' 找不到对应的 data-edu-id 元素');
      }
    });
    if (tl.duration() > meta.duration + 1e-3) {
      diag(where + '：动画长 ' + round(tl.duration()) + ' 秒，超过了本段时长 ' + meta.duration + ' 秒');
    } else {
      tl.set({}, {}, meta.duration);
    }

    function checkGeometry() {
      actors.forEach(function (a, name) {
        if (!a.reported && hashString(a.shapeString()) !== a.baseline) {
          a.reported = true;
          diag(where + '：角色零件形状被修改（' + name + '），角色只能整体移动、翻转、缩放或转动零件');
        }
      });
    }
    // Initialise every tween in time order once, so recorded start values never depend on
    // which time is visited first. Events stay on: seeking back fires each tween's ratio-0
    // onUpdate, so canvas drawn in onUpdate shows the same frame 0 as after any later visit.
    tl.seek(tl.duration(), false);
    checkGeometry();
    tl.seek(0, false);

    return {
      id: id,
      layer: layer,
      tl: tl,
      ctx: ctx,
      checkGeometry: checkGeometry,
      api: {
        id: id,
        tl: tl,
        duration: meta.duration,
        root: root,
        cue: ctx.cue,
        cueEnd: ctx.cueEnd,
        state: function (t) {
          tl.seek(t === undefined ? tl.time() : at(t, '时间 t'), false);
          var measured = {};
          actors.forEach(function (a, name) { measured[name] = a.measure(); });
          return {camera: measureCamera(), actors: measured, keep: keep.slice()};
        },
        geometryDigest: function () {
          var all = [];
          actors.forEach(function (a, name) { all.push(name + ':' + a.shapeString()); });
          return hashString(all.join('|'));
        },
        destroy: function () { tl.kill(); layer.remove(); }
      }
    };
  }

  window.EduStudio = {
    defineSegment: defineSegment,
    defineCharacter: defineCharacter,
    _createSegment: createSegment,
    _diag: diag
  };
})();
