# 3D 可行性验证（渲染服务没有显卡）

日期：2026-10-28。检查：`backend/tests/studio_render_checks.py::test_three_segment_renders_deterministically_without_gpu`，夹具 `backend/tests/fixtures/studio/three_segment.js`（立方体 + 旋转的函数曲面 z = 0.6 sin(1.5x) cos(1.5y)，`MeshStandardMaterial`，环境光 + 平行光，1280×720，`preserveDrawingBuffer: true`，`antialias: false`，`setPixelRatio(1)`，所有绘制都在 `ctx.paint` 里）。

## 结论：通过

单段、少量 3D 段的片子可以在渲染镜像里稳定渲染。第 2 部分的风格库可以包含"3D 物体与拆解"（不含 3D 角色），但要先处理下面"注意事项"第 1 条。

| 标准 | 结果 |
| --- | --- |
| 页面没有报错，画面不是空白 | 通过：无 pageerror、无诊断；21% 的像素不是背景色；0 秒到 1.5 秒画面平均变化 17.0 |
| 同一时刻前后两次截图像素一致（`same_png`） | 通过：正向 5 个时刻、倒序再看一遍、换到别处再回来，6/6 次逐字节完全相同 |
| 1280×720 单帧平均耗时 ≤ 0.5 秒 | 通过：平均 0.114–0.118 秒，p95 0.137 秒，最大 0.161 秒（60 帧，renderFrame + PNG 截图） |
| 3 秒片段能导出 mp4 | 通过：导出 3.0 秒、1280×720，耗时 18.2–19.0 秒（含启动浏览器和 ffmpeg 编码） |

另外 `inspect_film` 跑全部 6 项检查，0 条问题，耗时 7.5 秒。

## 测量方式

- 镜像：`docker compose build renderer`，`docker compose run --rm --no-deps renderer ...`。容器里 `cpu.max = 200000 100000`（2 CPU），`memory.max = 2147483648`（2 GiB），即 Compose 的限制；检查脚本启动时再用 `limit_cpu_affinity` 限到 2 个核。
- Chromium 155.0.8059.79（Debian trixie）。启动参数 `--use-angle=swiftshader --enable-unsafe-swiftshader`（`page.WEBGL_ARGS`）。WebGL 实际后端：`ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero)), SwiftShader driver)`。
- 何时带这些参数：`page.film_needs_webgl(html)`，段代码或角色代码（内联 `<script>`，不含 three.js 本身和影片 JSON）里出现 `THREE` 时为真；`inspect.py` 和 `export.py` 都用它决定 `studio_page(..., webgl=...)`。

## 注意事项

1. **WebGL 上下文上限（第 2 部分必须处理）**：Chromium 每页最多 16 个活动 WebGL 上下文。每个 3D 段启动时占 1 个，`inspect_film` 每段再 `EduFilm.instantiate` 一次又占 1 个，`destroy()` 只移除元素，上下文要等垃圾回收才释放。实测 8 段 3D 的片子检查无问题；9 段时控制台报 "Too many active WebGL contexts. Oldest context will be lost."，s0、s1 的画布失去上下文，检查报成 s0 的"正向定位和倒序定位得到的画面不一样"——原因说错了，模型会被误导。导出不做 instantiate，估计到 16 段 3D 才会遇到，而且失去上下文的画布只是空白，不会有诊断。已验证的修法：段销毁时对其中的 WebGL 画布调用 `WEBGL_lose_context.loseContext()`，9 段时启动画布全部保持正常。另外运行时最好在画布 `webglcontextlost` 时记一条诊断。
2. 不加这两个参数时，这个版本的 Chromium 也会自动退回 SwiftShader，画面相同。仍然保留参数：新版 Chrome 正在取消自动退回，不加参数以后可能直接拿不到 WebGL。
3. 只测了一个中等复杂度的场景（约 5 千个三角形、1 盏平行光、无阴影、无后处理、无贴图）。阴影、大量网格或高分段曲面会更慢；风格库里应限制几何体数量，不用阴影贴图。
4. 逐字节一致只在同一镜像、同一 Chromium 版本内验证过；换 Chromium 或 SwiftShader 版本后像素可能变化（不影响同一次导出内的确定性）。`antialias` 关着；打开 MSAA 未测。
5. 导出耗时约为普通 SVG 片段的 1.3 倍（4.2 秒的 SVG 片子 13.4 秒，3 秒的 3D 片段 18–19 秒），整片较长时注意 `RENDER_TIMEOUT`。
