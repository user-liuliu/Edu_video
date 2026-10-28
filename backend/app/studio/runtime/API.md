# 动效库接口（EduStudio）

单位：时间一律是**秒**（从本段 0 秒算起），坐标和长度是**像素**（画布左上角为原点，默认 1280×720），角度是**度**（顺时针为正，读回的值在 -180 到 180 之间）。

## 规则

- 每一帧只由时间决定。所有动画都放在 `ctx.tl` 上，运行时只通过 seek 定位，不会自己播放。
- `build(ctx)` 同步执行，不能用定时器、`requestAnimationFrame`、`Math.random`、`Date`、网络请求。需要随机数用 `ctx.random()`。
- 不要用 `gsap.to/from/timeline` 直接建动画（不会播放，会记一条诊断）；用 `ctx.tl.to/from/fromTo/set`。`gsap.set` 可以用，会立即生效，作为本段的初始状态。
- Canvas 或 three.js 只能在 tween 的 `onUpdate` 里按当前进度重画整张画面。每块画布只由一个 tween 来画，这个 tween 每次都要把整块画布重画一遍。
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

## 检查用（段代码不要调用）

- `EduFilm.instantiate(id) -> {tl, duration, cue, cueEnd, state(t), geometryDigest(), destroy()}`：在不可见的沙盒里重新构建一段。`state(t)` 定位到 t 秒后测量镜头和角色的实际值，返回 StageState；`geometryDigest()` 是所有角色零件内部形状的哈希。
- `window.renderFrame(t)`：把整片定位到 t 秒。
- `window.studioReady`：字体和所有段都准备好后 resolve。
- `window.studioDiagnostics`：运行时发现的错误和违规（中文字符串）。
