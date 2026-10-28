# 动效库接口（EduStudio）

单位：时间一律是**秒**（从本段 0 秒算起），坐标和长度是**像素**（画布左上角为原点，默认 1280×720），角度是**度**（顺时针为正，读回的值在 -180 到 180 之间）。

## 规则

- 每一帧只由时间决定。所有动画都放在 `ctx.tl` 上，运行时只通过 seek 定位，不会自己播放。
- `build(ctx)` 同步执行，不能用定时器、`requestAnimationFrame`、`Math.random`、`Date`、网络请求。需要随机数用 `ctx.random()`。
- 不要用 `gsap.to/from/timeline` 直接建动画（不会播放，会记一条诊断）；用 `ctx.tl.to/from/fromTo/set`。`gsap.set` 可以用，会立即生效，作为本段的初始状态。
- 运行时定位时间线时不触发任何回调。所以 `tl.call`、`onStart`、`onComplete`、`onUpdate` 里不要改任何看得见的东西，改了也不会显示。
- 瞬间的变化，比如换文字、显示或隐藏，用 `ctx.tl.set`，例如 `ctx.tl.set(el, {textContent: 'B'}, 2)`。连续的变化用 `ctx.tl.to` 去补间元素属性或普通对象。
- Canvas 和 three.js 只能在 `ctx.paint` 里画，每次都把整块画布重画一遍，画的时候读被补间的普通对象。
- 画布是 1280×720。所有文字都要放在 y=625 以上：底部（y 从 625 到 720）是程序显示字幕的地方。`timeline`、`mapRoute`、`scaleCompare` 的文字进入这里时会记一条诊断。
- 文字超出画布按镜头移动前的位置检查。故意放在画布外的文字必须给它（或它的外层组）加 `data-edu-offstage`：包括镜头平移或推移才带进画面的文字（比如长时间线远端的标签），以及之后再移进来或移出去的文字。这个标记只免去"超出画布"这一项：文字出现在画面上时，仍然不能压进字幕区，也不能和别的文字重叠。
- 元素用 `data-edu-id="标签"` 命名，高亮和 `endState` 都按这个标签找元素。SVG 里的 `id`（渐变、滤镜、clipPath）要带上段 id 前缀，避免和别的段重名。
- 可用的库：`gsap`（含 DrawSVGPlugin、MorphSVGPlugin、MotionPathPlugin、SplitText）、`katex`、`THREE`、`rough`。字体：`"Noto Sans SC"`（400、700）、`"LXGW WenKai"`。

## 段代码

你写的段代码只是一个函数体，里面可以直接用 `ctx`。程序会把它包成 `EduStudio.defineSegment("段id", function (ctx) { 你的代码 })`，所以段代码里不要再写 `defineSegment`，也不要写 `function (ctx)`。本文的示例除了 `defineCharacter` 那一个，其余都是段代码，可以直接写进函数体。这些示例前后相接，后面的示例会用到前面定义的变量。
```js
ctx.svg.innerHTML = '<circle data-edu-id="dot" cx="640" cy="360" r="20" fill="#c53030"/>';
ctx.tl.to(ctx.$('[data-edu-id="dot"]'), {x: 200, duration: 1}, 0.5);
```

## 角色定义

### `EduStudio.defineCharacter(name, factory)`
角色代码不属于段代码，它单独放一处，要写完整的 `defineCharacter` 调用。`factory(g, params)` 往 SVG 组 `g` 里画零件，角色脚底放在 (0,0)。每个零件是 `<g data-part="名字" data-pivot="x,y">`，零件只能绕 pivot 转动（pose）。零件自己的 `<g>` 上不要写 transform，位置写在里面的形状上。表情是带 `data-expression="名字"` 的组，不用的先设 `style.visibility='hidden'`。创建以后，零件的 `<g>` 不能平移、缩放或倾斜，里面形状的 `d`、坐标、尺寸和 transform 也不能改，否则会记"角色零件形状被修改"。
```js
EduStudio.defineCharacter('kr', function (g, params) {
  const c = params.color || '#333';
  g.innerHTML =
    '<g data-part="body" data-pivot="0,-60"><path d="M0,-120 L0,0" stroke="' + c + '" stroke-width="8"/></g>' +
    '<g data-part="arm_r" data-pivot="0,-105"><path d="M0,-105 L45,-80" stroke="' + c + '" stroke-width="8"/></g>' +
    '<g data-expression="smile"><path d="M-10,-140 Q0,-130 10,-140" stroke="' + c + '" fill="none"/></g>' +
    '<g data-expression="sad" style="visibility:hidden"><path d="M-10,-133 Q0,-143 10,-133" stroke="' + c + '" fill="none"/></g>';
});
```

## ctx 的成员

### 舞台
- `ctx.root`：本段内容所在的元素，跟着镜头移动。HTML 元素（如 KaTeX 公式）放在这里。
- `ctx.svg`：覆盖整个画布的 `<svg>`，viewBox 等于画布尺寸。
- `ctx.width`、`ctx.height`：画布宽高（像素）。`ctx.id`：本段 id。
- `ctx.$(sel) -> Element[]`：只在 `ctx.root` 内查找，返回数组；一个都找不到时抛错。
```js
const dot = ctx.$('[data-edu-id="dot"]')[0];
```

### 时间
- `ctx.tl`：暂停的 GSAP 时间线，0 秒是本段开头。位置参数写秒数。
- `ctx.duration`：本段时长（秒）。动画不能超过它。
- `ctx.cue(phrase, occurrence=1) -> 秒`：旁白里第 n 处 `phrase` 开始说出的时间。找不到时抛错，信息里有这个词和段 id。
- `ctx.cueEnd(phrase, occurrence=1) -> 秒`：这处 `phrase` 说完的时间。
```js
ctx.tl.to(dot, {scale: 1.5, duration: 0.3}, ctx.cue('顶点'));
ctx.tl.to(dot, {scale: 1, duration: 0.3}, ctx.cueEnd('顶点'));
```

### 工具
- `ctx.random() -> [0, 1)`：种子由段 id 决定，每次构建结果相同。
- `ctx.startState`：本段开始时的画面状态 `{camera: {x, y, zoom}, actors: {名字: {x, y, scale, flip, pose}}, keep: [...]}`。
```js
const jitter = (ctx.random() - 0.5) * 20;  // -10 到 10 像素
```

### 绘制
`ctx.paint(painter)`：注册一个绘制函数。每次定位到新的时间，只要本段可见，运行时会在补间值都更新好以后调用 `painter(t)`，`t` 是本段内的时间（秒）。painter 只能根据补间出来的值和 `t` 把画布整块重画，不能累积上一帧的结果。painter 抛错时，本段从此不再显示，并记一条带段 id 的诊断。
```js
const canvas = document.createElement('canvas');
canvas.width = 400; canvas.height = 200;
ctx.root.appendChild(canvas);
const g = canvas.getContext('2d');
const bar = {w: 0};
ctx.tl.to(bar, {w: 400, duration: 2, ease: 'none'}, 0.5);
ctx.paint(function (t) {
  g.clearRect(0, 0, 400, 200);
  g.fillStyle = '#2b6cb0';
  g.fillRect(0, 80, bar.w, 40);
});
```

### 镜头
`ctx.camera.shot({x, y, zoom}, at, dur=1, ease='power2.inOut')`：从 `at` 秒起用 `dur` 秒把镜头对准画布坐标 (x, y)，zoom 为放大倍数（1 为原样，大于 0）。三个参数都可以只写一部分。`dur` 为 0 时直接切过去。本段开始时自动应用 `startState.camera`（默认 x=640、y=360、zoom=1）。
```js
ctx.camera.shot({x: 640, y: 450, zoom: 1.4}, ctx.cue('顶点'), 0.8);
```

### 角色
`ctx.actor(name, params) -> Actor`：创建用 `defineCharacter(name)` 定义的角色，同一段里每个名字只能创建一次。开始时自动应用 `startState.actors[name]`；没有的话放在画布中心。

Actor 的方法：
- `place({x, y, scale, flip}, at=0)`：在 `at` 秒瞬间放到位置 (x, y)（脚底），`scale` 为大小倍数，`flip: true` 为水平镜像。只写需要改的参数。
- `moveTo({x, y}, at, dur=1, ease='power1.inOut')`：从 `at` 秒起用 `dur` 秒走到 (x, y)。
- `face(flip, at=0)`：在 `at` 秒转向，`true` 为水平镜像。
- `pose({零件: 角度}, at, dur=0.4, ease='power1.inOut')`：从 `at` 秒起用 `dur` 秒把零件转到指定角度（绝对角度，0 为原样）。
- `expression(name, at=0)`：在 `at` 秒切换到这个表情，其他表情隐藏。
- `el`：角色最外层的 `<g>`；`part(name)`：零件的 `<g>`。只用来读或改颜色、透明度，不要改形状。
```js
const kr = ctx.actor('kr', {color: '#2b6cb0'});
kr.place({x: 300, y: 600, scale: 0.8});
kr.moveTo({x: 500, y: 600}, 1, 1);
kr.pose({arm_r: -60}, 1.2, 0.6);
kr.face(true, 2.2);
kr.expression('sad', ctx.cue('最低点'));
kr.part('arm_r').setAttribute('opacity', '0.9');
```

### 结束状态
`ctx.endState({keep: [标签...]})`：声明本段结束时留给下一段的元素（`data-edu-id` 标签）。镜头和角色的结束状态由运行时在最后一帧实际测量，不用声明。
```js
ctx.endState({keep: ['dot']});
```

## 效果（`ctx.motion`）

常用的讲解效果都在 `ctx.motion` 上，它们只往 `ctx.tl` 里加动画，可以随意定位。通用约定：
- `at`、`dur` 单位是秒，`at` 通常写成 `ctx.cue('...')`。坐标、尺寸是像素。
- `target` 可以是元素、元素数组，或选择器（只在 `ctx.root` 里找，找不到时抛错，信息以"第 段id 段："开头）。
- 有时长的强调（`highlight`、`spotlight`）在 `at + dur` 后恢复成强调开始前一刻的样子（比如本段先把文字变成了蓝色，强调完还是蓝色）；如果恢复会超过本段时长，就保持到本段结束。`dur` 比淡入时间还短时，按淡入时间算。
- 所有强调（`highlight` 的每种 style 和 `spotlight`）都在 `at` 之后 0.15 秒内达到最强，结束时也用 0.15 秒恢复。
- 同一元素的强调重叠时，以后开始的为准：几处变色或发光同时作用在一个元素上时，按开始时间先后叠加，后开始的盖在上面，完全亮起后只看得到它；前一个还没结束时后一个结束了，就回到前一个的颜色。底色是本段自己的动画当时给它的颜色。
- 下划线、框、圈和聚光灯画在 `ctx.root` 里最上层的 `<svg class="edu-fx">` 上：跟着镜头动，盖在公式和角色上面，角色和镜头参数不会改它。它们每一帧按目标当时的位置重画，目标移动时也跟着走。`ctx.$('path')` 这样的宽泛选择器也会选到这些装饰，找元素请用 `data-edu-id`。

### `tex(latex, {x, y, size=48, color, id}) -> Element`
用 KaTeX 把公式画成 HTML 元素，放进 `ctx.root`。(x, y) 是公式中心，`size` 是公式实际的字号（像素，即 `.katex` 元素的 font-size），`id` 会写成 `data-edu-id`。只允许 `\htmlClass` 这一个扩展命令，用来给公式里的某一项命名。公式写错时抛错。JS 字符串里反斜杠要写两个。
```js
const formula = ctx.motion.tex('y=x^2-2x-3', {x: 900, y: 120, size: 44, id: 'formula'});
```

### `highlight(target, at, {dur=0.6, color='#c53030', style='glow'}) -> Element`
从 `at` 秒起用 0.15 秒变亮（下划线和框用 0.15 秒画完），保持到 `at + dur`，再用 0.15 秒恢复。`style`：`'glow'` 变色并发光，`'color'` 只变色，`'underline'` 画下划线，`'box'` 画圆角框。HTML 元素改文字颜色；SVG 图形改填充（没有填充的改描边），`<g>` 会改里面所有图形。每次调用都会被记下，用来检查高亮是否和旁白里的词对上。
```js
ctx.motion.highlight('[data-edu-id="formula"]', ctx.cue('二次'), {dur: 0.8});
ctx.motion.highlight('[data-edu-id="formula"]', ctx.cue('抛物线'), {style: 'underline'});
```

### `spotlight(target, at, dur=1, {dim=0.25, pad=16}) -> Element`
从 `at` 秒起 `dur` 秒，目标以外的画面变暗到原来亮度的 `dim` 倍（0 到 1），淡入淡出各 0.15 秒。`pad` 是亮区比目标多出的像素。
```js
ctx.motion.spotlight('[data-edu-id="formula"]', ctx.cue('最低点'), 0.5);
```

### `circle(target, at, dur=0.8, {color='#c53030', width=5}) -> Element`
用 `dur` 秒手绘一个圈圈住目标，画完后一直保留。
```js
ctx.motion.circle(dot, ctx.cue('顶点'), 0.6);
```

### `drawPath(target, at, dur=1, {ease='power1.inOut'}) -> Element[]`
从路径起点开始，用 `dur` 秒把带描边（stroke）的图形逐步画出来，`at` 之前看不见。`target` 是组时（比如 `rough` 的结果），组里所有带描边的图形一起画。只画描边，填充不受影响。
```js
ctx.svg.insertAdjacentHTML('beforeend',
  '<path data-edu-id="arrow" d="M200,650 L500,650" stroke="#2f855a" stroke-width="6" fill="none"/>');
ctx.motion.drawPath(ctx.$('[data-edu-id="arrow"]')[0], 0.5, 1);
```

### `plot(fn, {xRange, yRange, box: {x, y, w, h}, samples=200, color, width=4, id}) -> {path, toScreen(x, y) -> {x, y}, box}`
在画布上的矩形 `box` 里画出 y = fn(x)。`xRange`、`yRange` 是数学坐标的 `[最小, 最大]`；超出 `yRange` 的部分剪掉，`fn` 返回非有限数的地方断开。`samples` 是采样段数。`toScreen` 把数学坐标换成画布坐标，用来放标注。只画曲线，坐标轴需要的话自己画。曲线一开始就是完整的，要逐步画出来用 `drawPath`。
```js
const graph = ctx.motion.plot(x => x * x - 2 * x - 3, {xRange: [-2, 4], yRange: [-5, 5],
  box: {x: 100, y: 80, w: 600, h: 400}, id: 'graph'});
ctx.motion.drawPath(graph.path, 0.2, 1.5);
const vertex = graph.toScreen(1, -4);  // {x: 400, y: 440}
```

### `follow(target, pathEl, at, dur=1, {rotate=false, ease='power1.inOut'})`
让目标沿 `<path>` 运动。目标要画在 (0,0) 处（例如 `cx="0" cy="0"` 的圆），运动时它的 (0,0) 落在路径上；`at` 之前它停在路径起点。`rotate: true` 时跟着路径方向转。
```js
ctx.svg.insertAdjacentHTML('beforeend', '<circle data-edu-id="ball" cx="0" cy="0" r="10" fill="#c53030"/>');
ctx.motion.follow(ctx.$('[data-edu-id="ball"]')[0], graph.path, 2, 2);
```

### `morph(fromPath, toShape, at, dur=1, {ease='power1.inOut'})`
把 `fromPath` 变成另一个形状。`fromPath` 必须是 `<path>`；`toShape` 是 path 的 `d` 字符串、SVG 元素或选择器（目标元素可以设成不显示）。
```js
ctx.svg.insertAdjacentHTML('beforeend',
  '<path data-edu-id="blob" d="M1000,500 L1100,500 L1100,600 L1000,600 Z" fill="#d69e2e"/>');
ctx.motion.morph('[data-edu-id="blob"]', 'M1050,490 C1110,490 1110,610 1050,610 C990,610 990,490 1050,490 Z', 1, 1);
```

### `splitText(target, at, {stagger=0.04}) -> Element[]`
文字从 `at` 秒起逐字出现：每个字用 0.2 秒淡入，相邻两字相隔 `stagger` 秒。可以用于 HTML 元素，或只有文字的 SVG `<text>`。返回每个字的元素。
```js
ctx.svg.insertAdjacentHTML('beforeend',
  '<text data-edu-id="caption" x="640" y="60" text-anchor="middle" font-size="40">二次函数的图像</text>');
ctx.motion.splitText(ctx.$('[data-edu-id="caption"]')[0], ctx.cue('二次'));
```

### `rough(kind, args, opts) -> Element`
用 Rough.js 画手绘风格的图形，返回加在 `ctx.svg` 里的 `<g>`。`kind` 和 `args`：`'line'` 是 `[x1, y1, x2, y2]`，`'rect'` 是 `[x, y, w, h]`，`'circle'` 是 `[cx, cy, r]`（r 是半径），`'path'` 是 `[d]`。`opts` 是 Rough.js 的选项（`stroke`、`strokeWidth`、`roughness`、`fill`、`fillStyle` 等）加上 `id`；`seed` 自动由 `ctx.random()` 生成，每次构建都一样。要一笔一笔画出来就交给 `drawPath`。
```js
const sketch = ctx.motion.rough('rect', [760, 420, 180, 90], {stroke: '#2f855a', roughness: 1.5, id: 'sketch'});
ctx.motion.drawPath(sketch, 1, 1.2);
```

### 画面手法
- `timeline(items, at, dur=2, {x=140, y=画布高-175, w=画布宽-280, color, id}) -> Element`：一条从 (x, y) 起、长 `w` 的时间线，用 `dur` 秒从左推到右，推到哪一项那一项就弹出来。每项是字符串或 `{time, label}`，`time` 写在点上方，`label` 写在下方（基线在 y+48 处，所以 y 不要超过 565）。
- `mapRoute(points, at, dur=2, {color='#c53030', width=5, id}) -> Element`：按顺序用 `dur` 秒画出经过 `points` 的路线，一个圆点走在路线最前面，经过的点依次显示。每个点是 `{x, y, label}` 或 `[x, y]`。
- `scaleCompare(items, at, dur=2, {x=200, y=画布高-160, w=画布宽-400, h=360, shape='bar', unit, id}) -> Element`：按数值大小对比，各项在 `dur` 秒里依次长出来。`y` 是底线，`h` 是最大一项的高度；`shape: 'circle'` 时圆的面积和数值成正比。每项是 `{label, value, color}`，`value` 必须大于 0，`unit` 接在数值后面显示。名称写在底线下方（基线在 y+40 处，所以 y 不要超过 575）。
```js
ctx.motion.timeline([{time: '1637', label: '笛卡尔'}, {time: '1687', label: '牛顿'}, '今天'], 0.5, 3, {y: 540});
ctx.motion.mapRoute([{x: 900, y: 300, label: '北京'}, [1000, 380], {x: 1150, y: 330, label: '上海'}], 1, 2);
ctx.motion.scaleCompare([{label: '地球', value: 1}, {label: '木星', value: 11}], 2, 2,
  {x: 800, y: 560, w: 400, h: 160, unit: '倍', shape: 'circle'});
```

### 高亮写法
要单独强调公式里的某一项：在公式里用 `\htmlClass{t-名字}{...}` 包住这一项，再在旁白说到它时 `highlight('.t-名字', ctx.cue('词'))`。同一段里类名不要重复，否则会一起亮。
```js
ctx.motion.tex('y=\\htmlClass{t-a}{x^2}-2x-3', {x: 900, y: 210, id: 'term'});
ctx.motion.highlight('.t-a', ctx.cue('顶点'));
```

## 段与段之间（接缝）

两段之间的接缝由程序处理，段代码不用管时间怎么接。
- `continue`（接续）：接缝期间画面停在上一段的最后一帧，下一段从这一帧原样开始。所以上一段结束时的画面就是下一段的开头：镜头、角色、`endState` 保留的元素都要和下一段的 `startState` 对得上，结尾不要把东西淡出或移走。
- `transition`（转场）：程序把上一段停在最后一帧、下一段停在第一帧，再用 `push`（推移）、`wipe`（擦除）、`zoom`（缩放穿越）、`fade`（淡入淡出）或 `match`（匹配剪辑）过渡。段代码不要自己画转场，开头不用淡入，结尾也不用淡出。
- `match`：两段里 `data-edu-match` 值相同的元素，从上一段结尾的位置和大小平滑移到下一段开头的位置和大小，其余内容在转场中点直接切换。每段里同一个值只给一个元素。
```js
ctx.svg.insertAdjacentHTML('beforeend',
  '<circle data-edu-id="sun" data-edu-match="sun" cx="1100" cy="120" r="50" fill="#d69e2e"/>');
```

## 检查用（段代码不要调用）

- `EduFilm.instantiate(id) -> {tl, duration, cue, cueEnd, state(t), highlights(), geometryDigest(), destroy()}`：在不可见的沙盒里重新构建一段。`state(t)` 定位到 t 秒后测量镜头和角色的实际值，返回 StageState；`highlights()` 返回本段每次 `highlight`、`spotlight`、`circle` 调用的记录 `{target, at, segment, kind, labels}`（`target` 是传入的选择器，传元素时写成它的 `data-edu-id` 选择器；`labels` 是目标自己或最近的祖先上的 `data-edu-id`）；`geometryDigest()` 是所有角色零件内部形状的哈希。检查用的夹具可以把函数放进 `ctx.__probes`，它们会出现在 `instantiate` 的结果上。
- `window.renderFrame(t)`：把整片定位到 t 秒。
- `window.studioReady`：字体和所有段都准备好后 resolve。
- `window.studioDiagnostics`：运行时发现的错误和违规，每条是 `{segment: 段 id 或 null, message: 中文说明}`。出错的段从此不再显示。
