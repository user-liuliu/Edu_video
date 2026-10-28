// Segment "fx" (7 s): every ctx.motion effect at least once, overlapping in time so that the
// seek-safety check at 0.5, 2.2, 4.5 and 6.0 s lands inside many of them, plus a late camera
// push-in so decorations that measure their target are checked under the camera too.
const m = ctx.motion;

// Formula with a named term, highlighted when the narration says 顶点 (2.91 s).
m.tex('y=\\htmlClass{t-a}{x^2}-2x-3', {x: 980, y: 90, size: 44, id: 'formula'});
m.highlight('.t-a', ctx.cue('顶点'), {dur: 1.2, style: 'color'});

// Function graph, drawn from 1.0 s for 2.0 s at constant speed.
const graph = m.plot(x => x * x - 2 * x - 3, {xRange: [-2, 4], yRange: [-5, 5],
  box: {x: 100, y: 80, w: 600, h: 400}, id: 'graph'});
graph.path.id = 'curve';
m.drawPath(graph.path, 1.0, 2.0, {ease: 'none'});
ctx.__probes.plotProbe = x => graph.toScreen(x, x * x - 2 * x - 3);

const v = graph.toScreen(1, -4);
ctx.svg.insertAdjacentHTML('beforeend',
  '<text data-edu-id="vertex" x="' + v.x + '" y="' + (v.y + 50) + '" text-anchor="middle" font-size="32">顶点</text>' +
  '<text data-edu-id="title" x="860" y="200" font-size="36">抛物线的顶点</text>' +
  '<path data-edu-id="blob" d="M860,300 L960,300 L960,380 L860,380 Z" fill="#2b6cb0"/>' +
  '<circle data-edu-id="dot" cx="0" cy="0" r="10" fill="#c53030"/>');
m.highlight('[data-edu-id="vertex"]', 2.0, {dur: 1.5, style: 'box'});
m.highlight('[data-edu-id="vertex"]', 4.2, {dur: 1.0, style: 'underline'});
m.highlight('[data-edu-id="title"]', 1.8, {dur: 3.0, style: 'glow'});
m.spotlight('[data-edu-id="vertex"]', 4.0, 1.5);
m.circle('[data-edu-id="formula"]', 2.0, 0.8);
m.follow(ctx.$('[data-edu-id="dot"]')[0], graph.path, 3.2, 2.0);
m.morph('[data-edu-id="blob"]', 'M910,290 C960,290 970,340 970,340 C970,390 910,390 910,390 C860,390 850,340 850,340 C850,290 910,290 910,290 Z', 1.5, 1.5);
m.splitText(ctx.$('[data-edu-id="title"]')[0], 0.2, {stagger: 0.08});

const sketch = m.rough('rect', [760, 420, 180, 90], {stroke: '#2f855a', roughness: 1.5, id: 'sketch'});
m.drawPath(sketch, 0.3, 1.5);
m.timeline([{time: '1970', label: '开始'}, {time: '1990', label: '发展'}, '今天'], 1.0, 4.0,
  {x: 100, y: 560, w: 600});
m.mapRoute([{x: 980, y: 460, label: '甲'}, {x: 1100, y: 520}, {x: 1200, y: 440, label: '乙'}], 3.0, 2.5);
m.scaleCompare([{label: '地球', value: 1}, {label: '木星', value: 11}], 4.0, 2.0,
  {x: 960, y: 560, w: 280, h: 140, shape: 'circle'});

ctx.camera.shot({x: 700, y: 400, zoom: 1.2}, 5.2, 0.6);
