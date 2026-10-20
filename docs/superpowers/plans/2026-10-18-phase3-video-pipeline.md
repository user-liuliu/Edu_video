# 第三阶段视频生成 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将已确认的大纲转为带真实旁白、字幕和代码动画的MP4，并提供版本、预览、下载及重试。

**Architecture:** 复用项目、OutlineJob任务租约和每教师额度；独立视频版本和片段产物表固定输入快照。模型按受控场景接口生成SVG/HTML内容和时间轴，可信运行时按时间定位；无凭据独立渲染服务逐帧截图并用FFmpeg合成。

**Tech Stack:** FastAPI/SQLAlchemy/PostgreSQL/Celery/MinIO、Vue/Element Plus、Playwright Chromium、FFmpeg。

**Spec:** docs/superpowers/specs/2026-10-18-phase-3-video-design.md，尤其是第8节最新补充。使用现有codex/phase3-video-pipeline功能分支，不另建worktree。

**Status:** 用户接受修正版样片后已实施Task 1—6正式集成，自动回归、真实业务浏览器验收及本机8080部署完成。代码未提交/推送/合并；下方样片记录为历史记录，正式证据见文末及spec第9节。

## Global Constraints
- 只允许已保存、全部审核通过且已确认的大纲生成；保留原有功能和暖棕色样式。
- 视频和大纲共享每位教师的管理员并发额度；保留旧成功成片、版本及失败恢复。
- 不向模型生成代码或渲染容器传递业务密钥；固定时间渲染，不依赖页面实时播放。
- 生成素材/音频/视频私有存入MinIO；所有接口验证所有者，媒体支持Range。
- 真正配音驱动时长，字幕按句配音对齐；不伪称字级对齐。
- 本次使用现有工作目录及codex/phase3-video-pipeline分支；部署须完整测试及无运行任务。
- 分镜仅后台使用；教师通过播放位置和教学段落定位修改，不增加分镜确认步骤。
- 风格沿用现有配置：需求明确要求 > 具体讲解风格 > 按科目自动；视频步骤不擅改已确认讲稿。
- 版本记录稳定段落ID、片段ID、起止时间及风格/质量规则版本，旧版时间不得套用新版。

## 当前实现记录（2026-10-18，自动样片基础）
- 新增app/videos中的真实配音、按句字幕、纯数据Scene、规则显式注入、可信SVG运行时和本机逐帧MP4渲染；模型不输出可执行脚本。
- backend/scripts/video_samples.py读取现有配置生成理科和故事短片；输入为固定验收讲稿，尚未连接用户项目大纲、任务队列和MinIO。
- 本地缓存按讲稿、音色/模型配置、风格、规则版本及真实时长匹配，并校验文件摘要；没有匹配元数据的旧缓存不自动视为有效。
- 样片保存在忽略目录.superpowers/phase3-auto-samples；development依赖见backend/scripts/video-sample-requirements.txt。
- 常规后端测试另需执行真实浏览器回归：`python backend/tests/video_runtime_checks.py -v`。该检查依赖Playwright及本机Edge，不混入无浏览器的后端单测。
- 已修复审查发现的字幕字号不确定、递物提前覆盖轨道、公式与曲线参数不一致及缓存误复用；实际视频和测试记录见该目录verification.json及SDD进度记录。
- 后续仍须实现生产隔离renderer、整片超时/回收、动态几何检查、权限与媒体传输；此次不部署，也不将Task 1—6中的任一完整任务标为完成。

### 样片反馈修正（2026-10-18）
- 理科直线用解析求交裁切替代离散采样删点，避免端点在边缘跳动；新增smoother缓动，样片参数变化窗口由2.1秒延长到3.35秒。动画中的公式读数缩短，并以近似符号区分实际曲线精度，静止状态保留精确参数。
- 原故事音轨4.5—5.5秒与原始分句音频高度一致，异常来源已追溯至原始生成音频；波形对比不能单独判断声音类型或证明音质合格。
- 故事样片重新请求连续、单人、无背景与音效的干声旁白，保留48kHz WAV。字幕使用接口返回的句级时间戳，并核对讲稿一致性，时长变更后重新安排动作，不沿用旧秒数。
- 后续样片runner采用整段配音与时间戳，不再将每句随机生成音频压成MP3后拼接；缺失/无效时间戳和讲稿不一致显式报错。
- 修正版产物在.superpowers/phase3-auto-samples/{science,story}/revised/sample-v2.mp4，保留上一版供对比；旧模型场景只调整时间及缓动，不冒充重新全自动生成。主观音质仍以实际回听为准。

## Review Focus
- 并发重复提交/过期worker：只生成一个版本且不会覆盖新输出。
- 异常模型HTML与脚本：禁止网络、脚本、外部资源及越权文件访问。
- 大文件Range和断连：有界流式传输并关闭MinIO响应。
- 同项目旧成片与新稿：失败/编辑不丢历史版本，重试只复用匹配指纹产物。
- 容器重启/部分产物：持久化阶段和清理清单，孤立文件可回收。

### Task 1: 视频版本、任务准入与只读接口
**Files:** models.py、alembic新迁移、app/videos/{schemas,service,router}.py、main.py、jobs/tasks.py、projects/router.py；tests/test_videos.py。
**Interfaces:** POST /api/projects/{id}/videos (revision,idempotency_key,retry_version_id?)；GET版本列表/详情；任务kind=video；视频状态queued/running/succeeded/failed，项目完成状态completed。
- [x] 先测试准入、审核、幂等、教师隔离、共享配额、版本快照和旧成片保留。
- [x] 运行并观察失败，再实现迁移/模型/接口及任务分流。
- [x] 验证定向测试与原工作流回归。

### Task 2: 配音、字幕及受控动画内容
**Files:** app/videos/{speech,scenes,timeline}.py；tests/test_video_speech.py、test_video_scenes.py。
**Interfaces:** synthesize_speech(config,text,http)->bytes；build_scene(config,segment,duration,style,http)->Scene；compile_scene(scene,caption_timeline,dimensions)->html。
- [x] 测试真实接口形态解析、分句、文件限额、字幕时序、模型结构与SVG白名单、时间定位及理科/人物动作约束。
- [x] 实现先配音后定时；仅允许受控SVG/HTML元素与声明式变换，不执行模型任意JS。
- [x] 定向测试通过，记录实现选择。

### Task 3: 隔离渲染、MP4与媒体传输
**Files:** renderer/{Dockerfile,app.py,requirements.txt}、app/videos/{render_client,media}.py、docker-compose.yml；tests/test_video_media.py、renderer tests。
**Interfaces:** POST renderer /render (scene,captions,width,height,fps,audio_base64)->mp4；只接受受控数据，不接受HTML脚本。ffprobe验证尺寸/时长；私有媒体GET /api/projects/{id}/videos/{version}/media/{asset}?download=1支持Range。
- [x] 先测试Range、权限和隔离服务参数校验；实现有界渲染、无外部资源、非root与进程超时。
- [x] 真Chromium逐帧渲染短片并验证解码、移动帧与音频；不使用业务凭据。

### Task 4: 持久化视频流水线与重试
**Files:** app/videos/pipeline.py、jobs/tasks.py、materials/storage.py、projects/router.py；tests/test_video_pipeline.py。
**Interfaces:** execute_video_job(db,job,settings)按分句配音→场景→片段渲染→拼接→验证→存储；租约与revision发布保护。
- [x] 先测试成功发布、失败保留、checkpoint复用、任务接管和用户暂停状态。
- [x] 实现片段指纹和产物清单，最终输出与任务成功同事务提交。
- [x] 验证完整后端套件和迁移升级。

### Task 5: 第三步预览、历史与完成提醒
**Files:** frontend/src/api/videos.ts、views/workbench/VideoPreviewView.vue、OutlineView.vue、ProjectListView.vue、router及完成通知组件；frontend/tests。
**Interfaces:** 已确认大纲可进入视频预览并提交；显示持久化阶段、媒体播放/下载、版本/片段/重试；三秒提醒队列区分大纲/视频。
- [x] 先写交互测试，再接入既有制作步骤和样式，不新增无关页面或参数。
- [x] 提供按视频版本返回的教学段落与内部片段时间映射；测试片段边界、顺序变化、多个镜头对应同一段落及新旧版本时长变化。
- [x] 视频暂停后可选“修改这一段”，教学段落列表可跳转、调整修改范围；不暴露分镜编排页面或新增强制确认。
- [x] 首版范围选择只增减完整片段，并展示实际起止时间；提交segment_ids绑定来源版本，不把任意秒区间误当成已支持的剪辑能力。
- [x] 完整前后端测试、生产构建、独立审查；真实短片及部署健康检查，记录实际通过及限制。

### Task 6: 单片段自然语言修改与质量规范
**Files:** app/videos/{schemas,service,router,pipeline,scenes}.py、视频版本模型及所需迁移、frontend/src/api/videos.ts、VideoPreviewView.vue；tests/test_video_revisions.py及前端对应交互测试。
**Interfaces:** POST /api/projects/{id}/videos/{version_id}/revisions (revision,idempotency_key,segment_ids,instruction)；仅允许修改该版本已明确选中的片段画面，返回新版本及video任务。GET版本详情包含教学段落、片段ID、开始/结束时间及可修改状态。
- [x] 先测试所有者校验、来源版本和片段范围、空选区/歧义不得启动任务、幂等、共享额度、活动任务冲突、旧版保留及未改变片段复用。
- [x] 仅画面修改锁定讲稿与音色；模型提出讲稿或知识点变化时拒绝画面修改并提示回到大纲审核，不能自动改写后渲染。
- [x] 测试并实现风格优先级、风格来源和规则版本快照；规则显式进入生成上下文，既有大纲模型安全提示不被全局放松。
- [x] 实现理科/人物动作可检查规则与失败修复；未决定采用第三方框架，不因Skill参考擅加Remotion依赖。
- [x] 验证修改后音画同步、新版时间映射及重新合成，完整回归和实际播放后才能部署。

## 恢复开发前的顺序复核
- 建议先由Task 2/3所需的最小生成链输出一段理科、一段《孔融让梨》的自动生成短片，供用户确认效果，再扩展完整业务集成。
- Task 6中的风格与质量规范属于生成基础，恢复实施时前移至Task 2并在样片中验证；Task 6保留局部修改集成与对应回归，不等到最后才接入规范。
- Task 5的最终整体验收依赖Task 6也完成；先完成核心预览可独立验证，不能在局部修改尚缺失时宣称第三阶段全部交付。

## 正式集成验收记录

- Task 1/2/3/4/6已实现，测试分别见test_videos、test_video_content/quality、test_video_renderer/media、test_video_pipeline/revisions。Task 5核心交互已完成，17文件158项前端测试和生产构建通过；浏览器真实媒体验收待最终结果。
- 后端完整320 passed（108.26秒），包含独立schema迁移升级/check；前端158 passed；真实Edge运行时8 passed。
- 本轮独立审查7项Important全部进入修复：失败修改要求继承、MinIO open/read取消清理、缓存依赖失效、AAC时间映射、电路固定闭合、时长偏差提醒、几何失败有限重编排。修复回归有RED/GREEN记录，完整套件在修复后通过。
- 真实renderer已验证三个尺寸及完整解码、几何错误结构化返回；11/16/21帧三段拼接颜色逐帧一致、片段边界及片尾覆盖；进程init回收后无残留浏览器僵尸。
- 最终真实业务验收通过：三片段理科19.766秒、故事10.166秒，真实模型/配音/MinIO/renderer及Edge播放/暂停/段落seek/修改范围/下载；临时对象和测试凭据已清理。生成接口起点为确认过的大纲fixture，非新一轮资料到大纲全链。
- 正式8080已更新，部署前活动任务0及数据库备份，迁移0005=head，后端健康、worker→renderer连通，正式预览路由浏览器无脚本错误，匿名读取401。未提交推送或合并。
- 范围说明见spec第9节：统一舞台居中、有限理科/故事组件、自然配音无独立语速控制；不把自动检查当作主观教学质量验收。
