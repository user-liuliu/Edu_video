// 孔融和哥哥：照抄 .local/previews/character-reference.html 的零件、配色和关节位置。
// 参考文件把人物画在 200x320 的框里、脚底在 (100,320)；这里脚底放在 (0,0)，
// 所以每个零件里套一层固定的平移，形状坐标保持参考文件的原样。
// 零件只绕关节转动：arm_back（远侧手臂，画在身体后面）、arm_front（近侧手臂）、head（绕颈部）。
// 孔融远侧手里有一只大梨（data-prop="pear"），开始时隐藏，段代码用 tl.set 切换它的 visibility。
(function () {
  var NS = 'http://www.w3.org/2000/svg';
  var KONGRONG = {robe: '#3f7cac', robeDark: '#2f5f86', belt: '#d0603f', hair: '#2a2420', skin: '#f7d5b8', buns: true};
  var BROTHER = {robe: '#7a9a4f', robeDark: '#5c7a39', belt: '#c99a3c', hair: '#2a2420', skin: '#f2cdb0', buns: false};
  var INK = '#2a2420';

  function el(tag, attrs, into) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (into) into.appendChild(e);
    return e;
  }
  // A part rotating about (px, py) in feet-at-origin coordinates; its shapes are drawn in a
  // static inner frame whose origin is (ox, oy).
  function part(g, name, px, py, ox, oy) {
    var p = el('g', {'data-part': name, 'data-pivot': px + ',' + py}, g);
    return el('g', {transform: 'translate(' + ox + ',' + oy + ')'}, p);
  }

  // The reference pear, drawn around (0,0): big = the 1.25 size, else the 0.85 size.
  function pear(into, big) {
    var r = big ? 1.25 : 0.85;
    el('path', {d: 'M0,' + (-14 * r) + ' C' + (9 * r) + ',' + (-14 * r) + ' ' + (8 * r) + ',' + (-3 * r) + ' ' + (12 * r) + ',' + (6 * r) +
      ' C' + (16 * r) + ',' + (16 * r) + ' ' + (8 * r) + ',' + (22 * r) + ' 0,' + (22 * r) + ' C' + (-8 * r) + ',' + (22 * r) + ' ' +
      (-16 * r) + ',' + (16 * r) + ' ' + (-12 * r) + ',' + (6 * r) + ' C' + (-8 * r) + ',' + (-3 * r) + ' ' + (-9 * r) + ',' + (-14 * r) + ' 0,' + (-14 * r) + 'Z',
      fill: '#e8c547', stroke: '#c9a22e', 'stroke-width': 1.5}, into);
    el('path', {d: 'M' + (-5 * r) + ',' + (4 * r) + ' q' + (-3 * r) + ',' + (6 * r) + ' 0,' + (12 * r), stroke: '#f6e08c',
      'stroke-width': 3, fill: 'none', 'stroke-linecap': 'round'}, into);
    el('path', {d: 'M0,' + (-14 * r) + ' q2,-6 4,-9', stroke: '#6b4a2b', 'stroke-width': 2.2, fill: 'none', 'stroke-linecap': 'round'}, into);
    el('path', {d: 'M3,' + (-19 * r) + ' q8,-6 12,0 q-7,4 -12,0Z', fill: '#6aa14a'}, into);
  }

  // The reference arm, hanging straight down from its shoulder at (0,0) of the arm frame.
  function arm(frame, c) {
    el('path', {d: 'M-13,-4 Q0,-12 13,-4 L20,74 Q2,86 -18,76 Z', fill: c.robe}, frame);
    el('path', {d: 'M-18,70 Q2,82 20,70 L21,78 Q2,90 -19,80Z', fill: c.robeDark}, frame);
    el('circle', {cx: 1, cy: 86, r: 9, fill: c.skin}, frame);
  }

  function eyes(face) {
    el('ellipse', {cx: 84, cy: 106, rx: 4.2, ry: 5.5, fill: INK}, face);
    el('ellipse', {cx: 116, cy: 106, rx: 4.2, ry: 5.5, fill: INK}, face);
    el('circle', {cx: 85.5, cy: 104, r: 1.5, fill: '#fff'}, face);
    el('circle', {cx: 117.5, cy: 104, r: 1.5, fill: '#fff'}, face);
  }
  function stroke(face, d, width) {
    el('path', {d: d, stroke: INK, 'stroke-width': width || 2.6, fill: 'none', 'stroke-linecap': 'round'}, face);
  }
  function mouth(face, smile) {
    el('path', {d: smile ? 'M92,124 q8,8 16,0' : 'M94,126 q6,3 12,0', stroke: '#a4473a', 'stroke-width': 2.4,
      fill: 'none', 'stroke-linecap': 'round'}, face);
  }
  function expression(head, name, draw) {
    var face = el('g', {'data-expression': name}, head);
    if (name !== 'calm') face.style.visibility = 'hidden';
    draw(face);
  }

  function child(g, c, holdsPear) {
    // Shadow on the ground (never rotated).
    el('ellipse', {cx: 100, cy: 318, rx: 58, ry: 9, fill: 'rgba(70,50,20,.15)'}, part(g, 'shadow', 0, 0, -100, -320));

    // Far arm: shoulder at (132,158) in the reference, behind the body.
    var back = part(g, 'arm_back', 32, -162, 32, -162);
    arm(back, c);
    if (holdsPear) {
      var held = el('g', {'data-prop': 'pear', transform: 'translate(1,104)'}, back);
      held.style.visibility = 'hidden';
      pear(held, true);
    }

    // Shoes, robe, collar and belt.
    var body = part(g, 'body', 0, 0, -100, -320);
    el('ellipse', {cx: 80, cy: 309, rx: 15, ry: 8, fill: '#3b2f2a'}, body);
    el('ellipse', {cx: 120, cy: 309, rx: 15, ry: 8, fill: '#3b2f2a'}, body);
    el('path', {d: 'M64,152 Q100,140 136,152 L156,300 Q100,314 44,300 Z', fill: c.robe}, body);
    el('path', {d: 'M100,146 L100,306 Q72,306 46,300 L64,152 Q82,146 100,146Z', fill: c.robeDark, opacity: 0.35}, body);
    el('path', {d: 'M84,148 L120,206 L128,198 L96,146Z', fill: '#fbf4e6'}, body);
    el('path', {d: 'M116,148 L100,176 L94,168 L106,146Z', fill: '#efe3cc'}, body);
    el('path', {d: 'M58,204 Q100,214 142,204 L144,220 Q100,230 56,220Z', fill: c.belt}, body);
    el('rect', {x: 94, y: 206, width: 12, height: 18, rx: 3, fill: '#f3d27a'}, body);

    // Near arm: shoulder at (68,158) in the reference, in front of the body.
    arm(part(g, 'arm_front', -32, -162, -32, -162), c);

    // Head, turning about the neck at (100,145) in the reference.
    var head = part(g, 'head', 0, -175, -100, -320);
    el('rect', {x: 92, y: 130, width: 16, height: 22, rx: 6, fill: c.skin}, head);
    if (c.buns) {
      el('circle', {cx: 64, cy: 52, r: 17, fill: c.hair}, head);
      el('circle', {cx: 136, cy: 52, r: 17, fill: c.hair}, head);
      el('path', {d: 'M52,62 q6,8 16,4', stroke: '#d0603f', 'stroke-width': 5, fill: 'none', 'stroke-linecap': 'round'}, head);
      el('path', {d: 'M148,62 q-6,8 -16,4', stroke: '#d0603f', 'stroke-width': 5, fill: 'none', 'stroke-linecap': 'round'}, head);
    } else {
      el('ellipse', {cx: 100, cy: 40, rx: 16, ry: 13, fill: c.hair}, head);
      el('rect', {x: 92, y: 24, width: 16, height: 6, rx: 3, fill: '#c99a3c'}, head);
    }
    el('ellipse', {cx: 100, cy: 98, rx: 46, ry: 47, fill: c.hair}, head);
    el('ellipse', {cx: 100, cy: 104, rx: 41, ry: 41, fill: c.skin}, head);
    el('ellipse', {cx: 58, cy: 106, rx: 7, ry: 10, fill: c.skin}, head);
    el('ellipse', {cx: 142, cy: 106, rx: 7, ry: 10, fill: c.skin}, head);
    el('path', {d: 'M58,92 Q60,58 100,56 Q140,58 142,92 Q128,74 110,80 Q104,70 96,80 Q76,72 58,92Z', fill: c.hair}, head);
    stroke(head, 'M77,94 q7,-4 14,0', 2.2);
    stroke(head, 'M109,94 q7,-4 14,0', 2.2);
    el('ellipse', {cx: 74, cy: 120, rx: 7, ry: 4, fill: '#f2a7a0', opacity: 0.6}, head);
    el('ellipse', {cx: 126, cy: 120, rx: 7, ry: 4, fill: '#f2a7a0', opacity: 0.6}, head);
    // Faces: the reference's two mouths, plus closed eyes for a blink and a happy squint.
    expression(head, 'calm', function (f) { eyes(f); mouth(f, false); });
    expression(head, 'smile', function (f) { eyes(f); mouth(f, true); });
    expression(head, 'blink', function (f) { stroke(f, 'M80,107 q4,2 8,0'); stroke(f, 'M112,107 q4,2 8,0'); mouth(f, false); });
    expression(head, 'joy', function (f) { stroke(f, 'M79,108 q5,-6 10,0'); stroke(f, 'M111,108 q5,-6 10,0'); mouth(f, true); });
  }

  EduStudio.defineCharacter('kongrong', function (g) { child(g, KONGRONG, true); });
  EduStudio.defineCharacter('brother', function (g) { child(g, BROTHER, false); });
})();
