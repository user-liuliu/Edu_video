# 新链路 · 第 1 部分：渲染底座 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为对话式新链路搭好底座：按段写的动画能够被确定性地播放、检查、截帧、导出成 mp4，配音带逐词时间。

**Architecture:** 新代码全部放在新包 `backend/app/studio/`，不改旧链路 `backend/app/videos/` 的行为。每段动画是一段函数体代码，由 Python 包进 `EduStudio.defineSegment(id, function(ctx){...})`，代码在一条暂停的 GSAP 时间线上安排动画。整片 HTML 由 Python 拼装，靠 `window.renderFrame(t)` 定位到任意时刻。离线库统一从固定路径 `/studio-runtime/<digest>/` 加载：渲染服务用 Playwright 路由从本地文件返回这些请求，其他请求一律拦截。

**Tech Stack:** Python 3.12、FastAPI、Pydantic 2、Playwright Chromium、ffmpeg、edge-tts 7.3.1；GSAP 3（含 DrawSVG、MorphSVG、MotionPath、SplitText）、KaTeX、three.js、Rough.js；字体 Noto Sans SC、霞鹜文楷（woff2）；esbuild 只用于打包第三方库。

**Spec:** `docs/superpowers/specs/2026-10-28-conversational-video-pipeline-design.md`（第 7、8 节是本计划的主要依据）

## 整体拆分（5 份计划，按顺序实施）

1. **渲染底座**（本计划）：离线库、动效库、角色接口、整片拼装与转场、Edge 逐词配音、渲染服务新接口、3D 可行性验证、演示片。
2. **生成核心**：风格卡（6 种）、各环节提示词、脚本 → 角色设计 → 配音 → 分段动画 → 两层审核与修复 → 降级 → 拼片。用命令行从一份固定大纲跑出成片，两个验收题目（孔融让梨、二次函数）在这一部分通过。
3. **对话后端**：会话与消息数据表、追问（最多 7 轮）、大纲（整合资料和联网搜索）、风格推荐与 3 个样片、脚本修改的前后对比与重做范围、计费（整片 10、每段 4、自动修复和样片免费）、管理员给指定用户开通。
4. **对话前端**：左边对话、右边展示，右边按阶段切换内容，点片段引用到输入框，播放器标出降级镜头。
5. **角色库与后台**：角色自动提交审核、管理员审核入库、按"风格 + 名字"复用；"试用期免费"开关。

依赖关系：2 依赖 1；3 依赖 2；4 依赖 3；5 依赖 2 和 3。每一部分开始前，先按该部分的实际需要写出详细计划。

## Global Constraints

- 新代码只能放在 `backend/app/studio/`、`backend/tests/test_studio_*.py`、`backend/tests/studio_*_checks.py`、`backend/tests/fixtures/studio/`、`tools/studio-vendor/`，以及渲染服务的新增部分。旧链路 `backend/app/videos/` 只允许 import 其中的工具函数，不得修改，已有测试必须全部保持通过。
- 画布默认 1280×720，30 fps。底部是字幕区，高度为画布高度 × 95/720（720 高时为 y=625..720），动画里的文字不得进入字幕区。
- 同一时刻永远画出同一帧。段代码里禁止出现：`setTimeout`、`setInterval`、`requestAnimationFrame`、`Date.now`、`new Date`、`performance.now`、`Math.random`（要随机数时用 `ctx.random()`）、`fetch`、`XMLHttpRequest`、`WebSocket`、`EventSource`、`import(`、`eval`、`new Function`、`localStorage`、`sessionStorage`、`indexedDB`、`window.`、`parent.`、`top.`、`document.querySelector`、`document.body`、`gsap.ticker`、`gsap.globalTimeline`。
- 运行时不联网：所有库和字体离线打包，只通过 `/studio-runtime/<digest>/` 加载。
- 许可：GSAP 使用 Standard No-Charge License，禁止用于与 Webflow 竞争的无代码可视化动画编辑器；KaTeX、three.js、Rough.js 为 MIT 许可；字体为 SIL OFL 1.1。每个文件的版本、许可和 sha256 都记进 manifest。
- 配音只用 Edge，全片一位讲述者。
- 提交信息格式：中文标题 `<type>: <简述>`，正文逐条列出改动，末尾加 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`。只在当前功能分支上提交，不推送。
- 纯 Python 测试：`cd backend && uv run --env-file ../.env pytest tests/test_studio_*.py -q`。如果出现 `.venv\lib64 拒绝访问`，先问用户能否重建 `backend/.venv`。
- 浏览器检查在渲染镜像里运行（沿用 README 里的做法）：
  `docker compose build renderer && docker compose run --rm --no-deps -v "$PWD/backend/tests:/checks:ro" -e HOME=/tmp -e PYTHONPATH=/render renderer python /checks/studio_runtime_checks.py`

## Review Focus

- 旁白里有数字、英文或公式符号（比如"x²−2x−3"读作"x 的平方减 2x 减 3"），Edge 返回的词和原文对不上时，逐词对齐不能崩溃，也不能把时间错位到别的词上。确实对不上的高亮词要报出词和段号，不能悄悄当成 0 秒。（Task 2：`test_align_words_handles_digits_and_latin`）
- 同一段里要高亮的词出现了两次，要能按第几次出现来指定，默认取第一次。（Task 2：`test_cue_returns_word_span_and_picks_nth_occurrence`）
- 某一段代码在构建或定位时抛出异常，要报出这一段的 id 和错误信息，不能让整片空白，也不能悄悄跳过这一段。（Task 6：`test_broken_segment_is_reported_by_id`）
- 一段的时长比相邻的转场还短，或者第一段、最后一段没有对应的接缝，拼装时要给出明确的错误。（Task 3：`test_transition_longer_than_segment_rejected`）
- 中文长句或公式超出画面、压到字幕区时，检查要报出是哪个元素、在哪个时刻。（Task 7：`test_text_in_caption_zone_reported`）

---

### Task 1: 离线库打包

**Files:**
- Create: `tools/studio-vendor/package.json`、`tools/studio-vendor/build.mjs`、`tools/studio-vendor/README.md`
- Create: `backend/app/studio/__init__.py`、`backend/app/studio/runtime/__init__.py`、`backend/app/studio/runtime/assets.py`
- Create（打包产物，提交进仓库）：`backend/app/studio/runtime/vendor/**`、`backend/app/studio/runtime/vendor/manifest.json`、`backend/app/studio/runtime/vendor/NOTICE.md`
- Test: `backend/tests/test_studio_assets.py`

**Interfaces:**
- Produces: `VENDOR_DIR: Path`；`VENDOR_FILES: tuple[str, ...]`（下面列出的固定文件名）；`runtime_files() -> list[Path]`（vendor 文件，加上 Task 4、6 创建的 `edu_motion.js`、`film_runtime.js`，存在才列入）；`runtime_digest() -> str`（对 `runtime_files()` 按文件名排序后，逐个哈希"文件名 + 内容"，得到 64 位十六进制 sha256）；`runtime_url(name: str) -> str`，返回 `/studio-runtime/{runtime_digest()}/{name}`；`read_runtime_file(name: str) -> bytes`，名字不在 `runtime_files()` 里时抛 `KeyError`。

`VENDOR_FILES` 固定为：`gsap.min.js`、`DrawSVGPlugin.min.js`、`MorphSVGPlugin.min.js`、`MotionPathPlugin.min.js`、`SplitText.min.js`、`katex.min.js`、`katex.min.css`、`three.iife.js`（全局变量 `THREE`）、`rough.js`（全局变量 `rough`）、`fonts.css`。另外还有 `fonts/` 和 `katex-fonts/` 两个目录下的 woff2 文件。

- [ ] **Step 1: 写失败的测试**

```python
from app.studio.runtime import assets

def test_manifest_covers_every_vendor_file_with_matching_hash():
    manifest = json.loads((assets.VENDOR_DIR / 'manifest.json').read_text('utf-8'))
    on_disk = {p.relative_to(assets.VENDOR_DIR).as_posix() for p in assets.VENDOR_DIR.rglob('*')
               if p.is_file() and p.name not in ('manifest.json', 'NOTICE.md')}
    assert set(manifest['files']) == on_disk
    for name, entry in manifest['files'].items():
        assert entry['sha256'] == hashlib.sha256((assets.VENDOR_DIR / name).read_bytes()).hexdigest()
        assert entry['license'] in ('GSAP-Standard-No-Charge', 'MIT', 'OFL-1.1')
        assert entry['version'] and entry['package']

def test_required_vendor_files_present_and_digest_stable():
    for name in assets.VENDOR_FILES:
        assert (assets.VENDOR_DIR / name).is_file(), name
    assert re.fullmatch(r'[0-9a-f]{64}', assets.runtime_digest())
    assert assets.runtime_digest() == assets.runtime_digest()
    assert assets.runtime_url('gsap.min.js') == f'/studio-runtime/{assets.runtime_digest()}/gsap.min.js'

def test_read_runtime_file_rejects_unknown_and_traversal():
    for bad in ('../assets.py', 'nope.js', '/etc/passwd'):
        with pytest.raises(KeyError):
            assets.read_runtime_file(bad)
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && uv run --env-file ../.env pytest tests/test_studio_assets.py -q`
Expected: FAIL，报 `ModuleNotFoundError: app.studio`

- [ ] **Step 3: 写打包脚本，生成 vendor 目录**

`package.json` 固定写死以下依赖的确切版本，取打包当天的最新稳定版，`package-lock.json` 一起提交：`gsap@^3.13`、`katex`、`three`、`roughjs`、`@fontsource/noto-sans-sc`（400、700 两种字重）、`lxgw-wenkai-webfont`（400 字重）、`esbuild`。

`build.mjs` 的工作：
- 复制 GSAP 的 dist 文件、KaTeX 的 `katex.min.js` 和 `katex.min.css`（字体文件放进 `katex-fonts/`，并改写 css 里的路径）、Rough.js 的 `bundled/rough.js`。
- 用 esbuild 把 `three` 打成 IIFE，`globalName: 'THREE'`。
- 把字体复制进 `fonts/`，生成 `fonts.css`。`font-family` 固定为 `"Noto Sans SC"` 和 `"LXGW WenKai"`，保留原包按 unicode-range 拆分的子集。
- 生成 `manifest.json`，格式为 `{"files":{"<相对路径>":{"package","version","license","sha256"}}}`。
- 生成 `NOTICE.md`，列出每个包的许可，以及 GSAP 许可里的禁用条款。

README 写明重新打包的命令：`cd tools/studio-vendor && npm ci && node build.mjs`。

- [ ] **Step 4: 实现 `assets.py`，运行测试确认通过**

Run: `cd backend && uv run --env-file ../.env pytest tests/test_studio_assets.py -q`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add tools/studio-vendor backend/app/studio backend/tests/test_studio_assets.py
git commit  # 标题：feat(studio): 打包新链路离线动画库与字体
```

### Task 2: Edge 逐词配音

**Files:**
- Create: `backend/app/studio/speech.py`
- Test: `backend/tests/test_studio_speech.py`

**Interfaces:**
- Consumes: `app.videos.edge_speech` 里的 `_decode(data) -> bytes`、`available() -> bool`、`ATTEMPTS`、`MAX_STREAM_SECONDS`（只 import，不修改）。
- Produces:
  - `VOICES: tuple[dict, ...]`：每项是 `{'speaker_id': 'edge:<ShortName>', 'label': '中文名'}`。至少包含 `zh-CN-YunxiNeural`（云希·男声，默认）、`zh-CN-XiaoxiaoNeural`（晓晓·女声）、`zh-CN-YunjianNeural`（云健·男声）、`zh-CN-XiaoyiNeural`（晓伊·女声）、`zh-CN-YunyangNeural`（云扬·男声）。写进代码前，用 `edge-tts --list-voices` 确认这些音色仍然可用。
  - `@dataclass(frozen=True) class Word: text: str; start: float; end: float; char_start: int; char_end: int`。时间单位是秒；`char_*` 是这个词在原文中的位置，左闭右开。
  - `@dataclass(frozen=True) class WordNarration: audio: bytes; duration: float; words: list[Word]`，音频是 48 kHz 单声道 16 位 WAV。
  - `align_words(text: str, events: list[dict]) -> list[Word]`：events 是 Edge 返回的 `WordBoundary` 事件，`offset` 和 `duration` 以 100 纳秒为单位。
  - `cue(words: list[Word], text: str, phrase: str, occurrence: int = 1) -> tuple[float, float]`：返回第 `occurrence` 次出现的 `phrase` 覆盖到的那些词的开始和结束时间。找不到时抛 `ValueError('高亮词"<phrase>"在旁白中找不到第 <n> 处')`。
  - `sentence_captions(text: str, words: list[Word]) -> list[dict]`：按 `。！？!?；;` 切句，每句一项 `{'text', 'start', 'end'}`，时间取这句里的词。
  - `async synthesize_words(text: str, *, speaker: str, rate: str = '-5%') -> WordNarration`：`speaker` 不在 `VOICES` 里时抛 `ValueError('所选配音音色不可用，请重新选择')`。文本为空或超过 2000 字时抛 `ValueError('单段旁白长度不符合要求')`。

对齐算法：在原文里维护一个游标，按顺序处理事件。对每个事件，从游标开始查找它的 `text`。找不到时，把原文和事件文本都去掉空白和标点再比较；还找不到时，按"阿拉伯数字 ↔ 中文数字"的读法比较（比如 `2` ↔ `二`/`两`）。三种方式都失败，就抛 `ValueError('配音逐词时间与旁白对不上：<事件文本>')`。

- [ ] **Step 1: 写失败的测试**

测试数据取自 2026-10-28 的实测，每项是 `(开始秒, 时长秒, 词)`。原文：`二次函数的图像是一条抛物线，顶点就是它的最低点。`

```python
EVENTS = [ev(0.10,.35,'二次'), ev(.46,.33,'函数'), ev(.79,.09,'的'), ev(.89,.51,'图像'),
          ev(1.50,.19,'是'), ev(1.70,.24,'一条'), ev(1.96,.56,'抛物线'), ev(2.91,.44,'顶点'),
          ev(3.38,.14,'就'), ev(3.51,.09,'是'), ev(3.61,.11,'它'), ev(3.73,.07,'的'), ev(3.83,.55,'最低点')]
# ev(s, d, t) 返回 {'type':'WordBoundary','offset':round(s*1e7),'duration':round(d*1e7),'text':t}

def test_align_words_maps_events_to_text_positions():
    words = align_words(TEXT, EVENTS)
    assert len(words) == 13
    assert TEXT[words[7].char_start:words[7].char_end] == '顶点'
    assert (words[7].start, words[7].end) == pytest.approx((2.91, 3.35))

def test_cue_returns_word_span_and_picks_nth_occurrence():
    words = align_words(TEXT, EVENTS)
    assert cue(words, TEXT, '顶点') == pytest.approx((2.91, 3.35))
    assert cue(words, TEXT, '抛物线，顶点') == pytest.approx((1.96, 3.35))
    assert cue(words, TEXT, '的', 2) == pytest.approx((3.73, 3.80))
    with pytest.raises(ValueError, match='高亮词"开口"'):
        cue(words, TEXT, '开口')

def test_align_words_handles_digits_and_latin():
    text = '把2代入y等于x加1。'
    events = [ev(0,.2,'把'), ev(.2,.2,'二'), ev(.4,.3,'代入'), ev(.7,.2,'y'), ev(.9,.3,'等于'),
              ev(1.2,.2,'x'), ev(1.4,.2,'加'), ev(1.6,.2,'一')]
    words = align_words(text, events)
    assert text[words[1].char_start:words[1].char_end] == '2'
    assert cue(words, text, 'x加1') == pytest.approx((1.2, 1.8))
    with pytest.raises(ValueError, match='对不上'):
        align_words('甲乙。', [ev(0,.2,'丙')])

def test_sentence_captions_split_on_punctuation():
    text = TEXT + '它在对称轴上。'
    words = align_words(text, EVENTS + [ev(4.6,.2,'它'), ev(4.8,.2,'在'), ev(5.0,.6,'对称轴'), ev(5.6,.2,'上')])
    caps = sentence_captions(text, words)
    assert [c['text'] for c in caps] == [TEXT, '它在对称轴上。']
    assert (caps[0]['start'], caps[0]['end']) == pytest.approx((0.10, 4.38))

async def test_synthesize_words_uses_word_boundary_and_validates_speaker(monkeypatch, mp3):
    # 和 test_edge_speech.py 一样，mp3 夹具由 ffmpeg 生成；
    # 用 monkeypatch 替换 speech._stream_words，让它返回 (mp3, EVENTS)
    result = await synthesize_words(TEXT, speaker='edge:zh-CN-YunxiNeural')
    assert result.audio[:4] == b'RIFF' and len(result.words) == 13
    with pytest.raises(ValueError, match='音色不可用'):
        await synthesize_words(TEXT, speaker='system:zh-CN')
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && uv run --env-file ../.env pytest tests/test_studio_speech.py -q`
Expected: FAIL，报 `ImportError`

- [ ] **Step 3: 实现 `speech.py`**

`_stream_words(text, voice, rate)` 调用 `edge_tts.Communicate(..., boundary='WordBoundary')` 收集音频和事件，重试和超时规则照抄 `edge_speech._stream_once`。解码复用 `edge_speech._decode`。

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend && uv run --env-file ../.env pytest tests/test_studio_speech.py tests/test_edge_speech.py -q`
Expected: 全部通过，旧的 Edge 测试不受影响

- [ ] **Step 5: 提交**（标题：`feat(studio): Edge 配音返回逐词时间并支持多音色`）

### Task 3: 段的约定、静态检查与整片拼装

**Files:**
- Create: `backend/app/studio/contract.py`、`backend/app/studio/lint.py`、`backend/app/studio/film.py`
- Test: `backend/tests/test_studio_contract.py`、`backend/tests/test_studio_film.py`

**Interfaces:**
- Consumes: Task 1 的 `runtime_url`、`runtime_digest`；Task 2 的 `Word`。
- Produces（`contract.py`，所有模型都设 `extra='forbid'`）：
  - `ActorState(x: float, y: float, scale: float = 1, flip: bool = False, pose: dict[str, float] = {})`。`pose` 的键是零件名，值是旋转角度，单位为度。
  - `Camera(x: float = 640, y: float = 360, zoom: float = 1)`
  - `StageState(camera: Camera = Camera(), actors: dict[str, ActorState] = {}, keep: list[str] = [])`。`keep` 记录画面上要保留到下一段的元素标签。
  - `Seam(kind: Literal['continue','transition'], transition: Literal['push','wipe','zoom','match','fade'] | None = None, duration: float)`。`continue` 的时长是 0–0.6 秒的自然停顿；`transition` 的时长是 0.3–1.5 秒，并且必须写 `transition`。
  - `Highlight(phrase: str, occurrence: int = 1, target: str)`。`target` 是段代码里 `data-edu-id` 的值。
  - `Segment(id: str (^[a-z0-9-]{1,40}$), code: str (≤200_000 字符), duration: float (0.5–120), words: list[Word], narration: str, highlights: list[Highlight] = [], start_state: StageState, end_state: StageState)`
  - `state_diff(a: StageState, b: StageState) -> list[str]`：返回所有差异的中文描述，空列表表示一致。容差：位置 2 px、缩放 0.01、角度 2°；`flip`、角色集合、`keep` 必须完全相同。
- Produces（`lint.py`）：`lint_segment(code: str) -> list[str]`。逐条匹配 Global Constraints 里的禁用写法，每命中一条返回 `'<写法> 不允许使用'`。
- Produces（`film.py`）：
  - `class FilmError(ValueError)`
  - `timeline(segments: list[Segment], seams: list[Seam]) -> list[dict]`：返回每段的 `{'id','start','end'}` 和每个接缝的 `{'seam':i,'start','end','kind','transition'}`，按时间排序，接缝夹在两段之间。
  - `film_duration(segments, seams) -> float`
  - `build_film_html(segments: list[Segment], seams: list[Seam], *, characters_code: str = '', style_css: str = '', width: int = 1280, height: int = 720) -> str`
  - `assemble_audio(clips: list[bytes], segments: list[Segment], seams: list[Seam]) -> bytes`：在各段音频之间插入长度等于接缝时长的静音。某段音频时长和 `segment.duration` 相差超过 1/30 秒时，抛 `FilmError('第 <id> 段配音时长与动画不一致')`。
  - `film_captions(segments, seams) -> list[dict]`：用 Task 2 的 `sentence_captions` 生成字幕，再加上每段的起始偏移。

`build_film_html` 的规则：
- 先对每段运行 `lint_segment`，有问题就抛 `FilmError('第 <id> 段：' + '；'.join(问题))`。
- 检查 `len(seams) == len(segments) - 1`。
- 每个接缝的时长不能超过前后两段中较短那段时长的一半，否则抛 `FilmError('接缝 <i> 比相邻片段还长')`。
- 对每个 `continue` 接缝，用 `state_diff(前段.end_state, 后段.start_state)` 检查，有差异就抛 `FilmError`。

输出的 HTML 包含：
- 一条 CSP meta：`default-src 'none'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; font-src 'self'; img-src data:; connect-src 'none'`。CSP 的来源表达式不能只写路径，所以这里用 `'self'`；实际能加载什么，由页面路由只放行 `/studio-runtime/<digest>/` 来保证（见 Task 4 的 `studio_page`）。
- 按顺序加载 `runtime_url()` 里的 vendor 脚本和样式、`edu_motion.js`、`film_runtime.js`
- `<style>` 里放 `style_css`，`<script>` 里放 `characters_code`
- 每段一个 `<script>EduStudio.defineSegment("<id>", function(ctx){\n<code>\n});</script>`
- `<script type="application/json" id="edu-studio-film">`，内容是 `{timeline, duration, width, height, segments:[{id,duration,words,narration,highlights,start_state,end_state}], seams, captions}`
- 最后一行 `<script>EduFilm.boot()</script>`

- [ ] **Step 1: 写失败的测试**

```python
def test_lint_rejects_clock_random_network_and_global_dom():
    for bad in ('setTimeout(f,1)', 'Date.now()', 'Math.random()', 'fetch("/x")',
                'document.querySelector("a")', 'window.foo=1', 'gsap.ticker.add(f)', 'eval("1")'):
        assert lint_segment(bad), bad
    assert lint_segment('ctx.tl.to(ctx.$("#a"),{x:10,duration:1},ctx.cue("顶点"))') == []

def test_state_diff_tolerances():
    a = StageState(actors={'kr': ActorState(x=100, y=600)})
    assert state_diff(a, StageState(actors={'kr': ActorState(x=101.5, y=600)})) == []
    assert state_diff(a, StageState(actors={'kr': ActorState(x=110, y=600)}))
    assert state_diff(a, StageState(actors={'kr': ActorState(x=100, y=600, flip=True)}))
    assert state_diff(a, StageState())

def test_timeline_places_seam_gaps_between_segments():
    segs = [seg('a', 4.0), seg('b', 3.0)]
    t = timeline(segs, [Seam(kind='transition', transition='push', duration=0.8)])
    assert [(x.get('id') or x['kind'], x['start'], x['end']) for x in t] == [
        ('a', 0, 4.0), ('transition', 4.0, 4.8), ('b', 4.8, 7.8)]
    assert film_duration(segs, [Seam(kind='continue', duration=0.3)]) == pytest.approx(7.3)

def test_build_film_html_wraps_segments_and_embeds_runtime():
    html = build_film_html([seg('a', 2), seg('b', 2)], [Seam(kind='continue', duration=0.2)])
    assert 'EduStudio.defineSegment("a", function(ctx){' in html
    assert runtime_url('gsap.min.js') in html and "connect-src 'none'" in html
    data = json.loads(re.search(r'id="edu-studio-film">(.*?)</script>', html, re.S)[1])
    assert data['duration'] == pytest.approx(4.2)

def test_build_film_rejects_lint_mismatch_and_bad_seams():
    with pytest.raises(FilmError, match='第 b 段.*setInterval'):
        build_film_html([seg('a', 2), seg('b', 2, code='setInterval(f,9)')], [Seam(kind='continue', duration=0)])
    moved = seg('b', 2, start=StageState(actors={'kr': ActorState(x=300, y=600)}))
    with pytest.raises(FilmError, match='接缝'):
        build_film_html([seg('a', 2, end=StageState(actors={'kr': ActorState(x=100, y=600)})), moved],
                        [Seam(kind='continue', duration=0)])
    with pytest.raises(FilmError):
        build_film_html([seg('a', 2)], [Seam(kind='continue', duration=0)])

def test_transition_longer_than_segment_rejected():
    with pytest.raises(FilmError, match='接缝 0 比相邻片段还长'):
        build_film_html([seg('a', 1.0), seg('b', 3)], [Seam(kind='transition', transition='wipe', duration=0.9)])

def test_assemble_audio_inserts_silence_and_checks_lengths():
    segs = [seg('a', 1.0), seg('b', 2.0)]
    out = assemble_audio([wav(1.0), wav(2.0)], segs, [Seam(kind='transition', transition='fade', duration=0.5)])
    assert wav_seconds(out) == pytest.approx(3.5, abs=1/48000)
    with pytest.raises(FilmError, match='第 b 段配音时长'):
        assemble_audio([wav(1.0), wav(1.5)], segs, [Seam(kind='continue', duration=0)])
```

`seg(id, duration, code='', start=StageState(), end=StageState())`、`wav(seconds)` 和 `wav_seconds(bytes)` 是测试文件里的辅助函数，`words` 用空列表。

- [ ] **Step 2: 运行测试，确认失败**
Run: `cd backend && uv run --env-file ../.env pytest tests/test_studio_contract.py tests/test_studio_film.py -q`
Expected: FAIL（`ImportError`）

- [ ] **Step 3: 实现 `contract.py`、`lint.py`、`film.py`**

- [ ] **Step 4: 运行测试，确认通过**（同 Step 2 的命令，Expected: 全部通过）

- [ ] **Step 5: 提交**（标题：`feat(studio): 段约定、静态检查与整片拼装`）

### Task 4: 动效库核心：时间线、词时间、镜头、角色、状态

**Files:**
- Create: `backend/app/studio/runtime/edu_motion.js`
- Create: `backend/app/studio/runtime/film_runtime.js`，本任务只做最小版本：`EduFilm.boot()` 读取 `#edu-studio-film`，把各段按时间线依次放进同一条主时间线，各段之间没有转场，到了时间就直接切换图层。`window.renderFrame(t)` 把主时间线定位到 t。`window.studioReady` 是一个 Promise，等字体加载完成、所有段构建完成后才 resolve。`window.studioDiagnostics` 是诊断信息数组，运行时遇到的错误和违规都记在这里。转场、字幕和逐段的错误隔离在 Task 6 补上。
- Create: `backend/app/studio/runtime/API.md`。这是动效库接口说明的唯一一份，第 2 部分的动画提示词直接引用它，不再在别处复述。
- Create: `backend/app/studio/page.py`：创建浏览器页面的公共函数，检查脚本和渲染服务共用。
- Create: `backend/tests/studio_runtime_checks.py`（unittest，在渲染镜像里运行）、`backend/tests/fixtures/studio/`
- Modify: `renderer/Dockerfile`，加一行 `COPY backend/app/studio /render/app/studio`

**Interfaces:**
- Consumes: Task 1 的 `read_runtime_file`、`runtime_digest`；Task 3 的 `build_film_html`、`Segment`、`StageState`。
- Produces（`page.py`）：`async with studio_page(html: str, *, width=1280, height=720, webgl=False) as (page, errors)`。页面地址是 `http://studio.local/film.html`，内容就是传入的 `html`，这样 `'self'` 和相对路径都能指向同一个源。路由规则：`/studio-runtime/<当前 digest>/<name>` 由 `read_runtime_file` 返回内容，其余请求，包括其他 digest 和其他主机，一律 abort。`errors` 收集 `pageerror` 事件。进入上下文前会先等待 `window.studioReady`。`webgl=True` 时，启动参数加上 `--use-angle=swiftshader --enable-unsafe-swiftshader`。
- Produces（JS 全局对象 `EduStudio`，在 `API.md` 里写成接口文档）：
  - `EduStudio.defineSegment(id, build)`：注册一段。`build(ctx)` 同步执行，只能往 `ctx.tl` 上安排动画。
  - `EduStudio.defineCharacter(name, factory)`：`factory(svgGroup, params)` 画出各个零件，每个零件是一个 `<g data-part="名字" data-pivot="x,y">`。
  - `ctx` 的成员：
    - 舞台：`root`（这一段的图层元素）、`svg`（覆盖整个画布的 SVG）、`$(sel)`（只在 `root` 内查找元素）
    - 时间：`tl`（暂停状态的 GSAP 时间线，以本段 0 秒为起点）、`duration`、`cue(phrase, occurrence=1) -> 秒`、`cueEnd(phrase, occurrence=1)`。找不到词时抛 Error，信息里带上词和段 id。
    - 工具：`random()`（种子由段 id 决定）、`startState`
    - 镜头：`camera.shot({x, y, zoom}, at, dur, ease?)`，开始时自动应用 `startState.camera`
    - 角色：`actor(name, params) -> Actor`，开始时自动应用 `startState.actors[name]`。`Actor` 的方法有 `place({x,y,scale,flip}, at=0)`、`moveTo({x,y}, at, dur, ease?)`、`face(flip, at)`、`pose({部件: 角度}, at, dur)`、`expression(name, at)`。
    - 结束状态：`endState({keep: [...]})`，声明这一段要留给下一段的元素标签。
  - `EduFilm.instantiate(id) -> {tl, state(t) -> StageState, geometryDigest() -> string}`：只给检查脚本用。`geometryDigest` 把所有角色零件内部的 path、shape 属性哈希成一个字符串。

确定性规则（由运行时负责）：加载时执行 `gsap.ticker.sleep()`，设置 `gsap.config({autoSleep: 0})` 并暂停 `gsap.globalTimeline`。所有时间线只能通过 `seek` 来定位，画 Canvas 或 three.js 的代码只能写在 tween 的 `onUpdate` 回调里。

- [ ] **Step 1: 写失败的检查**

`studio_runtime_checks.py` 的写法和 `direct_determinism_checks.py` 一样，都继承 `unittest.IsolatedAsyncioTestCase`。夹具 `fixtures/studio/core_segment.js` 里有一个定义好的角色 `kr`，有 `arm_r` 零件；有一个文字元素 `data-edu-id="vertex"`；还有一条镜头推近。

```python
async def test_seek_is_deterministic_forward_and_backward(self):
    async with studio_page(core_film()) as (page, errors):
        times = [0, 0.5, 1.3, 2.9, 3.4, 2.0, 0.1, 3.4]
        shots = {}
        for t in times:
            await page.evaluate('t=>window.renderFrame(t)', t)
            png = await page.screenshot()
            if t in shots: self.assertTrue(same_png(shots[t], png), t)
            shots[t] = png
        self.assertEqual(errors, [])

async def test_cue_and_missing_cue(self):
    async with studio_page(core_film()) as (page, _):
        self.assertAlmostEqual(await page.evaluate('EduFilm.instantiate("a").cue("顶点")'), 2.91, 2)
        msg = await page.evaluate('(()=>{try{EduFilm.instantiate("a").cue("开口")}catch(e){return e.message}})()')
        self.assertIn('开口', msg); self.assertIn('a', msg)

async def test_start_state_applied_and_end_state_measured(self):
    # 夹具：start_state 里 kr 在 (300,600)，段代码在 1–2 秒把 kr 移到 (500,600)，镜头 zoom 推到 1.4
    async with studio_page(core_film()) as (page, _):
        s0 = await page.evaluate('EduFilm.instantiate("a").state(0)')
        s1 = await page.evaluate('(f=>f.state(f.tl.duration()))(EduFilm.instantiate("a"))')
        self.assertEqual((s0['actors']['kr']['x'], s0['actors']['kr']['y']), (300, 600))
        self.assertAlmostEqual(s1['actors']['kr']['x'], 500, 0)
        self.assertAlmostEqual(s1['camera']['zoom'], 1.4, 2)

async def test_actor_geometry_never_changes(self):
    async with studio_page(core_film()) as (page, _):
        digests = await page.evaluate('''(()=>{const f=EduFilm.instantiate("a");const d=[];
            for(const t of [0,1,2,3]){f.tl.seek(t);d.push(f.geometryDigest())}return d})()''')
        self.assertEqual(len(set(digests)), 1)
    async with studio_page(core_film(code=MUTATING_PART)) as (page, errors):
        await page.evaluate('t=>window.renderFrame(t)', 1.5)
        self.assertTrue(any('角色零件形状被修改' in e for e in await page.evaluate('window.studioDiagnostics')))

async def test_no_autonomous_playback(self):
    async with studio_page(core_film()) as (page, _):
        await page.evaluate('t=>window.renderFrame(t)', 1.0)
        a = await page.screenshot(); await page.wait_for_timeout(300); b = await page.screenshot()
        self.assertTrue(same_png(a, b))
```

`MUTATING_PART` 是一段会改写 `arm_r` 内部 path 的 `d` 属性的代码。

- [ ] **Step 2: 构建渲染镜像，运行检查，确认失败**
Run: Global Constraints 里的浏览器检查命令
Expected: FAIL（`edu_motion.js` 不存在）

- [ ] **Step 3: 实现 `page.py`、`edu_motion.js`、`API.md`**

`API.md` 的每个函数都要写上签名、一句说明和一个最小示例，单位统一写明（秒、像素、度）。

- [ ] **Step 4: 运行检查，确认通过**（同 Step 2 的命令，Expected: 5 个检查全部 OK）

- [ ] **Step 5: 提交**（标题：`feat(studio): 动效库核心（确定性时间线、逐词定位、镜头与角色接口）`）

### Task 5: 动效库效果：高亮、公式、绘制、函数图像、手绘

**Files:**
- Modify: `backend/app/studio/runtime/edu_motion.js`、`backend/app/studio/runtime/API.md`
- Test: `backend/tests/studio_runtime_checks.py`（新增检查）、`backend/tests/fixtures/studio/effects_segment.js`

**Interfaces:**
- Consumes: Task 4 的 `ctx`、`studio_page`。
- Produces（都挂在 `ctx.motion` 上，`at` 和 `dur` 的单位是秒，通常写成 `ctx.cue(...)`）：
  - `tex(latex, {x, y, size, id}) -> Element`：用 KaTeX 渲染公式，`trust` 只允许 `\htmlClass`，这样可以用 `\htmlClass{t-a}{x^2}` 给公式里的某一项命名。
  - `highlight(target, at, {dur=0.6, color, style='glow'|'underline'|'box'|'color'})`：`target` 可以是元素，也可以是 `'#vertex'`、`'.t-a'` 这样的选择器。每次调用都记录到 `ctx.__highlights`，记下 `{target, at}`，供 Task 7 检查高亮是否和词对上。
  - `spotlight(target, at, dur, {dim=0.25})`：其余部分变暗。
  - `circle(target, at, dur)`：画圈圈出目标。
  - `drawPath(pathEl, at, dur)`：用 DrawSVG 逐步画出路径。
  - `plot(fn, {xRange, yRange, box: {x, y, w, h}, samples=200, id}) -> {path, toScreen(x, y) -> {x, y}}`：画函数图像。
  - `follow(el, pathEl, at, dur)`：沿路径运动，用 MotionPath 实现。
  - `morph(fromEl, toShape, at, dur)`：图形变形，用 MorphSVG 实现。
  - `splitText(el, at, {stagger=0.04})`：文字逐字出现。
  - `rough(kind: 'line'|'rect'|'circle'|'path', args, opts) -> Element`：用 Rough.js 画手绘图形，`seed` 用 `ctx.random()` 生成。
  - `timeline(items, at, dur)`、`mapRoute(points, at, dur)`、`scaleCompare(items, at, dur)`：时间线推进、地图路线、比例尺对比这三种画面手法。

- [ ] **Step 1: 写失败的检查**

```python
async def test_tex_term_highlight_lands_on_cue(self):
    # 夹具：tex('y=\\htmlClass{t-a}{x^2}-2x-3') 在 cue("顶点") 时 highlight('.t-a')
    async with studio_page(effects_film()) as (page, errors):
        hs = await page.evaluate('EduFilm.instantiate("fx").highlights()')
        self.assertEqual(hs[0]['target'], '.t-a'); self.assertAlmostEqual(hs[0]['at'], 2.91, 2)
        await page.evaluate('t=>window.renderFrame(t)', 2.0)
        before = await page.locator('.t-a').evaluate('e=>getComputedStyle(e).color')
        await page.evaluate('t=>window.renderFrame(t)', 3.3)
        after = await page.locator('.t-a').evaluate('e=>getComputedStyle(e).color')
        self.assertNotEqual(before, after); self.assertEqual(errors, [])

async def test_plot_maps_function_to_box(self):
    # 夹具：plot(x=>x*x-2*x-3, {xRange:[-2,4], yRange:[-5,5], box:{x:100,y:80,w:600,h:400}})
    async with studio_page(effects_film()) as (page, _):
        p = await page.evaluate('EduFilm.instantiate("fx").plotProbe(1)')  # 夹具暴露 toScreen(1, f(1))
        self.assertAlmostEqual(p['x'], 100 + 600 * 3/6, 0)
        self.assertAlmostEqual(p['y'], 80 + 400 * (5 - (-4))/10, 0)

async def test_draw_path_progress_follows_time(self):
    async with studio_page(effects_film()) as (page, _):
        # 夹具：drawPath 从 1.0 秒开始，持续 2.0 秒，ease 为 'none'
        prog = await page.evaluate('''(()=>{const f=EduFilm.instantiate("fx");f.tl.seek(2.0);
            const e=f.root.querySelector("#curve");return parseFloat(getComputedStyle(e).strokeDashoffset)/e.getTotalLength()})()''')
        self.assertAlmostEqual(abs(prog), 0.5, 1)

async def test_every_effect_is_seek_safe(self):
    # 同一时刻画面必须一致：覆盖 spotlight、circle、follow、morph、splitText、rough 和三种画面手法
    async with studio_page(effects_film()) as (page, errors):
        shots = {}
        for t in [0.5, 4.5, 2.2, 6.0, 0.5, 6.0, 2.2]:
            await page.evaluate('t=>window.renderFrame(t)', t); png = await page.screenshot()
            if t in shots: self.assertTrue(same_png(shots[t], png), t)
            shots[t] = png
        self.assertEqual(errors, [])
```

`highlights()` 和 `plotProbe()` 是 `instantiate` 返回对象上只给检查用的辅助方法。`plotProbe` 只在夹具里定义。

- [ ] **Step 2: 运行检查，确认失败**（命令同 Task 4，Expected: 新增的 4 个检查 FAIL）
- [ ] **Step 3: 实现以上效果，并补全 `API.md`**
- [ ] **Step 4: 运行检查，确认通过**（Expected: 全部 OK）
- [ ] **Step 5: 提交**（标题：`feat(studio): 动效库高亮、公式、绘制与手绘效果`）

### Task 6: 整片运行时：接缝、转场、字幕、逐段错误隔离

**Files:**
- Modify: `backend/app/studio/runtime/film_runtime.js`、`backend/app/studio/runtime/API.md`
- Test: `backend/tests/studio_runtime_checks.py`（新增检查）

**Interfaces:**
- Consumes: Task 3 的 JSON 结构（`timeline`、`seams`、`captions`）；Task 4、5 的 `ctx`。
- Produces：
  - 每段一个图层 `<section class="edu-layer" data-segment="<id>">`。
  - `window.renderFrame(t)`：t 落在某段里时，只显示这一段的图层。t 落在 `continue` 接缝里时，保持前一段的最后一帧。t 落在 `transition` 接缝里时，前段图层停在最后一帧，后段图层停在第一帧，两者按转场类型做动画。
  - 转场函数 `EduStudio.transitions[name](outgoing, incoming, progress)`，`progress` 取值 0..1，必须是纯函数。五种转场：`push`（整体推移）、`wipe`（擦除）、`zoom`（缩放穿越）、`match`（匹配剪辑：两段中 `data-edu-match` 相同的元素做位置插值，其余部分硬切）、`fade`（淡入淡出）。
  - 字幕画在字幕区，取当前时刻所在的那一句；字幕区内文字居中，字号 30 px，下方有半透明底。
  - 错误隔离：某段的 `build` 抛出异常时，`studioDiagnostics` 记一条 `{segment, message}`，这一段显示为空图层，其余段照常运行。`studioReady` 仍然 resolve。每次 `renderFrame` 都把每段的 `geometryDigest()` 和构建时的基准值比较，不一致就记一条 `{segment, message: '角色零件形状被修改'}`。

- [ ] **Step 1: 写失败的检查**

```python
async def test_continue_seam_holds_last_frame(self):
    async with studio_page(two_segment_film(seam='continue', gap=0.4)) as (page, _):
        # 夹具：a 段长 2 秒，b 段从 2.4 秒开始
        a_end = await frame_at(page, 1.9999); mid = await frame_at(page, 2.2)
        self.assertTrue(same_png(a_end, mid))

async def test_each_transition_runs_inside_gap_only(self):
    for name in ('push', 'wipe', 'zoom', 'match', 'fade'):
        async with studio_page(two_segment_film(seam='transition', transition=name, gap=0.8)) as (page, errors):
            start, middle, end = (await frame_at(page, t) for t in (2.0, 2.4, 2.8))
            self.assertFalse(same_png(start, middle), name); self.assertFalse(same_png(middle, end), name)
            self.assertTrue(same_png(end, await frame_at(page, 2.8)), name)
            self.assertEqual(errors, [], name)

async def test_caption_shows_current_sentence(self):
    async with studio_page(two_segment_film(seam='continue', gap=0)) as (page, _):
        await page.evaluate('t=>window.renderFrame(t)', 0.5)
        self.assertEqual(await page.locator('.edu-caption').inner_text(), '第一句。')

async def test_broken_segment_is_reported_by_id(self):
    async with studio_page(two_segment_film(b_code='throw new Error("坏了")')) as (page, _):
        diag = await page.evaluate('window.studioDiagnostics')
        self.assertTrue(any(d['segment'] == 'b' and '坏了' in d['message'] for d in diag))
        await page.evaluate('t=>window.renderFrame(t)', 0.5)  # a 段仍然能正常画出来
```

`frame_at(page, t)` 是辅助函数：先 `renderFrame(t)`，再截图。`same_png` 沿用 `direct_render.same_pixels` 的阈值。

- [ ] **Step 2: 运行检查，确认失败**（命令同 Task 4）
- [ ] **Step 3: 实现**
- [ ] **Step 4: 运行检查，确认通过**（Expected: 全部 OK，Task 4、5 的检查也全部通过）
- [ ] **Step 5: 提交**（标题：`feat(studio): 整片接缝、五种转场、字幕与逐段错误隔离`）

### Task 7: 渲染服务新接口：检查、截帧、导出

**Files:**
- Create: `backend/app/studio/render_contract.py`、`backend/app/studio/inspect.py`、`backend/app/studio/export.py`
- Create: `renderer/studio_worker.py`
- Modify: `renderer/app.py`：新增 `POST /studio/inspect` 和 `POST /studio/render`，复用现有的 `busy` 标记和子进程方式；`execute` 原有的逻辑一行都不改。
- Test: `backend/tests/test_studio_render_contract.py`（pytest）、`backend/tests/studio_render_checks.py`（渲染镜像）

**Interfaces:**
- Consumes: Task 3 的 `build_film_html`、`Segment`、`Seam`、`state_diff`、`assemble_audio`；Task 4 的 `studio_page`。
- Produces（`render_contract.py`，`extra='forbid'`）：
  - `InspectRequest(runtime_digest: str, html: str (≤4_000_000), duration: float, frame_times: list[float] (≤40), checks: list[Literal['determinism','bounds','overlap','highlights','geometry','states']])`
  - `Issue(code: str, segment: str | None, t: float | None, element: str | None, message: str)`
  - `InspectResult(issues: list[Issue], frames: list[{t: float, png_base64: str}], states: dict[str, {start: StageState, end: StageState}])`。截图缩小到 640×360，用于看图审核。
  - `RenderRequest(runtime_digest: str, html: str, audio_base64: str (≤196 MB), duration: float, width=1280, height=720, fps=30)`，返回 `{mp4_base64, metadata}`，`metadata` 沿用 `videos.export.probe` 的格式。
  - `runtime_digest` 和渲染服务里的不一致时返回 409。
- Produces（`inspect.py`）：`async inspect_film(req: InspectRequest) -> InspectResult`。每项检查对应的 `Issue.code`：
  - `runtime`：`studioDiagnostics` 里的每一条。
  - `determinism`：在各段的 0%、50%、100% 时刻正向定位截图，再倒序定位截图，两次画面不一致。
  - `bounds`：文字和公式元素（`text`、`.katex`、`[data-edu-text]`）的外框超出画布，或者压进字幕区。检查时刻为每段 10 等分点，加上每个高亮时刻。带 `data-edu-offstage` 的元素不检查。
  - `overlap`：同一时刻两个文字元素的外框交叠面积超过较小者的 15%。
  - `highlights`：脚本要求的每个 `Highlight`，都要在 `cue(phrase, occurrence)` 的 ±0.15 秒内，有一次针对 `target` 的 `motion.highlight` 调用。
  - `geometry`：`studioDiagnostics` 里"角色零件形状被修改"的记录。
  - `states`：每段在第 0 帧和最后一帧实测的状态，和这一段声明的 `start_state`、`end_state` 用 `state_diff` 比较。
- Produces（`export.py`）：`async render_film(req: RenderRequest, output: Path) -> dict`。逐帧调用 `renderFrame` 并截图，用管道送给 ffmpeg 编码，参数沿用 `videos/direct_render.render_direct` 里的那组。编码完成后用 `videos.export.decode_check` 和 `probe` 检查输出。

- [ ] **Step 1: 写失败的测试**

```python
# test_studio_render_contract.py
def test_inspect_request_limits():
    with pytest.raises(ValidationError):
        InspectRequest(runtime_digest='0'*64, html='x', duration=1, frame_times=[0.0]*41, checks=[])
    with pytest.raises(ValidationError):
        InspectRequest(runtime_digest='0'*64, html='x', duration=1, frame_times=[], checks=['nope'])

# studio_render_checks.py
async def test_text_in_caption_zone_reported(self):
    result = await inspect_film(req(film_with_text_at(y=650)))
    issue = next(i for i in result.issues if i.code == 'bounds')
    self.assertEqual(issue.segment, 'a'); self.assertIsNotNone(issue.t); self.assertIn('字幕区', issue.message)

async def test_overlap_and_missing_highlight_and_state_mismatch(self):
    codes = {i.code for i in (await inspect_film(req(bad_film()))).issues}
    self.assertTrue({'overlap', 'highlights', 'states'} <= codes)

async def test_clean_film_has_no_issues_and_returns_frames(self):
    result = await inspect_film(req(two_segment_film(seam='transition', transition='push', gap=0.8), frames=[0.5, 2.4]))
    self.assertEqual(result.issues, []); self.assertEqual(len(result.frames), 2)

async def test_render_mp4_matches_duration(self):
    meta = await render_film(render_req(two_segment_film(seam='continue', gap=0.2)), Path(tmp)/'o.mp4')
    self.assertAlmostEqual(meta['duration'], 4.2, delta=1/30)
```

- [ ] **Step 2: 运行测试，确认失败**
Run: `cd backend && uv run --env-file ../.env pytest tests/test_studio_render_contract.py -q`，然后在渲染镜像里运行 `python /checks/studio_render_checks.py`
Expected: FAIL
- [ ] **Step 3: 实现以上内容，并接到 `renderer/app.py`**
- [ ] **Step 4: 运行测试，确认通过**；同时运行 `python /checks/direct_determinism_checks.py`，确认旧接口没有受影响
- [ ] **Step 5: 提交**（标题：`feat(studio): 渲染服务新增分段检查、截帧与导出接口`）

### Task 8: 后端调用渲染服务的客户端

**Files:**
- Create: `backend/app/studio/render_client.py`
- Test: `backend/tests/test_studio_render_client.py`

**Interfaces:**
- Consumes: Task 7 的请求和返回模型；`settings.renderer_url`。
- Produces: `class StudioRenderer(settings, http: httpx.AsyncClient)`，提供 `async inspect(req: InspectRequest) -> InspectResult` 和 `async render(req: RenderRequest) -> dict`。错误处理：
  - 429：按 `Retry-After` 等待后重试，最多 10 次。
  - 422：抛 `StudioRenderError(detail)`。
  - 409：抛 `ValueError('渲染服务版本不一致，请重新部署渲染服务')`。
  - 其他错误：抛 `ValueError('渲染服务暂时不可用')`。
  - 没有配置渲染服务：抛 `ValueError('视频渲染服务尚未配置，请联系管理员')`。

- [ ] **Step 1: 写失败的测试**：用 `httpx.MockTransport` 覆盖以下情况：429 两次后成功；422 抛出 `StudioRenderError`；409 的错误文案；`renderer_url` 为空。
- [ ] **Step 2: 运行，确认失败**：`cd backend && uv run --env-file ../.env pytest tests/test_studio_render_client.py -q`
- [ ] **Step 3: 实现**
- [ ] **Step 4: 运行，确认通过**
- [ ] **Step 5: 提交**（标题：`feat(studio): 渲染服务客户端（排队重试与错误分类）`）

### Task 9: 3D 可行性验证（渲染服务没有显卡）

**Files:**
- Create: `backend/tests/fixtures/studio/three_segment.js`：一个立方体加一个旋转的函数曲面，用 `MeshStandardMaterial` 材质和平行光；画面渲染写在 tween 的 `onUpdate` 里，`WebGLRenderer` 设置 `preserveDrawingBuffer: true`。
- Modify: `backend/tests/studio_render_checks.py`（新增一项检查）、`backend/app/studio/inspect.py` 和 `export.py`（页面里含 `THREE` 时用 `webgl=True` 打开）
- Create: `docs/superpowers/plans/notes/2026-10-28-studio-3d-spike.md`（记录结果）

**通过标准**：在渲染镜像里，按 Compose 的限制（2 CPU、2 GiB 内存）运行时，满足以下全部条件：
- 页面没有报错，画面不是空白。
- 同一时刻前后两次截图的像素一致，阈值同 `same_png`。
- 1280×720 下单帧截图的平均耗时不超过 0.5 秒。
- 3 秒的片段能导出 mp4。

- [ ] **Step 1: 写检查** `test_three_segment_renders_deterministically_without_gpu`：包含上面四项断言，并打印单帧平均耗时。
- [ ] **Step 2: 在渲染镜像里运行**，把结果写进 notes：是否通过、单帧耗时、遇到的问题。
- [ ] **Step 3: 根据结果二选一**：
  - 通过：保留这项检查。
  - 不通过：把这项检查标为 `skip`，写明原因，并在 notes 里写"第 2 部分的风格库暂不包含 3D 物体与拆解"。
- [ ] **Step 4: 提交**（标题：`test(studio): 验证无显卡环境下的 three.js 渲染`）
- [ ] **Step 5: 把结论告诉用户**（通过或不通过、单帧耗时），再开始 Task 10

### Task 10: 端到端演示片

**Files:**
- Create: `backend/tests/fixtures/studio/demo/characters.js`：用 `EduStudio.defineCharacter` 重写 `.local/previews/character-reference.html` 里的孔融和哥哥，零件、配色、关节位置都照抄原文件。
- Create: `backend/tests/fixtures/studio/demo/seg_parabola.js`、`seg_vertex.js`、`seg_story.js`，以及 `demo/film.json`（每段的旁白、时长、手写的逐词时间、高亮、开始和结束状态、接缝）。
- Create: `backend/app/studio/demo.py`：命令行入口，运行 `python -m app.studio.demo --voice edge:zh-CN-YunxiNeural --out <目录>`。
- Test: `backend/tests/studio_render_checks.py`（新增一项检查）、`backend/tests/test_studio_demo.py`

演示片的内容：
- `parabola` 段：KaTeX 写出 y=x²−2x−3，曲线逐步画出，讲到"开口向上"时高亮 x² 项。
- `vertex` 段：同一张坐标系，跟随点沿曲线移到 (1, −4)，讲到"顶点"时圈出顶点并推近镜头。和上一段之间是 `continue` 接缝，开始状态等于上一段的结束状态。
- `story` 段：和上一段之间是 `push` 转场。孔融拿起大梨，走到哥哥身边，抬手把梨递出去，哥哥点头。

**Interfaces:**
- Consumes: Task 2 到 Task 8 的全部接口。
- Produces: `async build_demo(voice: str, out: Path, *, synthesize=synthesize_words, renderer: StudioRenderer) -> Path`。流程：每段旁白先用 Edge 配音，得到真实的逐词时间，用它替换 `film.json` 里手写的时间，段时长取配音时长；然后依次调用 `build_film_html`、`assemble_audio`、`inspect`，`inspect` 有问题时抛 `FilmError` 并列出全部问题；没有问题就调用 `render`，写出 `out/demo.mp4` 和 `out/demo.html`。

- [ ] **Step 1: 写失败的测试**
  - `test_studio_demo.py`：把 `synthesize` 换成假函数，返回固定的逐词时间；把 `renderer` 换成假对象，`inspect` 返回空问题列表。断言 `film_duration` 等于各段时长加上接缝时长，且 `demo.html` 里含有 3 个 `defineSegment`。
  - `studio_render_checks.py`：`test_demo_film_has_no_issues`，使用手写的逐词时间，对演示片运行 `inspect_film`，打开全部检查项，断言没有任何问题。
- [ ] **Step 2: 运行，确认失败**
- [ ] **Step 3: 写夹具和 `demo.py`**
- [ ] **Step 4: 运行，确认通过**：pytest 和渲染镜像检查都要通过。
- [ ] **Step 5: 用真实 Edge 配音生成演示片**：在能联网的开发机上，启动 `docker compose up -d renderer`，设置 `RENDERER_URL`，然后运行 `cd backend && uv run --env-file ../.env python -m app.studio.demo --voice edge:zh-CN-YunxiNeural --out ../.local/previews/studio-demo`。Expected: 生成 `demo.mp4`，时长和配音一致。
- [ ] **Step 6: 提交**（标题：`feat(studio): 端到端演示片（公式高亮、延续接缝、推移转场、角色动作）`）。`.local/` 下的生成物不提交。
- [ ] **Step 7: 把 `demo.mp4` 发给用户看效果**，重点请用户看：人物有没有变形、高亮是否和配音对上、接缝是否顺。用户提出的问题记进第 2 部分计划的输入。

## 本计划完成的标志

- Task 1 到 Task 10 的 pytest 测试和渲染镜像检查全部通过，旧链路的测试也全部通过。
- 用户看过演示片，确认画面质量方向正确。
- 3D 可行性有明确结论，记录在 notes 里。
