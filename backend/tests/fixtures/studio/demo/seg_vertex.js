// 第 vertex 段：从 parabola 段的最后一帧原样开始（continue 接缝），
// 一个点沿左半支曲线滑到最低处停下；讲到"顶点"时点发光、被圈出，镜头推近；
// 随后画出到两条坐标轴的虚线，标出 (1, −4)。结尾镜头停在推近的位置，push 转场到 story 段。
const m = ctx.motion;
const FONT = 'font-family="Noto Sans SC"';
const INK = '#2d3748', MUTED = '#718096', BLUE = '#2b6cb0', RED = '#c53030';
const graph = m.plot(x => x * x - 2 * x - 3, {xRange: [-3, 5], yRange: [-5.4, 4.6],
  box: {x: 80, y: 60, w: 600, h: 540}, samples: 240, color: BLUE, width: 5, id: 'curve'});
const P = (x, y) => graph.toScreen(x, y);
const f1 = v => (Math.round(v * 10) / 10).toString();
const O = P(0, 0);

// Grid, axes and tick labels (labels sit beside their ticks, clear of the curve).
let grid = '';
for (let x = -3; x <= 5; x++) grid += '<line x1="' + f1(P(x, 0).x) + '" y1="60" x2="' + f1(P(x, 0).x) + '" y2="600"/>';
for (let y = -5; y <= 4; y++) grid += '<line x1="80" y1="' + f1(P(0, y).y) + '" x2="680" y2="' + f1(P(0, y).y) + '"/>';
let ticks = '';
[-2, -1, 1, 2, 3, 4].forEach(x => {
  ticks += '<line x1="' + f1(P(x, 0).x) + '" y1="' + f1(O.y - 6) + '" x2="' + f1(P(x, 0).x) + '" y2="' + f1(O.y + 6) + '"/>';
});
[-4, -2, 2, 4].forEach(y => {
  ticks += '<line x1="' + f1(O.x - 6) + '" y1="' + f1(P(0, y).y) + '" x2="' + f1(O.x + 6) + '" y2="' + f1(P(0, y).y) + '"/>';
});
function label(id, text, x, y, anchor) {
  return '<text data-edu-id="' + id + '" x="' + f1(x) + '" y="' + f1(y) + '" text-anchor="' + anchor + '" ' + FONT +
    ' font-size="22" fill="' + MUTED + '">' + text + '</text>';
}
const below = O.y + 30;
const labels =
  label('tick-x-2', '−2', P(-2, 0).x, below, 'middle') + label('tick-x-1', '−1', P(-1, 0).x - 12, below, 'end') +
  label('tick-x1', '1', P(1, 0).x + 6, below, 'start') + label('tick-x2', '2', P(2, 0).x, below, 'middle') +
  label('tick-x3', '3', P(3, 0).x + 12, below, 'start') + label('tick-x4', '4', P(4, 0).x, below, 'middle') +
  label('tick-y4', '4', O.x - 12, P(0, 4).y + 8, 'end') + label('tick-y2', '2', O.x - 12, P(0, 2).y + 8, 'end') +
  label('tick-y-4', '−4', O.x - 12, P(0, -4).y + 8, 'end') + label('tick-y-2', '−2', O.x + 12, P(0, -2).y + 8, 'start') + label('tick-o', 'O', O.x - 10, below, 'end') +
  '<text x="694" y="' + f1(O.y + 8) + '" ' + FONT + ' font-size="24" font-style="italic" fill="' + INK + '">x</text>' +
  '<text x="' + f1(O.x + 14) + '" y="58" ' + FONT + ' font-size="24" font-style="italic" fill="' + INK + '">y</text>';
const arrowHead = (x, y, dx, dy) => 'M' + f1(x - 9 * dx - 6 * dy) + ',' + f1(y - 9 * dy - 6 * dx) + ' L' + f1(x) + ',' + f1(y) +
  ' L' + f1(x - 9 * dx + 6 * dy) + ',' + f1(y - 9 * dy + 6 * dx);
ctx.svg.insertAdjacentHTML('afterbegin',
  '<g data-edu-id="grid" stroke="#e9e1d1" stroke-width="1">' + grid + '</g>' +
  '<g data-edu-id="axes" stroke="' + INK + '" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round">' +
  '<path d="M70,' + f1(O.y) + ' L688,' + f1(O.y) + '"/><path d="' + arrowHead(688, O.y, 1, 0) + '"/>' +
  '<path d="M' + f1(O.x) + ',610 L' + f1(O.x) + ',48"/><path d="' + arrowHead(O.x, 48, 0, -1) + '"/></g>' +
  '<g data-edu-id="ticks" stroke="' + INK + '" stroke-width="2">' + ticks + '</g>' +
  '<g data-edu-id="tick-labels">' + labels + '</g>');

// "Opens upward": an arrow inside each arm of the parabola.
const up = (x, y0, y1) => '<path d="M' + x + ',' + y0 + ' L' + x + ',' + y1 + '"/><path d="' + arrowHead(x, y1, 0, -1) + '"/>';
ctx.svg.insertAdjacentHTML('beforeend',
  '<g data-edu-id="open-arrows" stroke="' + RED + '" stroke-width="4" fill="none" stroke-linecap="round" stroke-linejoin="round">' +
  up(225, 205, 135) + up(535, 205, 135) + '</g>');

// Right-hand card: formula, then one line per idea.
ctx.svg.insertAdjacentHTML('beforeend',
  '<rect data-edu-id="card" x="730" y="70" width="490" height="350" rx="18" fill="#fffaf2" stroke="#e6d8bf" stroke-width="2"/>' +
  '<line data-edu-id="card-rule" x1="770" y1="190" x2="1180" y2="190" stroke="#e6d8bf" stroke-width="2"/>' +
  '<text data-edu-id="row-curve" x="770" y="250" ' + FONT + ' font-size="30" fill="' + INK + '">图像：抛物线</text>' +
  '<text data-edu-id="row-coef" x="770" y="310" ' + FONT + ' font-size="30" fill="' + INK + '">二次项系数 1 &gt; 0</text>' +
  '<g data-edu-id="row-open"><path d="M786,382 L786,348 M774,360 L786,346 L798,360" stroke="' + RED +
  '" stroke-width="4" fill="none" stroke-linecap="round" stroke-linejoin="round"/>' +
  '<text x="812" y="384" ' + FONT + ' font-size="38" font-weight="700" fill="' + RED + '">开口向上</text></g>');
m.tex('y=\\htmlClass{t-sq}{x^2}-2x-3', {x: 975, y: 130, size: 46, id: 'formula'});

// ---- vertex: the rolling point, its guides and its label ----------------------------------
const V = P(1, -4);
let track = '';
for (let i = 0; i <= 60; i++) {
  const x = -1.8 + 2.8 * i / 60, s = P(x, x * x - 2 * x - 3);
  track += (i ? ' L' : 'M') + f1(s.x) + ',' + f1(s.y);
}
// The path the point has travelled: a soft band drawn under the curve.
graph.path.insertAdjacentHTML('beforebegin',
  '<path data-edu-id="trail" d="' + track + '" stroke="#fbd38d" stroke-width="16" fill="none" stroke-linecap="round"/>');
ctx.svg.insertAdjacentHTML('beforeend',
  '<g data-edu-id="guides" stroke="' + RED + '" stroke-width="2.5" stroke-dasharray="8 7" opacity="0">' +
  '<line x1="' + f1(V.x) + '" y1="' + f1(V.y) + '" x2="' + f1(V.x) + '" y2="' + f1(O.y) + '"/>' +
  '<line x1="' + f1(V.x) + '" y1="' + f1(V.y) + '" x2="' + f1(O.x) + '" y2="' + f1(V.y) + '"/></g>' +
  '<circle data-edu-id="dot" cx="0" cy="0" r="11" fill="#dd6b20" stroke="#fff" stroke-width="3" opacity="0"/>' +
  '<text data-edu-id="vertex-label" x="' + f1(V.x + 26) + '" y="' + f1(V.y + 40) + '" ' + FONT +
  ' font-size="26" font-weight="700" fill="' + RED + '" opacity="0">顶点 (1, −4)</text>');
const dot = ctx.$('[data-edu-id="dot"]')[0];
const trail = ctx.$('[data-edu-id="trail"]')[0];

// ---- timing -----------------------------------------------------------------------------
const tl = ctx.tl;
// "让一个点": the point pops up at the top of the left arm.
tl.fromTo(dot, {opacity: 0, attr: {r: 2}}, {opacity: 1, attr: {r: 11}, duration: 0.35, ease: 'back.out(2.5)'}, ctx.cue('点'));
// "沿着曲线往下走，走到最低的地方停下": it slides down, slowing into the bottom.
const rollStart = ctx.cue('往下'), rollLength = ctx.cueEnd('停下') - 0.1 - ctx.cue('往下');
m.follow(dot, trail, rollStart, rollLength, {ease: 'power2.inOut'});
m.drawPath(trail, rollStart, rollLength, {ease: 'power2.inOut'});
tl.to(dot, {attr: {r: 15}, duration: 0.15, ease: 'power2.out', yoyo: true, repeat: 1}, rollStart + rollLength);

// "这个点就是顶点": the point glows, gets circled, and the camera pushes in.
m.highlight(dot, ctx.cue('顶点'), {style: 'glow', color: RED, dur: 1.4});
m.circle(dot, ctx.cue('顶点') + 0.1, 0.7, {color: RED, width: 4});
ctx.camera.shot({x: 372, y: 460, zoom: 1.8}, ctx.cue('顶点'), 1.0, 'power2.inOut');

// "坐标是 1 和负 4": dashed guides to both axes, the label, then each number lights up.
tl.to(ctx.$('[data-edu-id="guides"]'), {opacity: 1, duration: 0.4}, ctx.cue('坐标'));
tl.fromTo(ctx.$('[data-edu-id="vertex-label"]'), {opacity: 0, x: -10}, {opacity: 1, x: 0, duration: 0.4, ease: 'power2.out'}, ctx.cue('坐标'));
m.highlight('[data-edu-id="tick-x1"]', ctx.cue('1'), {style: 'glow', color: RED, dur: 0.8});
m.highlight('[data-edu-id="tick-y-4"]', ctx.cue('负 4'), {style: 'glow', color: RED, dur: 0.8});

ctx.endState({keep: ['axes', 'curve', 'formula', 'card', 'dot', 'vertex-label']});
