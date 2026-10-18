# Edu_video

教学视频生成助手。当前已交付平台基础和第 2 部分大纲 Agent，实际入口为 `http://127.0.0.1:8080/`。

## 当前功能（2026-10-18，第二阶段）

- 管理员登录默认进入页面配置，仅使用「页面配置、模型配置、用户管理」管理导航，保留所有原有字段和提示；不提供教师工作台，访问教师页面会返回页面配置。
- 视频制作：填写教学需求、选择动态参数、选择参考素材。点击保存草稿时上传素材并保存需求；生成大纲前自动执行保存，未保存的编辑不会覆盖已有草稿。页面内跳转保留当前编辑，刷新或退出登录清空未保存的新建内容。
- 大纲草稿：教学目标、完整逐字稿、五类画面、来源定位、审核提示和预计时长；支持保存、增删排序、勾选段落改写、重新审核和确认。审核状态为绿色“AI已审核”、黄色“待审核”、红色“审核未通过”；修改片段后需要重新审核。保存可以保留未审核稿件并提示去审核，确认要求当前内容已保存且全部片段审核通过。
- 我的视频/草稿箱：仅显示本人项目，未完成项目进入草稿箱，可继续编辑、恢复素材或删除；我的视频仅显示已完成视频，当前尚无实际渲染成片。
- 我的偏好：手动选择或明确接受建议后保存，按用户隔离；本次需求优先，管理员关闭后不读取或用于生成。
- 视频预览、实际插图、配音、FFmpeg 合成、版本和下载留给第 3 部分；账户设置不在本阶段新增功能。

## 本地部署

保留现有 `.env`、数据库卷和模型配置，补充 `.env.example` 中 MinIO 变量。凭据不能提交、打印或写入文档。backend、worker、scheduler 共用同一镜像，顺序构建以避免同时导出大型 LibreOffice 镜像：

```powershell
docker compose config --quiet
docker compose build backend
docker compose build frontend
docker compose up -d
docker compose ps
docker compose exec -T backend alembic current
docker compose exec -T backend alembic check
docker compose exec -T worker celery -A app.jobs.celery_app:celery_app inspect ping --timeout=4
```

后端启动依次执行迁移、管理员初始化和 agent state setup；worker/scheduler 等待后端健康。nginx 上传路径单独放宽到 26 MiB，保留 Host 端口。仅重建 backend 后须重启 frontend 以更新 nginx 解析的服务地址。

升级前备份完整 PostgreSQL 数据库（含业务表和 `agent_state` schema）、MinIO `materials` 卷，以及安全保存 `.env` 中 MASTER_KEY/存储凭据。恢复时匹配数据库与对象文件；禁止清空真实库或执行 `docker compose down -v`。

## 配置约定

搜索使用 Tavily，在模型配置的「联网搜索」填写 `https://api.tavily.com`（完整 `/search` 也可）和 Key，无需模型名。测试连接会实际调用搜索。2026-10-16 已核对官方接口 POST `/search`、Bearer 鉴权、`search_depth=basic` 与 `max_results`；自动测试使用模拟响应，未用真实 Key 产生费用。搜索未配置时隐藏开关；关闭后不访问搜索服务、网页或搜索缓存。上传素材和搜索摘要均需教师核实。

上传支持 PPT/PPTX、PDF、DOC/DOCX、PNG/JPEG/WebP，单文件 25 MiB、最多 10 文件/项目、总计 100 MiB。拒绝加密文档、宏、伪装类型及超限 ZIP。旧 Office 文件在 Linux 容器内通过 LibreOffice 隔离转换；Windows 本地开发可先另存为现代格式。MinIO 素材为私有，下载必须认证并校验项目归属。

隐藏参数按服务端默认值解析。生成须带当前 `form_version`；排队期间页面配置变化时明确失败并返回需求页确认参数。隐藏素材后禁止新上传，新生成大纲也不使用旧素材；已有文件仍可查看和删除。修改需求、科目、年级、教材、时长、风格、联网方式或素材后保留旧大纲并要求重新生成；尺寸/音色调整不会使讲稿失效。

自定义时长大于 0 且最多 60 分钟。每段画面数按管理员范围校验；总讲稿估时超出配置容差会显示审核提示，估时不等于实际配音时长。`illustrations_per_minute` 用于第 3 部分实际图片生成。

解析/生成/改写/审核运行于 Celery + Redis，持久化 outbox 每 15 秒派发，带租约、心跳、并发限制和崩溃恢复；关闭网页不会取消任务。LangGraph checkpoint/Store 在 PostgreSQL `agent_state` 独立 schema，业务 Alembic 不管理此 schema。Key 不进入任务消息或 checkpoint。

## 测试

后端：在 `backend` 运行 `uv run --env-file ../.env pytest -q`。只可使用独立 `TEST_DATABASE_URL`，不能指向开发/生产库，不能并行运行两套后端测试（fixtures 会清理测试表）。

前端：在 `frontend` 运行 `npx vitest run --maxWorkers=1 --pool=threads` 和 `npm run build`（含 TypeScript 检查）。

真实模型质量、联网额度和长文档效果需教师从界面提交任务验收；开发检查不读取或测试生产 `model_configs`。设计与计划见 `docs/superpowers/specs/2026-10-16-edu-video-agent-design.md` 和 `docs/superpowers/plans/2026-10-16-outline-agent.md`。

2026-10-18 合并前验证：后端 **230 passed**，前端 **16 个文件、148 passed**，TypeScript 检查与 Vite 生产构建通过，`git diff --cached --check` 通过。

## 第二阶段交付与验收边界

- 管理员统一设置同时生成任务上限，每位教师独立享有该额度；大纲与后续视频生成共享该教师的计数规则，超过上限返回明确提示。
- 大纲任务支持离页继续、返回恢复、失败重试与版本冲突检查；完成通知按完成时间依次展示，每条三秒，无需手动确认。加载使用持续移动的斜纹，显示阶段、累计等待时间和断线提示。
- 当前数据库迁移 revision 为 `0004`（`0004_material_parse_warnings.py`）。审核结果绑定内容版本，旧数据缺少明确通过结论时视为待审核；保存与确认由后端独立校验。
- 自动化测试使用独立测试数据库和模拟模型响应，不等同于真实模型质量验收，不额外消耗模型或搜索额度。

后续检查项已记录在 `docs/phase-2-follow-up.md`：真实模型与复杂素材质量、多教师任务与异常恢复、保存及多标签页一致性、跨会话通知、偏好与联网实际效果、备份恢复演练。视频渲染与 MinerU 仍为后续扩展。
