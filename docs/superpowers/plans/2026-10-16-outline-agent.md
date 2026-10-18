# 大纲 Agent 实施计划 · 第 2/3 部分

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 让教师能输入需求、上传参考素材、生成并审核分段大纲、手动编辑或局部改写、保存草稿并隔天继续使用。

**Architecture:** 沿用 FastAPI、SQLAlchemy 异步数据层和 Vue 3。PostgreSQL 保存项目、素材索引、大纲和任务；MinIO 保存私有素材；LangGraph 负责生成、审核和教师确认中断。后台大纲任务提前使用设计中既定的 Celery + Redis，第 3 部分复用同一任务设施；不在 HTTP 请求或 FastAPI BackgroundTasks 中运行长任务。

**Tech Stack:** 现有 Python 3.12、uv、FastAPI、PostgreSQL、Alembic、Redis、httpx、Vue 3、TypeScript、Element Plus、Vitest；新增 LangGraph/LangChain、PostgreSQL checkpoint/store 适配器、Celery、MinIO Python SDK、python-multipart、python-pptx、PyMuPDF、python-docx；旧格式 PPT/DOC 用 LibreOffice 无界面转换。新依赖实施时核对官方兼容性、固定直接依赖版本并更新 uv.lock。

**Spec:** `docs/superpowers/specs/2026-10-16-edu-video-agent-design.md` 第 4—7、9—12 节；结合当前对话中已确定的 B 布局 + C 暖棕色配色、管理员/教师侧栏和三阶段制作流程。原规格中待确认的视觉描述以当前对话为准。

## Global Constraints

- 所有界面和业务错误提示使用简体中文，沿用 `api_error()`、`errorText()`、`require_active_user` 和 `require_admin`。
- 保留已有全部管理字段、提示、音色配置和认证行为，不重新设计登录页及管理后台。
- 三阶段固定为「输入需求 → 大纲草稿 → 视频预览」；本阶段交付前两个阶段，第 3 阶段显示尚未开放，不能伪造可播放视频或生成成功。
- 教师侧栏保留「视频制作、我的视频、草稿箱、我的偏好、账户设置」；账户设置不在本阶段新增功能。按 2026-10-16 用户最新要求，管理员仅使用管理后台，默认进入页面配置，不提供教师工作台，教师页面地址统一返回页面配置。
- 使用 `model_configs.service.resolve()` 解析模型配置。仅实际业务任务读取所需配置，不在开发诊断中读取或测试生产模型配置；测试使用独立数据库、模拟外部接口，不用真实 Key 产生费用。
- 关闭联网搜索表示禁止搜索服务、页面抓取及模型内置联网工具；文本/视觉模型仍须通过已配置 API 调用。上传素材作为不可信内容，不能改变系统规则或开启工具。
- 所有教师资源查询必须同时带 `owner_id`；不存在和属于他人的资源统一 404。管理员无权借管理接口查看其他教师项目内容。
- 不打印 `.env`、模型 Key、会话 Cookie 或存储凭据；后台模型配置只在任务开始时解析为内存快照，不把解密后的 Key 存入任务消息、checkpoint 或日志。
- 无语义向量检索时无需 Embedding；长素材首版先结构化切片加关键词检索，后续可按需要启用 pgvector。
- 不提交、推送、合并现有未提交修改，除非用户另行授权；实施前保留 UI 和配音修复工作。
- 现有真实入口是 `http://127.0.0.1:8080/`；每个可验收增量通过测试后构建并部署到该入口。

## 本轮明确的实施选择

1. **后台任务前移：** 大纲生成、解析及审核需要跨请求并支持重启恢复，因此本阶段引入已在总设计中选定的 Celery，不另造后台执行框架。
2. **搜索适配（用户已选定）：** 首个适配器使用 Tavily 搜索 API，配置沿用现有 `web_search` 用途，需要接口地址和 API Key，不要求模型名。Key 由管理员在后台填写并加密保存，不在对话中索要。默认不自动启用或覆盖现有真实配置；未配置时页面隐藏开关，服务端策略为关闭，告知本次未使用联网依据。任务要求联网但搜索服务临时失效时明确失败，不能假称检索成功。不新增自部署搜索容器。
3. **上传边界：** 单文件 25 MiB、每项目最多 10 个文件、累计 100 MiB；支持 PPT/PPTX、PDF、DOC/DOCX、PNG/JPEG/WebP。服务端检查格式与实际类型，ZIP 解包限制累计 200 MiB、最多 5000 项；拒绝加密文档及宏文件。限制集中在配置中，界面同步提示。
4. **旧格式转换：** `.ppt`、`.doc` 在隔离临时目录用 LibreOffice 转换为现代格式；有超时、退出码和输出校验，不能简单改扩展名。运行期禁止转换器访问外网；本机 Docker 资源不足时反馈失败，不默默丢弃素材。
5. **保存与冲突：** 手动保存草稿；编辑时显示未保存状态，离开有确认提示。所有更改以 `revision` 乐观锁提交，过期版本返回 409，避免多标签页覆盖。
6. **阶段终点：** 「确认大纲」保存已确认状态，允许回到编辑；视频渲染、试听、FFmpeg、视频历史版本和下载属于第 3 部分。不能把它们标成已完成。

## Review Focus

1. 教师 A 通过项目、素材、任务、依据或偏好 ID 访问教师 B 的数据：全部 404，存储无新增泄漏；Task 1/3/6/9 覆盖。
2. 页面配置在填表后变化、隐藏项被伪造或搜索关闭：后端仍按当前配置解析并禁止联网；Task 2/4 覆盖。
3. 文件伪装、压缩炸弹、转换挂死或扫描 PDF 空文本：安全失败或进入有依据页码的识别流程，不产生空白成功；Task 3 覆盖。
4. 重复点击、任务入队失败、worker 崩溃和多标签页同时修改：任务可重试且不重复落库，不覆盖较新编辑；Task 5/6 覆盖。
5. 模型返回非法 JSON、虚构来源 ID、超时、错误或素材中的恶意指令：保留草稿、中文提示、来源不被信任；Task 4/5 覆盖。

## File Structure

- `backend/app/projects/{schemas,service,router}.py`：教师项目和草稿生命周期。SQLAlchemy 新模型仍放 `backend/app/models.py`，迁移放 `backend/alembic/versions/0002_outline_projects.py`。
- `backend/app/materials/{schemas,storage,upload,parsers,service,router}.py`：对象存储、上传边界、文件转换和页/幻灯片/段落解析。
- `backend/app/outline/{schemas,evidence,model_client,graph,service,router}.py`：结构化大纲、证据、生成与审核、编辑确认。
- `backend/app/search/{schemas,tavily,service}.py`：可替换搜索适配与来源等级。
- `backend/app/jobs/{celery_app,tasks,service,dispatcher}.py`：后台任务、事务后派发、状态/进度和重启恢复。
- `backend/app/preferences/{schemas,service,router}.py`：按用户隔离的长期偏好。
- `backend/app/settings_store/form_values.py`：补齐与校验管理员配置的表单值。
- `frontend/src/api/{projects,materials,outline,preferences}.ts`：对应 API 类型和调用；复用现有错误处理。
- `frontend/src/views/workbench/{CreateVideoView,ProjectListView,OutlineView,PreferencesView}.vue`：现有侧栏入口替换为真实功能。
- `frontend/src/components/workbench/{CreationSteps,MaterialUpload,SegmentEditor,EvidencePanel}.vue`：三步指示、上传、大纲和依据组件。
- `backend/tests/test_{projects,form_values,materials,evidence,outline_graph,outline_edit,jobs,preferences,admin_route_guards,migrations}.py`、对应 `frontend/tests/*.spec.ts`。

## 数据与接口约定

- `VideoProject`：UUID、owner_id、title、prompt、resolved_form_values、status、revision、timestamps；状态 `draft / outlining / outline_ready / outline_confirmed / failed`，不混用第 3 部分视频状态。
- `Material`：UUID、project_id、owner_id、原文件名、私有 object_key、类型/大小、解析状态和错误。`MaterialChunk` 记录稳定 ID、文件/页码/幻灯片/段落定位及文本；图片切片引用私有存储对象。
- `OutlineSegment`：稳定 UUID、position、title、objective、narration、visuals、evidence_ids、content_kind、review_notes、estimated_duration_seconds、content_revision、reviewed_revision；`visuals` 取插图/数学图形/公式/学科示意图/文字卡五类。
- `Evidence`：UUID、project_id、owner_id、claim、source_type、source_ref、location、excerpt、source_grade、verification_status。联网来源保存真实返回标题/URL；知识无依据记为 `unverified`，情景演绎使用明确标记。
- `OutlineJob`：UUID、owner_id、project_id、kind、status、stage、progress、error_message、expected_revision、idempotency_key、租约与时间戳；执行状态 `pending / running / succeeded / failed`。
- `POST /api/projects` 创建草稿；`GET /api/projects?scope=all|drafts` 列表；`GET/PATCH/DELETE /api/projects/{id}` 查看/保存/删除自己的项目。创建、更新返回 `ProjectView`，删除 204。
- `POST /api/projects/{id}/materials` multipart 上传，返回 `MaterialView` 和解析任务 ID；`GET /api/projects/{id}/materials` 列表；`GET/DELETE /api/projects/{id}/materials/{material_id}` 查看状态/删除；下载另走 `.../{material_id}/download`。
- `POST /api/projects/{id}/outline/generate`、`POST .../rewrite` 返回 202 `JobView`；`GET /api/jobs/{job_id}` 返回进度；本阶段前端轮询，页面关闭不取消任务。
- `GET/PUT /api/projects/{id}/outline` 获取/保存大纲；`POST .../review` 审核变更段；`POST .../confirm` 确认大纲。每次修改传 `revision`，成功返回递增版本；读不触发外部付费请求。
- `GET /api/projects/{id}/evidence/{evidence_id}` 返回可见依据和定位，不返回模型配置或其他项目素材。
- `GET/POST /api/preferences`、`PATCH/DELETE /api/preferences/{id}` 管理自己的偏好；`POST /api/preferences/suggestions/{id}/accept` 明确确认候选后保存。
- 所有 `revision` 冲突均 409 `revision_conflict`；任务重复提交使用 owner+project+operation+idempotency_key 唯一约束；跨用户查询统一 404。

### Task 1: 项目、草稿和权限基线

**Files:** `backend/app/models.py`、`backend/app/projects/`、`backend/alembic/versions/0002_outline_projects.py`、`backend/app/main.py`；测试 `test_projects.py`、`test_admin_route_guards.py`、`test_migrations.py`、`conftest.py`。

**Interfaces:** `get_owned_project(db, owner_id: UUID, project_id: UUID) -> VideoProject`；`CurrentTeacher = Annotated[User, Depends(require_active_user)]`。所有后续任务使用此查询入口。

- [x] 写失败测试：`test_project_owner_isolation` 验证 A 对 B 的读写删均 404；`test_project_revision_conflict` 验证旧 revision 不覆盖；停用/待审核用户不能调用业务 API。
- [x] 用测试库运行 `pytest -q tests/test_projects.py tests/test_admin_route_guards.py tests/test_migrations.py`，确认新增用例因功能缺失失败。
- [x] 实现项目 CRUD、分页和 `scope=drafts`；草稿指尚无成片的未完成项目，本阶段所有项目均可继续编辑，失败项目保留。列表支持删除确认；管理员用户列表新增视频项目数量，不提供他人内容入口。
- [x] 实现管理员路由依赖检查；更新 conftest 清理顺序，迁移测试使用独立临时测试库/模式，不碰开发库；执行 upgrade/check，不能以 create_all 代替迁移验证。
- [x] 运行上述用例及完整后端测试，预期 PASS；未授权前不提交。

### Task 2: 服务端表单默认值与真实新建表单

**Files:** `backend/app/settings_store/form_values.py`、`projects/schemas.py`、`public/router.py`；`frontend/src/api/projects.ts`、`views/workbench/CreateVideoView.vue`、`components/workbench/CreationSteps.vue`、路由/HomeView；测试 `test_form_values.py`、`create-video.spec.ts`。

**Interfaces:** `resolve_form_values(config: FormFieldsConfig, submitted: dict, *, voices: list[Voice], search_ready: bool) -> ResolvedFormValues`；复用 `GET /api/config/form`，绝不把生成参数传到教师浏览器。

- [x] 写失败测试：隐藏项使用管理员默认且不能被 payload 覆盖；教材随科目匹配；自定义分钟数大于 0；可见字段错误值返回 422；网页搜索不可用时最终策略为 false。
- [x] 运行 `pytest -q tests/test_form_values.py` 和 `npx vitest run tests/create-video.spec.ts --maxWorkers=1 --pool=threads`，确认失败。
- [x] 实现纯解析函数及服务端配置读取，在创建/生成时校验；`duration=custom` 携带 `custom_duration_minutes`。若表单已过期，以 409 `form_config_changed` 提示刷新，不能悄悄改教师已选择的可见值。
- [x] 实现完整输入需求表单、全部可见参数、动态教材、系统不可用提示、保存草稿与继续；使用现有暖棕色 token 和布局。不要提前放入假的素材或生成结果。
- [x] 运行对应前后端测试并构建，预期 PASS；验证 `system_available=false` 时不能提交生成。

### Task 3: MinIO、素材上传及解析

**Files:** `backend/app/materials/`、`backend/app/jobs/` 基础设施、模型/迁移扩展、`config.py`、Dockerfile、Compose、`.env.example`、`frontend/nginx.conf`；`MaterialUpload.vue`、`api/materials.ts`；测试 `test_materials.py`、`test_jobs.py`、`materials.spec.ts`。

**Interfaces:** `put_material(owner_id, project_id, material_id, stream) -> object_key`；`parse_material(material_id: UUID) -> list[MaterialChunkData]`；private key 为 `users/{owner_id}/projects/{project_id}/materials/{material_id}/...`，禁止使用原文件名作为路径。

- [x] 写失败测试：跨用户下载 404；缺失/错误 Origin 的 multipart 请求拒绝；Origin 同主机不同端口拒绝；超限、扩展名伪装、ZIP 超限、密码文档均明确失败；扫描 PDF 走视觉识别并保留页码。
- [x] 运行 `pytest -q tests/test_materials.py`、前端上传用例，确认失败。
- [x] 在本任务先建立共用 jobs/worker 的任务持久化、幂等提交、outbox 派发与租约恢复基础设施，供解析任务使用；Task 5 扩展大纲任务和 LangGraph，不能让第一批上传依赖尚未实现的 Task 5。测试 worker 重启后解析任务可以继续。
- [x] 接入私有 MinIO、受认证下载、分块大小统计和校验，异步解析任务；PPTX/PDF/DOCX 提取文本和图片，PPT/DOC 转换后解析。视觉输入只发给当前任务配置的看图模型，不抓取任意 URL。
- [x] 上传路由单独放宽 nginx 到 26m 并配置代理 1.1/超时；项目总大小与数量在数据库事务内校验。临时卷只给 uid 10001 可写；MinIO 凭据通过部署配置注入，不公开 bucket，不将控制台暴露外网。
- [x] 对象写成功而 DB 写失败时补偿清理；删除正在使用的素材返回 409；解析错误保留原因并可重试。转换进程限定时间/资源，测试包含损坏 PPT 和转换超时。
- [x] 用合成小文件验证所有格式与首尾定位；运行测试，检查上传、下载、解析失败均不泄漏路径/凭据。

### Task 4: 依据检索与搜索开关

**Files:** `backend/app/search/`、`outline/evidence.py`、`model_configs/{service,probe,router}.py`、`frontend/src/views/admin/ModelConfigDialog.vue`/`ModelConfigTab.vue`；测试 `test_evidence.py`、`test_search.py`、`test_probe.py`、模型配置和后台现有测试。

**Interfaces:** `collect_evidence(project, chunks, config_snapshot, *, allow_web_search: bool) -> list[EvidenceData]`；`search(query: str, config: ResolvedConfig) -> list[SearchHit]`。模型输出只能引用本次提供的 Evidence ID。

- [x] 写失败测试：搜索关闭时搜索/抓取适配器调用次数为 0；无依据显示未核实；素材优先，冲突有提示；虚构来源 ID 拒绝或标无依据；百科为次级、论坛不能独立佐证史实。
- [x] 写失败测试：web_search 启用和解析时需要地址和 Key、不需要模型名；未启用时仍可保存不完整配置；搜索按官方协议发送查询与鉴权；空结果与服务失败区分，401/403、额度不足、429 和超时有中文提示；所有错误与记录均不泄漏 Key。
- [x] 运行 `pytest -q tests/test_evidence.py tests/test_search.py tests/test_probe.py` 及配置测试，确认新增失败。
- [x] 实施时核对 Tavily 官方搜索 API 的端点、鉴权和请求参数后实现适配器，统一结果为标题、链接、摘要及实际返回的发布时间；不得把摘要当已核实的原文，缺字段不编造。管理员测试连接走同一适配器验证搜索响应，不只检查首页 HTTP 200。
- [x] 在现有联网搜索配置中补充 Tavily 地址、Key 及测试说明，Key 使用既有加密与掩码机制；保留其他模型字段和提示，不自动覆盖真实配置，不新增搜索容器或搜索基础设施凭据。
- [x] 设置请求超时、有限重试、并发限制与短时缓存，明确错误和额度反馈；不能用无限重试产生额外调用。缓存不得绕过本次联网关闭规则。
- [x] 联网查询只在后端确定 allow_web_search=true 后执行，不让模型自行改开关；教师端不直接连接 Tavily。
- [x] 实现素材切片检索、来源等级与证据绑定；上传文本和检索结果隔离为不可信上下文。来源等级只是辅助，不声称自动证实全部内容。
- [x] 运行开关、错误响应、密钥脱敏、来源真实性测试；用模拟 HTTP 覆盖 401/403/429/超时、无结果和非法响应，预期 PASS。实际搜索验收由管理员点击测试或明确授权后进行；搜索失效不能影响不联网的大纲流程。

### Task 5: 大纲生成、独立审核及持久后台任务

**Files:** `backend/app/outline/{schemas,model_client,graph,service,router}.py`、`backend/app/jobs/`、数据库模型/迁移、资源启动关闭、Docker/Compose；测试 `test_outline_graph.py`、`test_jobs.py`。

**Interfaces:** `start_outline(owner_id, project_id, expected_revision, idempotency_key) -> JobView`；`build_outline_graph(checkpointer, store)`；状态依次解析素材→依据→生成→审核→interrupt 等待教师确认。异步应用使用相应 AsyncPostgresSaver/Store，worker 使用匹配运行模式的适配器，不能混用连接。

- [x] 写失败测试：完整流程生成 schema 正确的段落并停在确认点；生成/审核使用不同用途配置；非法 JSON 有有界修复重试，失败保留草稿；持久 checkpoint 在进程重建后可恢复。
- [x] 写失败测试：重复幂等键只有一个任务；任务提交后 broker 故障仍可派发；worker 崩溃可恢复；旧任务不能覆盖新 revision；任务消息和 checkpoint 不包含 API Key。
- [x] 运行 `pytest -q tests/test_outline_graph.py tests/test_jobs.py`，确认失败。
- [x] 实现结构化输出：完整逐字稿、教学目标、五类画面、依据、内容性质、审核提示及预计时长；默认开场/小结，按字数/英文词数估算并标明只是估计。模型不能生成可执行代码。
- [x] 使用独立审核用途检查事实/公式/年级/出处/演绎及多音字提醒；服务端额外强制无依据标记和合法 Evidence ID，不把审核通过包装成事实保证。
- [x] 使用数据库任务/outbox + 周期派发恢复入队间隙；Celery 有租约/幂等提交，重试次数使用管理员配置。模型响应脱敏，进度仅包含阶段/计数。
- [x] `thread_id` 由服务端绑定 owner/project；checkpointer/store 初始化单独管理，正式启用前测试升级步骤。任务中不长时间持有业务 DB 事务。
- [x] 运行完整后端测试和 worker 集成测试；中断并重启 worker 后，项目仍可查询并恢复，预期 PASS。

### Task 6: 编辑、局部改写、重新审核与确认

**Files:** `outline/service.py`、`outline/router.py`、`outline/graph.py`；测试 `test_outline_edit.py`。

**Interfaces:** `save_outline(owner_id, project_id, revision, segments) -> OutlineView`；`rewrite_segments(..., segment_ids, instruction, revision, idempotency_key) -> JobView`；`confirm_outline(..., revision) -> OutlineView`。

- [x] 写失败测试：编辑一段只使该段审核过期；增删重排保留稳定 UUID，纯重排不重审未变内容；旧 revision 409；改写他人段落 ID 404。
- [x] 写失败测试：只有已保存且变更段审核完成的大纲能确认；审核有提示仍允许教师明确确认；正文修改期间旧审核结果不能覆盖新版本。
- [x] 运行 `pytest -q tests/test_outline_edit.py`，确认失败。
- [x] 实现段落内容指纹、局部上下文改写和部分复审；确认通过 LangGraph 恢复等待节点并持久化，不触发视频任务。
- [x] 尺寸/音色修改不重写讲稿；科目/年级/教材/时长/风格/联网/素材更改先提示将重新生成，大纲快照保留至新任务成功，失败不能清空旧成果。
- [x] 运行并发、隔离、局部审核测试，预期 PASS。

### Task 7: 大纲页、进度和依据交互

**Files:** `frontend/src/api/outline.ts`、`views/workbench/OutlineView.vue`、`SegmentEditor.vue`、`EvidencePanel.vue`、路由及对应测试。

**Interfaces:** 仅消费前述 OutlineView、JobView、Evidence；已保存 revision 是提交基础；不向浏览器暴露 LangGraph thread ID 或内部 checkpoint。

- [x] 写失败测试：按段展示全部字段；本地编辑可保存；添加/删除/排序；改写仅发选中 ID；依据打开原文定位/安全链接；任务失败后仍保留输入。
- [x] 运行 `npx vitest run tests/outline-view.spec.ts --maxWorkers=1 --pool=threads`，确认失败。
- [x] 实现三步指示、阶段进度轮询（2 秒，仅页面可见时）、重试/恢复、错误反馈；隐藏页面暂停轮询、销毁清理，返回页面从后端恢复。
- [x] 实现未保存提示、冲突提示、待复审标记、审核红色提示和「确认大纲」；视频预览标记下一阶段开放。
- [x] 完整前端测试、TypeScript 检查和构建 PASS；375/768/1440 宽度验证布局、键盘操作与错误态。

### Task 8: 我的视频、草稿箱及管理计数

**Files:** `frontend/src/views/workbench/ProjectListView.vue`、`api/projects.ts`、`AppLayout.vue`、HomeView/路由、后台 UsersTab 与类型；后端 `admin/users_router.py`、`admin/schemas.py`；相关测试。

**Interfaces:** 复用 `scope=all|drafts` 项目列表和分页；管理员计数字段 `video_count` 为自己创建的视频项目数量，界面标清项目数，不能假称已有成片。

- [x] 写失败测试：空列表、分页、失败/待确认状态、继续编辑/删除确认；侧栏路径和当前项正确；管理员默认仍是页面配置，后台不出现重复 tabs。
- [x] 运行新增页面及现有 layout/admin/guards 测试，确认失败。
- [x] 实现真实项目列表、草稿入口、状态时间和继续编辑；无成片不用假缩略图。按用户最新要求，管理员始终使用管理导航，不提供教师入口，访问教师页面时返回页面配置。
- [x] 扩展用户计数查询和类型，保留原有所有用户管理操作；测试无 N+1 查询、无项目内容泄露。
- [x] 运行前后端测试及构建，预期 PASS。

### Task 9: 教师确认的长期偏好

**Files:** `backend/app/preferences/`、LangGraph Store 资源、outline 上下文组装；`frontend/src/api/preferences.ts`、`views/workbench/PreferencesView.vue`；测试 `test_preferences.py`、`preferences.spec.ts`。

**Interfaces:** Store namespace 固定为 `('users', str(owner_id), 'preferences')`；候选偏好与正式偏好分离；建议只在检测到重复编辑习惯后提出，点击接受才写入正式 namespace。

- [x] 写失败测试：A 看不到/改不了 B 的偏好；候选未接受不生效；关闭长期记忆不读取/使用/新增；本次要求覆盖旧偏好；事实内容不进入偏好生成通道。
- [x] 运行 `pytest -q tests/test_preferences.py` 及前端对应测试，确认失败。
- [x] 实现手动增删改查和候选确认，偏好限制为教学方式/表达/画风/常用设置；拒绝把讲稿、史实和来源当偏好保存，人工输入不适合偏好时返回明确提示，不能仅依赖模型判定。
- [x] 首版候选采用可解释规则检测重复的长度/风格调整，不在后台偷偷存储或跨用户推断；全局关闭时页面说明不可用，保留已有数据，重新开启后才恢复使用。
- [x] 重启后确认偏好仍存在，运行隔离和开关测试，预期 PASS。

### Task 10: 集成验收和真实部署

**Files:** `README.md`、`任务存档.md`、Compose/部署说明、集成用例；需要时调整实际实现发现的协议缺口。

- [x] 检查以上任务覆盖原规格；未实现项明确列为第 3 部分，不改成已完成。更新实际端点、模型能力、备份/迁移和部署步骤。
- [x] 运行完整后端测试：`cd backend; & 'C:/Users/Lenovo/.local/bin/uv.exe' run --env-file ../.env pytest -q`；迁移测试仅临时测试数据库，不能在开发库执行 drop/create。
- [x] 运行完整前端测试和构建：`npx vitest run --maxWorkers=1 --pool=threads`、`npm run build`；`git diff --check`，预期无失败、无新警告。
- [x] 使用模拟模型/搜索和合成文档串通：教师登录→保存草稿→上传→大纲生成→局部改写→审核→确认→退出重进；覆盖搜索关闭、失败重试、worker 重启、两个用户和 revision 冲突。
- [x] 构建部署前后端、worker、MinIO；保持数据库卷和真实模型配置，处理 nginx 后端地址变化，验证 8080 健康/资源/上传代理及 Tavily 配置入口。不可重置真实数据库或用测试 fixtures 操作生产应用。
- [ ] 真实模型验收由教师点击任务或明确授权后运行；没有真实任务结果时报告自动化结果与剩余实测项，不宣称模型生成已实测成功。
- [x] 给出简洁交付说明和已实现入口，等待用户实测后再开始第 3 部分视频生成；不自动提交/推送。

## 实施顺序和验收增量

1. **第一批（Task 1—3）**：真实新建表单、项目/草稿、上传与解析，先部署可操作入口。
2. **第二批（Task 4—7）**：真实大纲生成、来源、审核和编辑确认，交付核心闭环。
3. **第三批（Task 8—10）**：列表完善、长期偏好、隔离/重启/迁移验收与文档。

## 自检结果

- 原规格第 4—7 节的输入/大纲/依据/审核由 Task 2—7 覆盖；第 9 节基础设施由 Task 3/5 覆盖；第 10—11 节教师页面/隔离/管理计数由 Task 1/7/8 覆盖；第 12 节记忆由 Task 5/9 覆盖。
- 音色试听、视频预览播放、渲染、成片版本、下载属于第 3 部分；本阶段不伪造入口成功。账户设置保留现有入口。
- 五类重点失败场景均绑定到具体测试任务；项目/段落/任务 revision 和 owner_id 边界一致。
- 用户已明确选定 Tavily，计划已恢复为 Tavily 搜索接入；上传限制、Celery 前移和旧格式转换仍按上述实施建议执行。本轮仅更新计划，尚未安装或部署搜索服务。


## 2026-10-16 执行验收记录

任务1—9已实现，任务10的自动化/本机部署/文档已执行；真实模型及Tavily额度效果由教师在界面提交验收，不把它视作开发阶段已付费实测。上述勾选代表对应实现/自动化与检查已覆盖，并不表示逐条人工完成每一种格式和每一种故障组合。

- 静态最终审查的5项Important均已修复并由同一审查代理复核闭合。关键修复有RED回归记录，最终完整测试日志保存在本计划ledger工作目录。
- 实际部署为8080，共7个服务运行，backend/postgres健康。迁移0003、alembic check无漂移，worker ping成功。
- 合成素材在部署容器中验证私有MinIO写/读/删、真实DOC与PPT转换后解析。现代文档、扫描PDF、损坏文档与转换超时受自动测试覆盖；没有上传个人文件用于模型试验。
- UI在真实8080检查管理员默认入口、教师五项侧栏、需求表单、偏好页及未保存离开提示；375/768/1440布局宽度检查无整页水平溢出，临时viewport已恢复。大纲内容与编辑动作主要通过组件/API集成测试验收，真实生成后视觉还待教师查看。
- 已核对Tavily官方Search API的POST端点、Bearer鉴权、basic/search_depth/max_results。只抓取公开文档，不使用真实生产配置发起搜索。
- 实施偏差：自定义时长最多60分钟；隐藏素材保留下载/删除但禁止新上传与新生成使用；任务保存表单版本并在执行前拒绝过期配置；时长超差作审核提示，每分钟插图限制留第3部分。
- 无提交、推送、合并或清理既有未提交修改；第3部分尚未开始。
