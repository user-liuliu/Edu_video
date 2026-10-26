# Edu_video

教学视频与 PPT 生成助手，实际入口为 `http://127.0.0.1:8080/`。

## 当前正式版（2026-10-26）

工作台同时支持教学视频与 PPT 制作；草稿箱保留生成中的项目，教师点击满意导出后，PPT 才进入我的作品。以下功能已接入当前本地运行版本。

- PPT 使用独立项目、素材、任务和 `/api/presentations` 接口，共用登录、素材解析、私有存储、大纲模型配置和教师并发额度。大纲生成及课件生成完成均有通知。
- 大纲支持新增、删除、排序、编辑和选页模型修改；大纲页集中提供审核、保存与确认进入预览，课件生成在预览页发起。
- 预览中可直接修改原页面文字、添加文本框，并拖动或缩放文本、图片与图形；教师手动修改直接保存。模型修改直接基于选中页面，历史版本可预览，并按当前选中版本下载。
- 自动生成先质检、修复和简化重建，再使用确定性模板兜底，最后检查文件技术可用性；依赖外部模型与运行服务的可用性，不能据此承诺所有请求必然成功。
- 提供「简洁教学 · 清蓝」「活泼插画 · 橙光」「学术正式 · 墨红」及自动推荐，固定宽屏 16:9。内置固定版本 PPT Master 6.7.0 与许可文件，不依赖开发机 Skill 路径。
- PPT 生成和模型改页每次消耗 10 积分，使用余额预留、成功结算和失败释放机制，消费计入积分记录；手动编辑不触发模型生成计费。管理员项目数包含视频与 PPT。
- 视频支持生成检查点、上下文压缩与中断续跑；我的作品视频卡片支持直接下载。
- PPT 大纲与大纲改写采用有界流式接收，保留安全的模型接口错误原因；上游服务仍可能返回限流、鉴权或超时错误。

部署细节与历史验收记录见 [PPT 运行说明](docs/ppt-generation.md)。数据库迁移已扩展到 `0010`；部署须包含 backend、worker、scheduler、frontend 及 PPT 渲染服务。`.env`、用户素材、生成课件和本地模板验收产物不提交到仓库。自动测试使用隔离测试数据库与模拟模型，不消耗用户积分，也不代替真实模型质量或 PowerPoint/WPS 应用兼容性验收。

## 历史功能记录（2026-10-18，第二阶段）

- 管理员登录默认进入页面配置，仅使用「页面配置、模型配置、用户管理」管理导航，保留所有原有字段和提示；不提供教师工作台，访问教师页面会返回页面配置。
- 视频制作：填写教学需求、选择动态参数、选择参考素材。点击保存草稿时上传素材并保存需求；生成大纲前自动执行保存，未保存的编辑不会覆盖已有草稿。页面内跳转保留当前编辑，刷新或退出登录清空未保存的新建内容。
- 大纲草稿：教学目标、完整逐字稿、五类画面、来源定位、审核提示和预计时长；支持保存、增删排序、勾选段落改写、重新审核和确认。审核状态为绿色“AI已审核”、黄色“待审核”、红色“审核未通过”；修改片段后需要重新审核。保存可以保留未审核稿件并提示去审核，确认要求当前内容已保存且全部片段审核通过。
- 我的视频/草稿箱：仅显示本人项目，未完成项目进入草稿箱，可继续编辑、恢复素材或删除；我的视频仅显示已完成视频，当前尚无实际渲染成片。
- 我的偏好：手动选择或明确接受建议后保存，按用户隔离；本次需求优先，管理员关闭后不读取或用于生成。
- 视频预览、HTML 动画、配音、FFmpeg 合成、版本和下载留给第 3 部分；账户设置不在本阶段新增功能。

## 本地部署

保留现有 `.env`、数据库卷和模型配置，补充 `.env.example` 中 MinIO 变量。凭据不能提交、打印或写入文档。backend、worker、scheduler 共用同一镜像，顺序构建以避免同时导出大型 LibreOffice 镜像：

```powershell
docker compose config --quiet
docker compose build backend
docker compose build renderer
docker compose build frontend
docker compose up -d
docker compose ps
docker compose exec -T backend alembic current
docker compose exec -T backend alembic check
docker compose exec -T worker celery -A app.jobs.celery_app:celery_app inspect ping --timeout=4
```

后端启动依次执行迁移、管理员初始化和 agent state setup；worker/scheduler 等待后端健康。nginx 上传路径单独放宽到 26 MiB，保留 Host 端口。仅重建 backend 后须重启 frontend 以更新 nginx 解析的服务地址。

升级前备份完整 PostgreSQL 数据库（含业务表和 `agent_state` schema）、MinIO `materials` 卷，以及安全保存 `.env` 中 MASTER_KEY/存储凭据。恢复时匹配数据库与对象文件；禁止清空真实库或执行 `docker compose down -v`。

修改 backend/app/videos 中参与动画运行版本计算的代码、提示词或素材时，必须同时重建并更新 backend、worker、scheduler 和 renderer。renderer 镜像也复制了这些文件；只更新后端会导致预览检查或 MP4 导出提示“动画运行版本不一致”。部署后须核对 worker 与 renderer 的 app.videos.direct_html.direct_digest() 一致，并从 worker 实测 HTML 检查及短片导出；仅健康接口成功不足以证明版本一致。

## 配置约定

搜索使用 Tavily，在模型配置的「联网搜索」填写 `https://api.tavily.com`（完整 `/search` 也可）和 Key，无需模型名。测试连接会实际调用搜索。2026-10-16 已核对官方接口 POST `/search`、Bearer 鉴权、`search_depth=basic` 与 `max_results`；自动测试使用模拟响应，未用真实 Key 产生费用。搜索未配置时隐藏开关；关闭后不访问搜索服务、网页或搜索缓存。上传素材和搜索摘要均需教师核实。

上传支持 PPT/PPTX、PDF、DOC/DOCX、PNG/JPEG/WebP，单文件 25 MiB、最多 10 文件/项目、总计 100 MiB。拒绝加密文档、宏、伪装类型及超限 ZIP。旧 Office 文件在 Linux 容器内通过 LibreOffice 隔离转换；Windows 本地开发可先另存为现代格式。MinIO 素材为私有，下载必须认证并校验项目归属。

隐藏参数按服务端默认值解析。生成须带当前 `form_version`；排队期间页面配置变化时明确失败并返回需求页确认参数。隐藏素材后禁止新上传，新生成大纲也不使用旧素材；已有文件仍可查看和删除。修改需求、科目、年级、教材、时长、风格、联网方式或素材后保留旧大纲并要求重新生成；尺寸/音色调整不会使讲稿失效。

自定义时长大于 0 且最多 60 分钟。总讲稿估时超出配置容差会显示审核提示，估时不等于实际配音时长。第三阶段采用大纲驱动 HTML/SVG/JavaScript 动画再导出 MP4，不依赖生图模型。人物故事默认采用清晰矢量／简洁插画人物，只有教师在需求或画面修改中明确要求像素风时才采用像素风并加载像素参考；公式、函数图像和实验保持清晰图形。教师明确的其他画风优先，模型自动产生的像素描述不作为像素风选择依据。已有封存预览保持原画风，重新生成完整视频才使用当前默认规则。管理员已移除“画插图”、每段画面数上下限和每分钟插图上限；画面描述保留，按教学内容与旁白节奏安排，不按旧数量范围拦截生成/改写/审核。原大纲结构的大小保护仍保留。

有效模型用途为大纲/讲稿、审核、看图识别、Embedding、配音、联网搜索；必需项不再包含生图。看图识别仍用于参考素材。生成参数保留每位教师的并发任务数、重试次数、时长允许偏差和长期记忆。旧生图加密配置行保留但不使用，旧图片数量参数读取时忽略。HTML 自动生成与渲染业务链尚待第三阶段后续实施。

解析/生成/改写/审核运行于 Celery + Redis，持久化 outbox 每 15 秒派发，带租约、心跳、并发限制和崩溃恢复；关闭网页不会取消任务。LangGraph checkpoint/Store 在 PostgreSQL `agent_state` 独立 schema，业务 Alembic 不管理此 schema。Key 不进入任务消息或 checkpoint。

模型请求遇到临时限流、服务端异常或网络故障时，按管理员重试次数做有限退避重试；鉴权、权限、明确的额度不足等错误直接给出对应提示。结构化输出只有收到相关不兼容错误才降级为 JSON 对象。服务端记录模型用途、HTTP 状态和重试类别，不记录密钥、响应正文或教师资料。调用错误不会误报为大纲结构错误；失败保留旧稿，审核检查点支持继续处理。

## 测试

后端：在 `backend` 运行 `uv run --env-file ../.env pytest -q`。只可使用独立 `TEST_DATABASE_URL`，不能指向开发/生产库，不能并行运行两套后端测试（fixtures 会清理测试表）。

前端：在 `frontend` 运行 `npx vitest run --maxWorkers=1 --pool=threads` 和 `npm run build`（含 TypeScript 检查）。
渲染端回归：先构建 renderer，在该镜像中只读挂载 `backend/tests` 到 `/checks`，设置 `HOME=/tmp`、`PYTHONPATH=/render`，运行 `python /checks/direct_determinism_checks.py`。使用与 Compose 相同的只读文件系统、离线网络、2 CPU、2 GiB 内存和 `/tmp` tmpfs。用例覆盖真实 SVG 阴影/透明转场的正反定位、累计 Canvas/DOM 与自主 CSS 动画的拒绝、正常 worker 子进程及短片 MP4 编解码。`renderer/capture.py` 在截图前临时移出并原位放回原 SVG 节点，使 Chromium 重建滤镜绘制缓存；不克隆角色节点、不再次执行 `renderFrame`，也不放宽像素差阈值。此捕获修复不修改封存 HTML、配音或动画运行版本。

真实模型质量、联网额度和长文档效果需教师从界面提交任务验收；开发检查不读取或测试生产 `model_configs`。设计与计划见 `docs/superpowers/specs/2026-10-16-edu-video-agent-design.md` 和 `docs/superpowers/plans/2026-10-16-outline-agent.md`。

2026-10-18 合并前验证：后端 **230 passed**，前端 **16 个文件、150 passed**，TypeScript 检查与 Vite 生产构建通过，`git diff --cached --check` 通过。

## 第二阶段交付与验收边界

- 管理员统一设置同时生成任务上限，每位教师独立享有该额度；大纲与后续视频生成共享该教师的计数规则，超过上限返回明确提示。
- 大纲任务支持离页继续、返回恢复、失败重试与版本冲突检查；完成通知按完成时间依次展示，每条三秒，无需手动确认。加载使用持续移动的斜纹，显示阶段、累计等待时间和断线提示。
- 当前数据库迁移 revision 为 `0004`（`0004_material_parse_warnings.py`）。审核结果绑定内容版本，旧数据缺少明确通过结论时视为待审核；保存与确认由后端独立校验。
- 自动化测试使用独立测试数据库和模拟模型响应，不等同于真实模型质量验收，不额外消耗模型或搜索额度。

后续检查项已记录在 `docs/phase-2-follow-up.md`：真实模型与复杂素材质量、多教师任务与异常恢复、保存及多标签页一致性、跨会话通知、偏好与联网实际效果、备份恢复演练。视频渲染与 MinerU 仍为后续扩展。
