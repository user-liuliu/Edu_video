// 第 parabola 段：坐标系画出来，公式 y=x²−2x−3 出现，曲线逐步画出，
// 讲到"开口向上"时 x² 项发光，两侧箭头往上画出。结尾画面原样留给 vertex 段（continue 接缝）。
// 场景（坐标系、曲线、右侧卡片）和 vertex 段完全一样，两段各写一份。
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

// ---- timing -----------------------------------------------------------------------------
const tl = ctx.tl;
tl.from(ctx.$('[data-edu-id="grid"]'), {opacity: 0, duration: 0.6}, 0.05);
m.drawPath('[data-edu-id="axes"]', 0.15, 0.8, {ease: 'power2.out'});
tl.from(ctx.$('[data-edu-id="ticks"], [data-edu-id="tick-labels"]'), {opacity: 0, duration: 0.4}, 0.75);
tl.from(ctx.$('[data-edu-id="card"], [data-edu-id="card-rule"]'), {opacity: 0, x: 24, duration: 0.5, ease: 'power2.out'}, 0.3);
tl.from(ctx.$('[data-edu-id="formula"]'), {opacity: 0, y: 16, duration: 0.5, ease: 'power2.out'}, ctx.cue('函数'));
// Underline the formula while it is read out.
m.highlight('[data-edu-id="formula"]', ctx.cue('y'), {style: 'underline', color: BLUE,
  dur: ctx.cueEnd('减 3') - ctx.cue('y')});

// The graph is drawn while "它的图像是一条抛物线" is said.
m.drawPath(graph.path, ctx.cue('图像'), ctx.cueEnd('抛物线') - ctx.cue('图像'), {ease: 'power1.inOut'});
tl.from(ctx.$('[data-edu-id="row-curve"]'), {opacity: 0, x: -14, duration: 0.4, ease: 'power2.out'}, ctx.cue('抛物线'));

// The x² term and its coefficient.
m.highlight('.t-sq', ctx.cue('x 的平方', 2), {style: 'color', color: BLUE, dur: ctx.cueEnd('正数') - ctx.cue('x 的平方', 2)});
tl.from(ctx.$('[data-edu-id="row-coef"]'), {opacity: 0, x: -14, duration: 0.4, ease: 'power2.out'}, ctx.cue('系数'));

// "开口向上": the x² term glows, the arrows rise, the conclusion line appears.
m.highlight('.t-sq', ctx.cue('开口向上'), {style: 'glow', color: RED, dur: 1.2});
m.drawPath('[data-edu-id="open-arrows"]', ctx.cue('开口向上'), 0.5, {ease: 'power2.out'});
tl.from(ctx.$('[data-edu-id="row-open"]'), {opacity: 0, x: -14, duration: 0.4, ease: 'power2.out'}, ctx.cue('开口向上'));

ctx.endState({keep: ['axes', 'curve', 'formula', 'card']});
