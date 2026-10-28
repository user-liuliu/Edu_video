# 3D 可行性验证（渲染服务没有显卡）

日期：2026-10-28。检查在 `backend/tests/studio_render_checks.py` 的 3D 部分，主检查是 `test_three_segment_renders_deterministically_without_gpu`；夹具 `backend/tests/fixtures/studio/three_segment.js`：一个立方体加一个旋转的函数曲面 z = 0.6 sin(1.5x) cos(1.5y)，用 `MeshStandardMaterial`、环境光和平行光，所有绘制都在 `ctx.paint` 里。

## 结论：通过

3D 段在渲染镜像里能稳定渲染，一部片子里 3D 段的数量没有上限（实测 20 段）。第 2 部分的风格库可以包含"3D 物体与拆解"（不含 3D 角色）。

| 标准 | 结果 |
| --- | --- |
| 页面没有报错，画面不是空白 | 通过：没有页面报错，也没有诊断。21.0% 的像素不是背景色，只有字幕的同一帧是 3.8%；0 秒到 1.5 秒画面的平均变化是 17.0 |
| 同一时刻前后两次截图像素一致（`same_png`） | 通过：正向截 5 个时刻，再倒序截一遍，最后定位到别处再回来，6/6 次逐字节相同 |
| 1280×720 单帧平均耗时不超过 0.5 秒 | 通过：平均 0.136–0.143 秒，p95 0.155–0.185 秒，最大 0.224 秒（60 帧，计时包括 renderFrame、拷贝画面和 PNG 截图） |
| 3 秒片段能导出 mp4 | 通过：导出 3.0 秒、1280×720 的视频，耗时 20.9 秒。从 mp4 解码 1.5 秒处的一帧，21.5% 的像素有内容 |

其他检查：
- 单段夹具跑 `inspect_film` 的全部 6 项检查：0 条问题，用时 7.5 秒。
- 20 段 × 1 秒、每段都是 3D 的片子，`inspect_film` 跑全部检查：0 条问题，用时 38.5 秒。第 0、9、19 段（0.5、9.5、19.5 秒）的帧都有 18.4% 的像素有内容，只有字幕的帧是 0.8%。导出 20 秒 mp4 用时 98.8 秒，从视频解码第一段和最后一段的帧，都有 18.4% 的像素有内容。
- 两个 3D 段之间的擦除转场：转场中点左半边是后一段的画面（自己的浅蓝背景加红色立方体），右半边是前一段的画面（背景透明、金色曲面），正向和倒序定位得到的画面一致。
- 段代码自己 `new THREE.WebGLRenderer()` 会记一条诊断"第 段id 段：请用 ctx.three() 获取渲染器，不要自己创建 WebGLRenderer"，这一段从此不显示，其他段不受影响。构建时和 painter 里创建都测了。
- 共用的上下文丢失时记一条诊断"3D 渲染上下文丢失"（segment 为 null）。测法：在页面里再开 16 个 WebGL 上下文，让 Chromium 丢掉最早的那个。

## 设计：整片共用一个 WebGL 上下文

第一版是每段自己建 `WebGLRenderer`，评审时发现会出问题。Chromium 每页最多保留 16 个活动 WebGL 上下文，超过时直接丢掉最早的。影片启动时就构建所有段，每个 3D 段占一个上下文直到结束，检查时每段还要再构建一次。结果：
- 检查：9 段 3D 时 s0、s1 的上下文丢失，被误报成 s0"正向定位和倒序定位得到的画面不一样"。
- 导出：18 段 × 1 秒的 3D 片子能导出，也没有任何报错或诊断，但 s0 的画面是空的，只剩字幕（3.5% 的像素有内容，其他段是 21%）。

改法（`backend/app/studio/runtime/edu_motion.js`）：
- `ctx.three()` 返回 `{renderer, THREE}`。整页只有一个 `THREE.WebGLRenderer`，由运行时在第一次调用时创建：大小同舞台，`preserveDrawingBuffer: true`，`alpha: true`，`antialias: false`，像素比 1。它的画布不放在任何层里。
- 调用过 `ctx.three()` 的段，在自己的 `ctx.root` 里、`ctx.svg` 下面放一块 2D `<canvas>`。每次绘制这一段时，运行时先恢复这一段的渲染器设置并清空共用画布，然后跑这一段的 painter，最后把共用画布清空拷贝（`drawImage`）到这一段的 2D 画布上。这一段的设置是新建渲染器的默认值，加上构建时自己改的部分。各层按时间线顺序一个一个绘制，转场时两层各是各的画面。
- 页面上的 `THREE.WebGLRenderer` 换成了一个直接抛错的构造函数：记上面那条诊断，这一段按构建或绘制失败处理。运行时自己用的是原来的构造函数。
- `destroy()` 会释放这一段的 2D 画布，并 dispose 这一段画过的场景里的几何体、材质和贴图。最后一个用户释放时，运行时 dispose 渲染器并调用 `loseContext()`。
- `film_needs_webgl`：段代码或角色代码里出现 `THREE`（包括 `window.THREE`）或 `ctx.three(` 时为真。
- `API.md` 写了 `ctx.three()` 的用法和示例，并说明段代码不能自己创建渲染器。

拷贝画面让每帧多花约 0.02 秒（每帧平均从 0.114–0.118 秒变成 0.136–0.143 秒）。

## 测量方式

- 镜像用 `docker compose build renderer` 构建，用 `docker compose run --rm --no-deps renderer ...` 运行，没有挂载 studio 代码。容器里 `cpu.max = 200000 100000`（2 CPU），`memory.max = 2147483648`（2 GiB），和 Compose 的限制一样。检查脚本启动时还会用 `limit_cpu_affinity` 把进程限制在 2 个核上。
- Chromium 版本 155.0.8059.79（Debian trixie）。启动参数 `--use-angle=swiftshader --enable-unsafe-swiftshader`（`page.WEBGL_ARGS`）。WebGL 实际用的后端是 `ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero)), SwiftShader driver)`。
- "像素有内容"指和舞台背景色相差超过 24。对照帧是同一部片子把段代码换成空的、只剩字幕的那一帧，要求 3D 帧的比例至少是对照帧的 3 倍。

## 注意事项

1. 不加这两个启动参数时，这个版本的 Chromium 也会自动改用 SwiftShader，画面一样。仍然保留参数，因为新版 Chrome 正在取消自动改用，不加参数以后可能拿不到 WebGL。
2. 只测了中等复杂度的场景：约 4.6 千个三角形、1 盏平行光，没有阴影、后处理和贴图。阴影、大量网格或高分段的曲面会更慢，风格库里应该限制几何体的数量，不用阴影贴图。
3. 逐字节一致只在同一个镜像、同一个 Chromium 版本里验证过。换 Chromium 或 SwiftShader 版本后像素可能变化，但同一次导出里的结果仍然一致。抗锯齿是关着的，打开 MSAA 没有测。
4. 导出比 SVG 慢：3 秒的 3D 片段 20.9 秒，20 秒的 3D 片子 98.8 秒（每秒影片约 5 秒），4.2 秒的 SVG 片子 13.4 秒。整片较长时注意 `RENDER_TIMEOUT`。
5. 渲染器的设置只恢复 `edu_motion.js` 里 `FLAGS` 列出的这些，以及清屏颜色、裁剪平面、阴影开关和阴影类型、视口、剪刀区域和大小。别的渲染器状态如果在 painter 里改了，可能会影响后面的段。API.md 已经要求不要改渲染器的大小和像素比，也不要用 `setAnimationLoop`。
