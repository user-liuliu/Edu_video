# 平台基础（账号、管理后台、模型配置）实施计划 · 第 1/3 部分

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搭好能在本地 Docker 里运行的平台底座：老师自助注册、管理员审核，管理后台有三个选项卡（页面配置、模型配置、用户管理），前端外壳和路由守卫也一并完成。

**Architecture:** 后端是一个 FastAPI 单体应用，按功能分包（auth、admin、settings_store、model_configs、public）。数据层用 SQLAlchemy 2 异步接 PostgreSQL；Redis 只负责登录失败限流；会话用签名 cookie；模型 key 用 Fernet 加密后存库。前端用 Vue 3、Vite 和 Element Plus，和后端同源，通过 `/api` 访问。

**Tech Stack:** Python 3.12、uv、FastAPI、SQLAlchemy 2（asyncpg）、Alembic、pydantic-settings、argon2-cffi、cryptography、httpx、redis-py、itsdangerous；pytest、pytest-asyncio、fakeredis、respx；Vue 3、TypeScript、Vite、Vue Router、Pinia、Element Plus、Vitest；Docker Compose（`pgvector/pgvector:pg16`、`redis:7-alpine`）。

**Spec:** `docs/superpowers/specs/2026-10-16-edu-video-agent-design.md`（本计划实现第 2、3、5、9、10、11 节中的账号、后台和配置部分）

**后续计划（不在本计划内）：**
- 第 2 部分「大纲 agent」：视频项目、MinIO 和素材上传解析、按管理员配置补全隐藏项的默认值、依据检索与联网开关、大纲生成与审核、LangGraph checkpointer、长期偏好记忆、联网搜索服务接入（包括它的连接测试），以及新建视频页、大纲编辑页、我的偏好页、用户列表的"视频数"列。
- 第 3 部分「视频生成」：Celery、豆包配音（包括音色试听）、插图和图片检查、数学和学科模板、FFmpeg 合成、按段增量、版本、进度、预览下载。

## Global Constraints

- 所有命令都在 Windows 的 Git Bash 下执行，路径用正斜杠。
- Python 3.12，依赖用 uv 管理，`uv.lock` 要提交（版本由 lock 文件固定）。前端用 npm，安装时加 `--save-exact`，`package-lock.json` 要提交。
- 不要新增本计划没列出的第三方依赖；确实需要时先问用户。
- 密钥只能放在 `.env`（不提交）和数据库（加密存储）里。任何接口响应、日志、异常信息里都不能出现完整 key。
- 接口错误统一格式为 `{"detail": {"code": "<code>", "message": "<中文提示>"}}`；FastAPI 自带的 422 校验错误保持原样。
- 所有接口路径以 `/api` 开头；前端和后端同源。
- 界面文字全部用简体中文。
- 用户名：去掉首尾空格后 3–32 位，只能包含字母、数字、下划线和汉字（Python 正则 `^[A-Za-z0-9_一-鿿]+$`），唯一性检查不区分大小写。密码长度 8–128 位。
- 只有 `status=active` 的用户能调用业务接口；管理后台接口在服务端校验 `role=admin` 且 `status=active`。
- 系统里至少要保留一个 `role=admin` 且 `status=active` 的用户。
- 第一版不做删除用户。
- Commit 信息最后一行写 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`。
- 后端测试命令：`cd backend && uv run --env-file ../.env pytest -q`；前端测试命令：`cd frontend && npx vitest run`。

## Review Focus

1. 用户名的大小写和首尾空格：`"Teacher_Wang "` 和 `"teacher_wang"` 算同一个用户名。注册时返回 `username_taken`，登录时两种写法都能登录。测试在 Task 5。
2. 管理员编辑模型配置但没有重新填 key：请求里不带 `api_key`（或者值为 null）时保留原来的 key，只有 `clear_api_key=true` 才清空。测试在 Task 8。
3. 接口地址末尾的斜杠：`https://r.example.com/v1/` 和 `https://r.example.com/v1` 拼出来的都应该是 `https://r.example.com/v1/chat/completions`。测试在 Task 9。
4. 管理员删掉的选项正好是默认值，或者是某个科目的默认教材版本：保存时返回 422，提示"默认值必须在可选值中"，不保存。测试在 Task 4。
5. `.env` 里的 `MASTER_KEY` 换了，库里的 key 解不开：模型配置列表显示 `api_key_status="undecryptable"`，系统判定为不可用，不能报 500。测试在 Task 8。

---

## File Structure

```
.gitignore  .env.example  docker-compose.yml
infra/postgres/init/01-test-db.sql        # 创建 eduvideo_test 测试库
backend/
  pyproject.toml  uv.lock  alembic.ini  Dockerfile
  alembic/env.py  alembic/versions/0001_initial.py
  app/
    main.py            # create_app()，注册中间件和路由
    config.py          # Settings（读取 .env）
    db.py              # 异步 engine、session、get_session 依赖
    redis_client.py    # get_redis 依赖
    errors.py          # api_error()
    models.py          # User、SystemSetting、ModelConfigRow
    security.py        # 密码哈希、SecretBox、mask_secret
    purposes.py        # Purpose 枚举、中文名、必需用途
    cli.py             # bootstrap 命令：创建初始管理员
    auth/  schemas.py deps.py login_limiter.py router.py
    admin/ schemas.py user_actions.py users_router.py settings_router.py
    settings_store/ schemas.py defaults.py service.py
    model_configs/  schemas.py service.py probe.py router.py
    public/router.py   # GET /api/config/form
  tests/  conftest.py  test_*.py（每个任务一个）
frontend/
  package.json  vite.config.ts  Dockerfile  nginx.conf  index.html
  src/
    main.ts  App.vue  styles/tokens.css
    api/http.ts  api/auth.ts  api/admin.ts
    stores/auth.ts
    router/index.ts  router/guards.ts
    layouts/AppLayout.vue  layouts/AdminLayout.vue
    views/LoginView.vue RegisterView.vue AccountStatusView.vue HomeView.vue
    views/admin/PageConfigTab.vue ModelConfigTab.vue UsersTab.vue
  tests/  *.spec.ts
```

---

### Task 1: 仓库与后端骨架

**Files:**
- Create: `.gitignore`, `.env.example`, `docker-compose.yml`, `infra/postgres/init/01-test-db.sql`
- Create: `backend/pyproject.toml`, `backend/app/{__init__,main,config,db,redis_client,errors}.py`
- Test: `backend/tests/conftest.py`, `backend/tests/test_health.py`

**Interfaces:**
- Produces:
  - `app.config.Settings`（pydantic-settings，字段：`database_url: str`、`test_database_url: str = ""`、`redis_url: str`、`master_key: str`、`session_secret: str`、`cookie_secure: bool = False`、`initial_admin_username: str | None = None`、`initial_admin_password: str | None = None`）；`get_settings() -> Settings`（用 lru_cache 缓存）
  - `app.main.create_app(settings: Settings | None = None) -> FastAPI`：把 settings、engine、sessionmaker、redis 放进 `app.state`；`app = create_app()` 只在 `if __name__` 或 uvicorn 的工厂模式下创建（用 `uvicorn app.main:create_app --factory` 启动）
  - `app.db.get_session(request) -> AsyncIterator[AsyncSession]`、`app.redis_client.get_redis(request) -> Redis`（都从 `request.app.state` 取）
  - `app.errors.api_error(status: int, code: str, message: str) -> HTTPException`
  - `GET /api/health` → `{"status": "ok", "db": true}`
  - conftest fixtures：`settings`（用 `TEST_DATABASE_URL`，`master_key` 每次测试会话现生成一个 Fernet key）、`app`（`create_app(settings)`，redis 换成 `fakeredis.aioredis.FakeRedis()`）、`client`（httpx `AsyncClient` + `ASGITransport`，base_url 为 `http://test`）

- [ ] **Step 1: 初始化 git 和忽略文件**

运行 `git init`。`.gitignore` 写入：`.env`、`__pycache__/`、`.venv/`、`.pytest_cache/`、`node_modules/`、`frontend/dist/`、`.superpowers/`。

- [ ] **Step 2: 写 `.env.example`、`docker-compose.yml` 和测试库初始化脚本**

`.env.example` 的键：`POSTGRES_USER=eduvideo`、`POSTGRES_PASSWORD=change-me`、`POSTGRES_DB=eduvideo`、`DATABASE_URL=postgresql+asyncpg://eduvideo:change-me@localhost:5432/eduvideo`、`TEST_DATABASE_URL=postgresql+asyncpg://eduvideo:change-me@localhost:5432/eduvideo_test`、`REDIS_URL=redis://localhost:6379/0`、`MASTER_KEY=`（注释写生成命令 `uv run python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"`）、`SESSION_SECRET=`、`COOKIE_SECURE=false`、`INITIAL_ADMIN_USERNAME=admin`、`INITIAL_ADMIN_PASSWORD=`。

`docker-compose.yml` 里有两个服务：`postgres`（镜像 `pgvector/pgvector:pg16`，端口 `127.0.0.1:5432:5432`，挂载 `./infra/postgres/init` 到 `/docker-entrypoint-initdb.d`，数据放在 named volume 里，带 `pg_isready` 健康检查）和 `redis`（镜像 `redis:7-alpine`，端口 `127.0.0.1:6379:6379`）。`01-test-db.sql` 的内容是 `CREATE DATABASE eduvideo_test;`。

- [ ] **Step 3: 起基础设施**

把 `.env.example` 复制成 `.env`，填入随机生成的 `POSTGRES_PASSWORD`、`MASTER_KEY`、`SESSION_SECRET`（`python -c "import secrets;print(secrets.token_urlsafe(48))"`），以及 `INITIAL_ADMIN_PASSWORD`，然后运行 `docker compose up -d postgres redis`。
Expected: `docker compose ps` 里两个服务都是 healthy 或 running。

- [ ] **Step 4: 初始化后端项目并安装依赖**

```bash
cd backend && uv init --app --python 3.12 --name edu-video-backend --no-readme
uv add fastapi "uvicorn[standard]" "sqlalchemy[asyncio]" asyncpg alembic pydantic-settings argon2-cffi cryptography httpx redis itsdangerous
uv add --dev pytest pytest-asyncio fakeredis respx
```
在 `pyproject.toml` 里加：`[tool.pytest.ini_options] asyncio_mode = "auto"`、`asyncio_default_fixture_loop_scope = "session"`、`asyncio_default_test_loop_scope = "session"`。

- [ ] **Step 5: 写失败的测试**

```python
async def test_health_reports_db_ok(client):
    r = await client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "db": True}
```

- [ ] **Step 6: 运行，确认失败**

Run: `cd backend && uv run --env-file ../.env pytest tests/test_health.py -q`
Expected: FAIL（`app.main` 还不存在）

- [ ] **Step 7: 实现 config、db、redis_client、errors、main**

`create_app` 要挂上 Starlette 的 `SessionMiddleware`，参数为 `secret_key=settings.session_secret`、`session_cookie="ev_session"`、`same_site="lax"`、`https_only=settings.cookie_secure`、`max_age=14*24*3600`。health 接口执行 `SELECT 1`。

- [ ] **Step 8: 运行，确认通过**

Run: `cd backend && uv run --env-file ../.env pytest -q`
Expected: 1 passed

- [ ] **Step 9: Commit**

```bash
git add .gitignore .env.example docker-compose.yml infra backend
git commit -m "chore: scaffold repo, infra compose and FastAPI skeleton"
```

---

### Task 2: 安全工具（密码哈希、key 加密、脱敏）

**Files:**
- Create: `backend/app/security.py`
- Test: `backend/tests/test_security.py`

**Interfaces:**
- Produces:
  - `hash_password(raw: str) -> str`、`verify_password(raw: str, hashed: str) -> bool`（argon2-cffi 的 `PasswordHasher`；哈希格式不合法时返回 False，不抛异常）
  - `class SecretBox(master_key: str)`：`encrypt(plain: str) -> str`、`decrypt(token: str) -> str`；解密失败时抛 `SecretDecryptError`（同一个模块里定义）
  - `mask_secret(plain: str) -> str`：长度不超过 4 时返回 `"****"`，否则返回 `"****" + plain[-4:]`

- [ ] **Step 1: 写失败的测试**

```python
def test_password_roundtrip():
    h = hash_password("abcd1234"); assert verify_password("abcd1234", h); assert not verify_password("abcd12345", h)
def test_verify_garbage_hash_is_false():
    assert verify_password("x", "not-a-hash") is False
def test_secretbox_roundtrip_and_wrong_key():
    k1, k2 = Fernet.generate_key().decode(), Fernet.generate_key().decode()
    t = SecretBox(k1).encrypt("sk-abc"); assert SecretBox(k1).decrypt(t) == "sk-abc"
    with pytest.raises(SecretDecryptError): SecretBox(k2).decrypt(t)
def test_mask_secret():
    assert mask_secret("sk-12345678") == "****5678"; assert mask_secret("abc") == "****"
```

- [ ] **Step 2: 运行，确认失败**

Run: `cd backend && uv run --env-file ../.env pytest tests/test_security.py -q`
Expected: FAIL（ImportError）

- [ ] **Step 3: 实现 `app/security.py`**

- [ ] **Step 4: 运行，确认通过**

Run: 同 Step 2
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/security.py backend/tests/test_security.py
git commit -m "feat: add password hashing and secret encryption helpers"
```

---

### Task 3: 数据模型与迁移

**Files:**
- Create: `backend/app/models.py`, `backend/app/purposes.py`, `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/versions/0001_initial.py`
- Modify: `backend/tests/conftest.py`（加 fixture）
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Consumes: `hash_password`（Task 2）
- Produces:
  - `app.purposes.Purpose(StrEnum)`：`outline_llm`、`review_llm`、`vision_llm`、`image_gen`、`embedding`、`tts`、`web_search`；`PURPOSE_LABELS: dict[Purpose, str]` = 写大纲/讲稿、审核、看图识别、画插图、Embedding、配音、联网搜索；`REQUIRED_PURPOSES = {outline_llm, review_llm, vision_llm, image_gen, tts}`
  - `app.models.Base`（DeclarativeBase）
  - `UserRole(StrEnum)`: `teacher`、`admin`；`UserStatus(StrEnum)`: `pending`、`active`、`rejected`、`disabled`
  - `User`：`id: UUID`（主键，默认 uuid4）、`username: str(32)`、`password_hash: str`、`role`（默认 teacher）、`status`（默认 pending）、`session_version: int = 1`、`created_at`、`reviewed_at: datetime | None`、`reviewed_by: UUID | None`（外键 users.id）；唯一索引 `ix_users_username_lower` 建在 `lower(username)` 上
  - `SystemSetting`：`key: str`（主键）、`value: JSONB`、`updated_at`
  - `ModelConfigRow`（表名 `model_configs`）：`purpose: str`（主键）、`base_url: str = ""`、`api_key_encrypted: str | None`、`model: str = ""`、`enabled: bool = False`、`extra: JSONB = {}`、`last_test_ok: bool | None`、`last_test_message: str | None`、`last_tested_at: datetime | None`、`updated_at`
  - conftest fixtures：`db_engine`（session 作用域：`drop_all` 后 `create_all`）、`db`（每个测试一个 `AsyncSession`，测试结束后 `TRUNCATE users, system_settings, model_configs CASCADE`）、`make_user(username="t1", password="pass1234", role="teacher", status="active") -> User`

- [ ] **Step 1: 写失败的测试**

```python
async def test_username_unique_case_insensitive(db, make_user):
    await make_user("Teacher_Wang")
    with pytest.raises(IntegrityError):
        await make_user("teacher_wang")
async def test_user_defaults(db):
    u = User(username="x1", password_hash="h"); db.add(u); await db.commit()
    assert (u.role, u.status, u.session_version) == ("teacher", "pending", 1)
```

- [ ] **Step 2: 运行，确认失败**

Run: `cd backend && uv run --env-file ../.env pytest tests/test_models.py -q`
Expected: FAIL（ImportError）

- [ ] **Step 3: 实现 `purposes.py`、`models.py` 和 conftest 里的 fixture**

- [ ] **Step 4: 运行，确认通过**

Run: 同 Step 2
Expected: 2 passed

- [ ] **Step 5: 配置 Alembic（异步模板），生成初始迁移**

```bash
cd backend && uv run alembic init -t async alembic
```
`env.py` 从 `get_settings().database_url` 读取连接串，`target_metadata = Base.metadata`。然后运行 `uv run --env-file ../.env alembic revision --autogenerate -m initial`，把生成的文件改名为 `0001_initial.py`；检查 `lower(username)` 的函数索引有没有生成出来，没有就手动补上 `op.create_index(..., [sa.text("lower(username)")], unique=True)`。

- [ ] **Step 6: 在开发库上迁移，并检查模型和迁移是否一致**

Run: `cd backend && uv run --env-file ../.env alembic upgrade head && uv run --env-file ../.env alembic check`
Expected: 第二条命令输出 `No new upgrade operations detected.`

- [ ] **Step 7: Commit**

```bash
git add backend
git commit -m "feat: add user, settings and model config tables"
```

---

### Task 4: 系统设置存储（注册开关、页面配置、生成参数）

**Files:**
- Create: `backend/app/settings_store/{__init__,schemas,defaults,service}.py`
- Test: `backend/tests/test_settings_store.py`

**Interfaces:**
- Consumes: `SystemSetting`（Task 3）
- Produces:
  - `FieldKey(StrEnum)`：`prompt`、`materials`、`subject`、`grade`、`textbook_edition`、`duration`、`aspect_ratio`、`style`、`voice`、`web_search`
  - `FieldOption(BaseModel)`：`value: str`、`label: str`、`subjects: list[str] | None = None`（只有教材版本用这个字段：表示这个版本适用于哪些科目，None 表示适用于所有科目）
  - `FieldConfig(BaseModel)`：`key: FieldKey`、`label: str`、`visible: bool`、`default: str | bool | None`、`options: list[FieldOption] = []`、`default_by_subject: dict[str, str] = {}`
  - `FormFieldsConfig(BaseModel)`：`fields: list[FieldConfig]`。校验规则：10 个 key 每个恰好出现一次；`prompt.visible` 必须为 True；subject、grade、textbook_edition、duration、aspect_ratio、style 这几项的 options 不能为空，且 value 不能重复；这几项的 `default` 必须是某个 option 的 value；`default_by_subject` 的键必须是 subject 的某个 option，值必须是 textbook_edition 的某个 option。校验失败的错误信息里要包含"默认值必须在可选值中"
  - `GenerationParams(BaseModel)`：`segment_visuals_min: int = 3`（1–10）、`segment_visuals_max: int = 6`（1–12，必须 ≥ min）、`illustrations_per_minute: int = 4`（0–20）、`max_concurrent_jobs: int = 2`（1–20）、`max_retries: int = 2`（0–5）、`duration_tolerance_pct: int = 15`（5–50）、`long_term_memory_enabled: bool = True`
  - `RegistrationSettings(BaseModel)`：`open: bool = True`
  - `DEFAULT_FORM_FIELDS: FormFieldsConfig`（在 `defaults.py` 里定义，取值见下面 Step 3）
  - service：`async get_form_fields(db) -> FormFieldsConfig`、`async put_form_fields(db, cfg) -> FormFieldsConfig`、`async get_generation_params(db) -> GenerationParams`、`async put_generation_params(db, p) -> GenerationParams`、`async get_registration(db) -> RegistrationSettings`、`async put_registration(db, r) -> RegistrationSettings`。库里没有这条记录时返回默认值，写入后 commit。存储用的 key 分别是 `form_fields`、`generation_params`、`registration`

- [ ] **Step 1: 写失败的测试**

```python
async def test_defaults_when_absent(db):
    f = {x.key: x for x in (await get_form_fields(db)).fields}
    assert f["subject"].default == "数学" and f["grade"].default == "初三"
    assert f["textbook_edition"].default == "人教版"
    assert f["textbook_edition"].default_by_subject == {"语文": "统编版", "历史": "统编版", "道德与法治": "统编版"}
    assert (await get_generation_params(db)).illustrations_per_minute == 4
    assert (await get_registration(db)).open is True
async def test_put_then_get_roundtrip(db): ...  # 把 aspect_ratio 设成不可见后保存，重新读出来仍然是不可见
def test_prompt_cannot_be_hidden(): ...       # 把 prompt.visible 设成 False 时抛 ValidationError
def test_default_must_be_in_options(): ...    # 删掉 "数学" 这个 option、default 仍然是 "数学" 时抛 ValidationError，错误信息包含 "默认值必须在可选值中"
def test_default_by_subject_must_reference_options(): ...  # 删掉 "统编版" 这个 option 时抛 ValidationError
def test_visuals_max_ge_min(): ...            # min=5、max=4 时抛 ValidationError
```

- [ ] **Step 2: 运行，确认失败**

Run: `cd backend && uv run --env-file ../.env pytest tests/test_settings_store.py -q`
Expected: FAIL（ImportError）

- [ ] **Step 3: 实现 schemas、defaults、service**

默认值，按 `key：label，visible，default，options` 列出：
- prompt：想讲什么，可见，None，无选项
- materials：参考素材，可见，None，无选项（允许的文件类型由第 2 部分决定）
- subject：科目，可见，`数学`，数学 / 物理 / 化学 / 生物 / 语文 / 英语 / 历史 / 地理 / 道德与法治
- grade：年级，可见，`初三`，一年级 … 六年级 / 初一 / 初二 / 初三 / 高一 / 高二 / 高三
- textbook_edition：教材版本，可见，`人教版`，人教版 / 北师大版 / 苏教版 / 沪教版 / 统编版（统编版的 `subjects` 为 `["语文","历史","道德与法治"]`）；`default_by_subject` 见上面的测试
- duration：视频时长，可见，`5`，`3`→3 分钟 / `5`→5 分钟 / `10`→10 分钟 / `custom`→自定义
- aspect_ratio：视频尺寸，可见，`16:9`，16:9 横屏 / 9:16 竖屏 / 1:1 方形
- style：讲解风格，可见，`auto`，`auto`→按科目自动 / `math_animation`→数学动画 / `story_sketch`→故事 / 简笔画
- voice：配音声音，可见，None，无选项（可选的音色来自模型配置里的 tts 一项）
- web_search：允许联网搜索，可见，True，无选项

- [ ] **Step 4: 运行，确认通过**

Run: 同 Step 2
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/settings_store backend/tests/test_settings_store.py
git commit -m "feat: add typed system settings store with defaults"
```

---

### Task 5: 注册、登录、会话

**Files:**
- Create: `backend/app/auth/{__init__,schemas,deps,login_limiter,router}.py`
- Modify: `backend/app/main.py`（注册路由）、`backend/tests/conftest.py`
- Test: `backend/tests/test_auth.py`, `backend/tests/test_login_limiter.py`

**Interfaces:**
- Consumes: `User`、`UserStatus`（Task 3），`hash_password`、`verify_password`（Task 2），`get_registration`（Task 4），`get_redis`、`api_error`（Task 1）
- Produces:
  - `normalize_username(raw: str) -> str`：只去掉首尾空格，保留大小写用于显示；查重和登录时用 `func.lower(User.username) == name.lower()` 比较
  - `RegisterRequest`（`username`、`password`，按 Global Constraints 校验）、`LoginRequest`（`username`、`password`，只要求非空）、`UserOut`（`id`、`username`、`role`、`status`、`created_at`）
  - `class LoginLimiter(redis, user_threshold=5, ip_threshold=20, window_seconds=900)`：`async is_locked(username, ip) -> bool`、`async record_failure(username, ip) -> None`、`async reset_user(username) -> None`。Redis key 为 `login_fail:u:<lower(username)>` 和 `login_fail:ip:<ip>`，第一次失败时设置过期时间
  - 会话里的键：`uid`（字符串形式的 UUID）、`sv`（session_version）
  - `async get_current_user(request, db) -> User`：会话里没有用户、用户不存在、或 `sv` 和库里的 `session_version` 不一致时，清空会话并返回 401 `not_authenticated`
  - `async require_active_user(user=Depends(get_current_user)) -> User`：状态不是 active 时返回 403，错误码对应关系为 pending→`account_pending`、rejected→`account_rejected`、disabled→`account_disabled`
  - `async require_admin(user=Depends(require_active_user)) -> User`：不是管理员时返回 403 `forbidden`
  - 路由：
    - `POST /api/auth/register`：201，返回 `UserOut`（状态为 pending，不自动登录）。错误：403 `registration_closed`、409 `username_taken`
    - `POST /api/auth/login`：200，返回 `UserOut`（任何状态的账号，只要密码对就能登录，前端根据状态跳转）。错误：401 `invalid_credentials`（用户名不存在和密码错误都返回这一个）、429 `login_locked`（提示"登录失败次数过多，请 15 分钟后再试"）
    - `POST /api/auth/logout`：204
    - `GET /api/auth/me`：返回 `UserOut`，用 `get_current_user` 校验
  - conftest：`login(client, username, password) -> None`（登录失败就 assert）；`app` fixture 里额外挂一个只用于测试的路由 `GET /api/_test/active`，依赖 `require_active_user`

- [ ] **Step 1: 写失败的测试（test_auth.py）**

```python
async def test_register_creates_pending(client, db):
    r = await client.post("/api/auth/register", json={"username": "Teacher_Wang", "password": "pass1234"})
    assert r.status_code == 201 and r.json()["status"] == "pending"
    assert (await client.get("/api/auth/me")).status_code == 401   # 注册后不自动登录
async def test_register_duplicate_case_and_space(client, make_user):
    await make_user("teacher_wang")
    r = await client.post("/api/auth/register", json={"username": " Teacher_Wang ", "password": "pass1234"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "username_taken"
@pytest.mark.parametrize("username,password", [("ab", "pass1234"), ("a"*33, "pass1234"), ("bad name", "pass1234"), ("ok_name", "short")])
async def test_register_validation(client, username, password): ...   # 返回 422
async def test_register_closed(client, db): ...   # 先 put_registration(open=False)，注册返回 403 registration_closed
async def test_login_case_insensitive_and_me(client, make_user):
    await make_user("Teacher_Wang", "pass1234")
    r = await client.post("/api/auth/login", json={"username": "teacher_wang ", "password": "pass1234"})
    assert r.status_code == 200 and (await client.get("/api/auth/me")).json()["username"] == "Teacher_Wang"
async def test_login_wrong_password_and_unknown_user_same_error(client, make_user): ...   # 两种情况都是 401 invalid_credentials
async def test_login_locked_after_5_failures(client, make_user): ...   # 输错 5 次后，第 6 次即使密码正确也返回 429 login_locked
async def test_logout_clears_session(client, make_user): ...           # 退出后 /me 返回 401
async def test_pending_user_blocked_from_active_routes(client, make_user):
    await make_user("p1", status="pending"); await login(client, "p1", "pass1234")
    r = await client.get("/api/_test/active")
    assert r.status_code == 403 and r.json()["detail"]["code"] == "account_pending"
async def test_session_invalidated_when_session_version_bumps(client, db, make_user): ...  # 登录后把库里的 session_version 加 1，/me 返回 401
```

test_login_limiter.py：连续 5 次 `record_failure` 后 `is_locked` 为 True；`reset_user` 后为 False；同一个 IP 对 20 个不同用户名各失败 1 次后，`is_locked` 对任意用户名都为 True。

- [ ] **Step 2: 运行，确认失败**

Run: `cd backend && uv run --env-file ../.env pytest tests/test_auth.py tests/test_login_limiter.py -q`
Expected: FAIL

- [ ] **Step 3: 实现 auth 包，并在 `create_app` 里注册路由**

登录流程：先 `is_locked`，被锁定就返回 429；然后查用户、校验密码，失败就 `record_failure` 后返回 401；成功就 `reset_user`，清空旧会话，写入 `uid` 和 `sv`。IP 取 `request.client.host`。

- [ ] **Step 4: 运行，确认通过**

Run: `cd backend && uv run --env-file ../.env pytest -q`
Expected: 全部通过

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: add registration, login with lockout and session guards"
```

---

### Task 6: 初始管理员命令

**Files:**
- Create: `backend/app/cli.py`
- Test: `backend/tests/test_cli.py`

**Interfaces:**
- Consumes: `User`、`hash_password`、`get_settings`
- Produces:
  - `async bootstrap_admin(db, username: str | None, password: str | None) -> str`：返回 `"created"`、`"promoted"` 或 `"noop"`
  - 命令行入口：`uv run python -m app.cli bootstrap`，从 settings 读取 `initial_admin_username` 和 `initial_admin_password`

规则：
- 已经有正常状态的管理员，并且环境变量没给用户名：返回 `noop`。
- 没有正常状态的管理员，并且环境变量缺用户名或密码：抛 `SystemExit("请在 .env 中设置 INITIAL_ADMIN_USERNAME 和 INITIAL_ADMIN_PASSWORD")`。
- 同名用户已存在：改成 admin 和 active，不改密码，返回 `promoted`；如果它本来就是正常状态的管理员，返回 `noop`。
- 同名用户不存在：密码少于 8 位就抛 SystemExit；否则创建正常状态的管理员，返回 `created`。

- [ ] **Step 1: 写失败的测试**

`test_creates_admin_when_none`（返回 created，库里的用户是 admin/active，密码能校验通过）、`test_idempotent`（第二次运行返回 noop）、`test_promotes_existing_pending_user_keeps_password`、`test_exits_when_no_admin_and_env_missing`、`test_noop_when_admin_exists_and_env_missing`、`test_rejects_short_password`。

- [ ] **Step 2: 运行，确认失败**

Run: `cd backend && uv run --env-file ../.env pytest tests/test_cli.py -q`
Expected: FAIL

- [ ] **Step 3: 实现 `app/cli.py`**（用 argparse，只有 `bootstrap` 一个子命令，通过 `asyncio.run` 调用）

- [ ] **Step 4: 运行测试，再在开发库上实际执行一次**

Run: `cd backend && uv run --env-file ../.env pytest tests/test_cli.py -q && uv run --env-file ../.env python -m app.cli bootstrap`
Expected: 6 passed；命令输出 `created`

- [ ] **Step 5: Commit**

```bash
git add backend/app/cli.py backend/tests/test_cli.py
git commit -m "feat: add bootstrap command for initial admin"
```

---

### Task 7: 管理后台：用户管理与注册开关

**Files:**
- Create: `backend/app/admin/{__init__,schemas,user_actions,users_router,settings_router}.py`
- Modify: `backend/app/main.py`、`backend/tests/conftest.py`
- Test: `backend/tests/test_admin_users.py`

**Interfaces:**
- Consumes: `require_admin`、`UserOut`（Task 5），`get_registration`、`put_registration`（Task 4）
- Produces:
  - `UserAction(StrEnum)`：`approve`、`reject`、`disable`、`enable`
  - `async apply_user_action(db, actor: User, target_id: UUID, action: UserAction) -> User`，状态转换规则：
    - approve：pending 或 rejected → active
    - reject：pending → rejected
    - disable：active → disabled
    - enable：disabled → active
    - 其他转换返回 409 `invalid_transition`；用户不存在返回 404 `user_not_found`
    - approve 和 reject 时写入 `reviewed_at`、`reviewed_by`
    - disable 时 `session_version += 1`
  - `async reset_password(db, target_id, new_password) -> None`：同时 `session_version += 1`
  - `async set_role(db, target_id, role: UserRole) -> User`
  - 保护最后一个管理员：disable 某个管理员，或者把管理员改成 teacher 之后，如果系统里正常状态的管理员数量变成 0，就返回 409 `last_admin`（提示"系统至少需要保留一个管理员"）
  - 路由（全部依赖 `require_admin`）：
    - `GET /api/admin/users?status=&q=&page=1&page_size=20`：返回 `{"items": [UserOut], "total": int}`。排序：pending 排在最前，其余按 `created_at` 倒序；`q` 对用户名做不区分大小写的模糊匹配
    - `POST /api/admin/users/{id}/actions`，body 为 `{"action": ...}`，返回 `UserOut`
    - `POST /api/admin/users/{id}/password`，body 为 `{"password": ...}`（8–128 位），返回 204
    - `PUT /api/admin/users/{id}/role`，body 为 `{"role": ...}`，返回 `UserOut`
    - `GET`、`PUT /api/admin/settings/registration`，读写 `RegistrationSettings`
  - conftest：`make_client(app) -> AsyncClient`，用来同时模拟两个已登录的用户

- [ ] **Step 1: 写失败的测试**

```python
async def test_admin_routes_require_admin(client, make_user): ...   # 未登录返回 401；teacher 返回 403 forbidden；待审核的 admin 返回 403 account_pending
async def test_list_pending_first_and_filter(admin_client, make_user): ...   # 列表第一条是 pending；status=active 只返回正常账号；q="WANG" 能匹配到 teacher_wang
async def test_approve_pending_and_rejected(admin_client, make_user): ...    # pending→active、rejected→active，并检查 reviewed_by 等于当前管理员的 id
async def test_invalid_transition_409(admin_client, make_user): ...          # 对 active 用户执行 approve 返回 409 invalid_transition
async def test_disable_kicks_existing_session(app, admin_client, make_user):
    await make_user("t1"); t = make_client(app); await login(t, "t1", "pass1234")
    await admin_client.post(f"/api/admin/users/{uid}/actions", json={"action": "disable"})
    assert (await t.get("/api/auth/me")).status_code == 401
async def test_reset_password_invalidates_and_new_works(...): ...   # 旧会话返回 401；旧密码登录返回 401；新密码可以登录
async def test_reset_password_too_short_422(...): ...
async def test_last_admin_cannot_demote_or_disable_self(admin_client, admin_user): ...   # 两种操作都返回 409 last_admin
async def test_second_admin_allows_demotion(...): ...   # 再设一个管理员之后，可以把第一个降级
async def test_registration_toggle(admin_client, client): ...   # PUT open=false 之后，注册返回 403 registration_closed
```
（在 conftest 里加 `admin_user` 和 `admin_client` 两个 fixture：创建一个正常状态的管理员并登录。）

- [ ] **Step 2: 运行，确认失败**

Run: `cd backend && uv run --env-file ../.env pytest tests/test_admin_users.py -q`
Expected: FAIL

- [ ] **Step 3: 实现 admin 包，并注册路由**

- [ ] **Step 4: 运行，确认通过**

Run: `cd backend && uv run --env-file ../.env pytest -q`
Expected: 全部通过

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: add admin user management and registration toggle"
```

---

### Task 8: 模型配置的存储和接口

**Files:**
- Create: `backend/app/model_configs/{__init__,schemas,service,router}.py`
- Modify: `backend/app/main.py`（在 `app.state` 里放 `SecretBox`）
- Test: `backend/tests/test_model_configs.py`

**Interfaces:**
- Consumes: `ModelConfigRow`、`Purpose`、`PURPOSE_LABELS`、`REQUIRED_PURPOSES`（Task 3），`SecretBox`、`SecretDecryptError`、`mask_secret`（Task 2），`require_admin`（Task 5）
- Produces:
  - `DEFAULTS: dict[Purpose, tuple[str, str]]`，值为（base_url, model）：`tts` → (`https://openspeech.bytedance.com`, `seed-audio-1.0`)，`embedding` → (`""`, `qwen3.7-text-embedding-flash`)，`image_gen` → (`""`, `gpt-image-2.5-flare`)，其余都是 (`""`, `""`)
  - `Voice(BaseModel)`：`speaker_id: str`、`label: str`
  - `ModelConfigView`：`purpose`、`label`、`required: bool`、`base_url`、`model`、`enabled`、`api_key_status: Literal["set","missing","undecryptable"]`、`api_key_masked: str | None`、`voices: list[Voice]`（只有 tts 有）、`last_test_ok`、`last_test_message`、`last_tested_at`
  - `ModelConfigUpdate`：`base_url: str`、`model: str`、`enabled: bool`、`api_key: str | None = None`、`clear_api_key: bool = False`、`voices: list[Voice] | None = None`。校验：`base_url` 为空，或者以 `http://`、`https://` 开头；保存前去掉末尾的 `/`
  - `@dataclass ResolvedConfig`：`purpose`、`base_url`、`api_key`（解密后的明文）、`model`、`extra: dict`
  - service：
    - `async list_configs(db, box) -> list[ModelConfigView]`：按 Purpose 的顺序返回 7 项，库里没有的用 DEFAULTS 补齐
    - `async update_config(db, box, purpose, upd) -> ModelConfigView`
    - `async resolve(db, box, purpose, *, require_enabled=True) -> ResolvedConfig | None`：没启用（当 `require_enabled` 为 True 时）、没有 key、key 解不开、`base_url` 或 `model` 为空时返回 None。web_search 不检查 model
    - `async system_available(db, box) -> bool`：`REQUIRED_PURPOSES` 里每一项都能 resolve，并且 `last_test_ok is not False`
    - `async list_voices(db) -> list[Voice]`
    - `async record_test(db, purpose, ok: bool, message: str) -> None`
  - `update_config` 的规则：
    - `api_key` 非空时加密后保存；为 None 或空字符串时保留原值；`clear_api_key=True` 时清空
    - `enabled=True` 时，必须有 key（新填的或原来的）、`base_url` 和 `model`（web_search 不要求 model），否则返回 422 `config_incomplete`
    - tts 并且 `enabled=True` 时，`voices` 至少要有 1 个，`speaker_id` 不能重复，否则返回 422 `invalid_voices`
    - `base_url`、`model` 或 key 发生变化时，把 `last_test_ok`、`last_test_message`、`last_tested_at` 清空
  - 音色保存在 tts 那一行的 `extra["voices"]` 里（`list[{"speaker_id","label"}]`），`ResolvedConfig.extra` 原样带出
  - 路由（`require_admin`）：`GET /api/admin/model-configs` 返回 `list[ModelConfigView]`；`PUT /api/admin/model-configs/{purpose}` 返回 `ModelConfigView`（purpose 不合法时返回 422）
  - conftest：`box` fixture，返回 `app.state.secret_box`；测试辅助函数 `put(client, purpose, **fields)`，调用 PUT 接口并 assert 返回 200

- [ ] **Step 1: 写失败的测试**

```python
async def test_list_defaults_seven_purposes(admin_client):
    items = (await admin_client.get("/api/admin/model-configs")).json()
    assert [i["purpose"] for i in items] == ["outline_llm","review_llm","vision_llm","image_gen","embedding","tts","web_search"]
    tts = items[5]; assert tts["base_url"] == "https://openspeech.bytedance.com" and tts["model"] == "seed-audio-1.0"
async def test_key_encrypted_and_masked(admin_client, db):
    await put(admin_client, "outline_llm", base_url="https://r.example.com/v1/", model="m", enabled=True, api_key="sk-secret-9f2a")
    row = await db.get(ModelConfigRow, "outline_llm")
    assert "sk-secret" not in row.api_key_encrypted and row.base_url == "https://r.example.com/v1"
    body = (await admin_client.get("/api/admin/model-configs")).text
    assert "sk-secret" not in body and '"api_key_masked":"****9f2a"' in body.replace(" ", "")
async def test_omitted_key_is_kept(admin_client): ...       # 再次 PUT 时不带 api_key，状态仍然是 set、掩码不变
async def test_clear_key(admin_client): ...                 # clear_api_key=True、enabled=False 之后，状态变成 missing
async def test_enable_requires_key_and_model(admin_client): ...   # 返回 422 config_incomplete
async def test_tts_voices_validation(admin_client): ...     # voices 为空或 speaker_id 重复时返回 422 invalid_voices
async def test_undecryptable_key(app, db, admin_client):
    # 先用当前的 box 存一个 key，再把 app.state.secret_box 换成用另一个 Fernet key 创建的 SecretBox
    item = ...; assert item["api_key_status"] == "undecryptable" and item["api_key_masked"] is None
    assert await system_available(db, app.state.secret_box) is False
async def test_system_available(db, box): ...   # 5 个必需项都配好时为 True；不配 web_search 和 embedding 也为 True；任意一个必需项 last_test_ok=False 时为 False
async def test_changing_base_url_resets_test_status(...): ...
async def test_model_config_admin_only(client, make_user): ...   # teacher 访问返回 403
```

- [ ] **Step 2: 运行，确认失败**

Run: `cd backend && uv run --env-file ../.env pytest tests/test_model_configs.py -q`
Expected: FAIL

- [ ] **Step 3: 实现 model_configs 的 schemas、service、router**

key 解不开时捕获 `SecretDecryptError`，把状态标成 `undecryptable`，不要往外抛异常。

- [ ] **Step 4: 运行，确认通过**

Run: `cd backend && uv run --env-file ../.env pytest -q`
Expected: 全部通过

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: add encrypted model configuration with admin API"
```

---

### Task 9: 模型配置的"测试连接"

**Files:**
- Create: `backend/app/model_configs/probe.py`
- Modify: `backend/app/model_configs/router.py`、`backend/app/main.py`（在 `app.state.http` 里放一个共享的 `httpx.AsyncClient(timeout=20)`，应用关闭时 close）
- Test: `backend/tests/test_probe.py`

**Interfaces:**
- Consumes: `resolve(..., require_enabled=False)`、`record_test`（Task 8）
- Produces:
  - `join_url(base: str, path: str) -> str`：去掉 base 末尾的 `/` 和 path 开头的 `/`，再用一个 `/` 连接
  - `@dataclass ProbeResult`：`ok: bool`、`message: str`
  - `class ProbeUnsupported(Exception)`
  - `async run_probe(http: httpx.AsyncClient, cfg: ResolvedConfig) -> ProbeResult`：
    - outline_llm、review_llm、vision_llm：`POST {base}/chat/completions`，请求头 `Authorization: Bearer <key>`，body 为 `{"model": m, "messages": [{"role":"user","content":"ping"}], "max_tokens": 1}`
    - embedding：`POST {base}/embeddings`，body 为 `{"model": m, "input": "ping"}`
    - image_gen：`GET {base}/models`，在返回的 `data[].id` 里找有没有这个模型；找不到就返回 `ok=False`，提示"接口可用，但没有找到模型 <m>"（这样测试时不会真的花钱生成一张图）
    - tts：`POST {base}/api/v3/tts/create`，请求头 `X-Api-Key: <key>`，body 为 `{"model": m, "text_prompt": "测试", "speaker": voices[0].speaker_id}`；返回 2xx 且 JSON 里 `code` 为 0 或不存在，才算成功
    - web_search：抛 `ProbeUnsupported`（第 2 部分再实现）
    - 成功时 `message="连接正常"`。超时时为"连接超时"；连不上时为"无法连接到 <host>"；HTTP 错误时为"HTTP <status>：<响应体前 200 个字符>"
  - `redact(text: str, secret: str) -> str`：把 text 里出现的 secret 替换成 `****`。所有失败提示都要经过它处理之后才能保存或返回
  - 路由：`POST /api/admin/model-configs/{purpose}/test`，返回 `ProbeResult` 并调用 `record_test` 记录。配置不完整时返回 409 `config_incomplete`；web_search 返回 400 `probe_unsupported`（不记录）

- [ ] **Step 1: 写失败的测试**（用 respx 模拟 `app.state.http` 发出的请求）

```python
def test_join_url():
    assert join_url("https://r.example.com/v1/", "/chat/completions") == "https://r.example.com/v1/chat/completions"
    assert join_url("https://r.example.com/v1", "chat/completions") == "https://r.example.com/v1/chat/completions"
async def test_llm_probe_ok_records(admin_client, respx_mock): ...   # mock 返回 200；结果 ok=True；列表里 last_test_ok 为 True
async def test_llm_probe_http_error_redacts_key(...):
    # mock 返回 401，响应体为 "invalid key sk-secret-9f2a"
    assert r.json()["ok"] is False and "sk-secret-9f2a" not in r.text and r.json()["message"].startswith("HTTP 401")
async def test_timeout_message(...): ...   # mock 抛 httpx.ConnectTimeout，提示为 "连接超时"
async def test_image_probe_model_missing(...): ...   # /models 里没有这个模型：ok=False，提示包含 "没有找到模型"
async def test_tts_probe_uses_x_api_key_and_first_voice(...): ...   # 检查请求头 X-Api-Key 和 body 里的 speaker
async def test_probe_incomplete_409(admin_client): ...
async def test_probe_web_search_400(admin_client): ...
```

- [ ] **Step 2: 运行，确认失败**

Run: `cd backend && uv run --env-file ../.env pytest tests/test_probe.py -q`
Expected: FAIL

- [ ] **Step 3: 实现 `probe.py` 和测试接口**

- [ ] **Step 4: 运行，确认通过**

Run: `cd backend && uv run --env-file ../.env pytest -q`
Expected: 全部通过

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: add connection test for model configs"
```

---

### Task 10: 页面配置接口和老师端表单配置

**Files:**
- Modify: `backend/app/admin/settings_router.py`
- Create: `backend/app/public/{__init__,router}.py`
- Test: `backend/tests/test_page_config.py`

**Interfaces:**
- Consumes: `get_form_fields`、`put_form_fields`、`get_generation_params`、`put_generation_params`（Task 4），`system_available`、`list_voices`、`resolve`（Task 8），`require_active_user`、`require_admin`（Task 5）
- Produces:
  - 管理员接口：`GET`、`PUT /api/admin/settings/form-fields`（`FormFieldsConfig`，校验失败时返回 422）；`GET`、`PUT /api/admin/settings/generation-params`（`GenerationParams`）
  - 老师接口：`GET /api/config/form`（`require_active_user`），返回 `PublicFormConfig`，结构为 `{"system_available": bool, "fields": [PublicField]}`。`PublicField` 包含 `key`、`label`、`default`、`options`、`default_by_subject`
  - 规则：
    - 只返回 `visible=True` 的字段
    - voice 的 options 来自 `list_voices`（value 为 speaker_id，label 为显示名），default 为第一个音色；tts 没有可用音色时不返回 voice 字段
    - `resolve(web_search)` 为 None 时不返回 web_search 字段
    - 不返回生成参数，也不返回任何模型配置信息
  - 隐藏字段在创建项目时怎么补默认值，由第 2 部分实现（`resolve_form_values`）

- [ ] **Step 1: 写失败的测试**

```python
async def test_admin_form_fields_roundtrip_and_validation(admin_client): ...   # 把 aspect_ratio 设成不可见后 PUT 返回 200；删掉 "数学" 这个 option 后 PUT 返回 422，并且响应体包含 "默认值必须在可选值中"
async def test_public_hides_invisible_fields(teacher_client, admin_client):
    # 管理员把 aspect_ratio 设成不可见之后
    keys = [f["key"] for f in (await teacher_client.get("/api/config/form")).json()["fields"]]
    assert "aspect_ratio" not in keys and "prompt" in keys
async def test_public_voice_options_from_tts(...): ...   # tts 配了两个音色时，options 为这两个，default 为第一个
async def test_public_omits_web_search_when_unconfigured(...): ...
async def test_public_reports_system_unavailable(...): ...   # 没有配置任何模型时 system_available 为 False
async def test_public_never_leaks_model_info(...): ...       # 先配上带 key 的模型，响应文本里不应出现 base_url、key 掩码和 "generation"
async def test_public_requires_active(client, make_user): ... # 待审核的账号返回 403 account_pending
async def test_generation_params_admin_only_and_validation(...): ...   # teacher 访问返回 403；max_concurrent_jobs=0 时返回 422
```
（conftest 加 `teacher_client` fixture：创建一个正常状态的老师并登录。）

- [ ] **Step 2: 运行，确认失败**

Run: `cd backend && uv run --env-file ../.env pytest tests/test_page_config.py -q`
Expected: FAIL

- [ ] **Step 3: 实现上述接口**

- [ ] **Step 4: 运行，确认通过**

Run: `cd backend && uv run --env-file ../.env pytest -q`
Expected: 全部通过

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: add page config admin API and teacher form config"
```

---

### Task 11: 前端骨架、视觉方向、路由守卫

**Files:**
- Create: `frontend/`（用 Vite 的 vue-ts 模板生成），`frontend/vite.config.ts`、`src/main.ts`、`src/App.vue`、`src/styles/tokens.css`、`src/api/http.ts`、`src/api/auth.ts`、`src/stores/auth.ts`、`src/router/{index,guards}.ts`、`src/layouts/AppLayout.vue`、`src/views/HomeView.vue`
- Create（需要用户同意后）：`.claude/skills/frontend-design/SKILL.md`
- Test: `frontend/tests/guards.spec.ts`, `frontend/tests/http.spec.ts`

**Interfaces:**
- Consumes: 后端 `/api/auth/*`（Task 5）
- Produces:
  - `class ApiError extends Error { status: number; code: string }`
  - `request<T>(method: string, path: string, body?: unknown): Promise<T>`：使用 `credentials: "same-origin"`；状态码不是 2xx 时，从 `detail.code` 和 `detail.message` 构造 `ApiError` 抛出（422 时 code 为 `"validation_error"`，message 取第一条错误信息）；204 返回 undefined
  - `type CurrentUser = { id: string; username: string; role: "teacher" | "admin"; status: "pending" | "active" | "rejected" | "disabled" }`
  - `useAuthStore()`：`user: CurrentUser | null`、`loaded: boolean`、`fetchMe()`（401 时把 user 设为 null）、`login(u, p)`、`logout()`、`register(u, p)`
  - `decideRoute(to: { name: string; meta: { public?: boolean; admin?: boolean } }, user: CurrentUser | null): true | { name: string }`：纯函数，路由守卫调用它
  - 路由名：`login`、`register`（这两个是 public）、`account-status`、`home`、`admin`（meta.admin，重定向到 `admin-page-config`）、`admin-page-config`、`admin-model-config`、`admin-users`

- [ ] **Step 1: 确定视觉方向（需要用户同意）**

先问用户：是否同意把 Anthropic 官方的 frontend-design skill（`https://raw.githubusercontent.com/anthropics/skills/main/skills/frontend-design/SKILL.md`）下载到 `.claude/skills/frontend-design/SKILL.md`。同意的话，下载后先读一遍，再按里面的方法为"给中小学老师用的、严谨又亲切的教学工具"定一个视觉方向。不同意的话，就自己定一个克制、清晰的方向。不管哪种情况，结果都写进 `tokens.css` 开头的注释（3–5 行：气质、主色、字体），并定义 CSS 变量：`--ev-color-primary`、`--ev-color-bg`、`--ev-color-surface`、`--ev-color-text`、`--ev-color-muted`、`--ev-color-danger`、`--ev-color-success`、`--ev-radius`、`--ev-font-sans`（中文字体放在前面，例如 `"PingFang SC","Microsoft YaHei",...`），再把 Element Plus 的 `--el-color-primary` 等变量映射到这些变量上。

- [ ] **Step 2: 生成项目并安装依赖**

```bash
npm create vite@latest frontend -- --template vue-ts
cd frontend && npm install --save-exact && npm install --save-exact vue-router pinia element-plus
npm install --save-exact -D vitest @vue/test-utils jsdom
```
`vite.config.ts`：`server.proxy["/api"] = "http://localhost:8000"`，`test.environment = "jsdom"`。

- [ ] **Step 3: 写失败的测试**

```ts
const T = (s: CurrentUser["status"], role: CurrentUser["role"] = "teacher") => ({ id: "1", username: "u", role, status: s })
test("anonymous to private → login", () => expect(decideRoute({ name: "home", meta: {} }, null)).toEqual({ name: "login" }))
test("anonymous to public ok", () => expect(decideRoute({ name: "register", meta: { public: true } }, null)).toBe(true))
test("pending → account-status", () => expect(decideRoute({ name: "home", meta: {} }, T("pending"))).toEqual({ name: "account-status" }))
test("active on login → home", () => expect(decideRoute({ name: "login", meta: { public: true } }, T("active"))).toEqual({ name: "home" }))
test("teacher to admin → home", () => expect(decideRoute({ name: "admin-users", meta: { admin: true } }, T("active"))).toEqual({ name: "home" }))
test("admin to admin ok", () => expect(decideRoute({ name: "admin-users", meta: { admin: true } }, T("active", "admin"))).toBe(true))
test("active on account-status → home", () => expect(decideRoute({ name: "account-status", meta: {} }, T("active"))).toEqual({ name: "home" }))
```
http.spec.ts：模拟 `fetch` 返回 409 `{"detail":{"code":"username_taken","message":"用户名已被使用"}}`，期望 `request` 抛出的 `ApiError` 满足 `code==="username_taken"`、`message==="用户名已被使用"`。

- [ ] **Step 4: 运行，确认失败**

Run: `cd frontend && npx vitest run`
Expected: FAIL

- [ ] **Step 5: 实现 http、auth store、guards、router、AppLayout、HomeView**

AppLayout 的顶栏：左侧是产品名"教学视频助手"，右侧是用户名、"管理后台"入口（只有管理员能看到）和"退出"。HomeView 标题为"我的视频"，空状态的文字是"新建视频功能即将上线"。

- [ ] **Step 6: 运行测试和构建**

Run: `cd frontend && npx vitest run && npm run build`
Expected: 测试全部通过；构建成功

- [ ] **Step 7: Commit**

```bash
git add frontend            # 如果 Step 1 下载了 skill，再加上 .claude/skills/frontend-design
git commit -m "feat: scaffold Vue frontend with design tokens and route guards"
```

---

### Task 12: 注册、登录、账号状态页面

**Files:**
- Create: `frontend/src/views/{LoginView,RegisterView,AccountStatusView}.vue`
- Test: `frontend/tests/auth-views.spec.ts`

**Interfaces:**
- Consumes: `useAuthStore`、`ApiError`、`decideRoute`（Task 11）

- [ ] **Step 1: 写失败的测试**（mock store 的方法）

```ts
test("register: mismatched confirm blocks submit")      // 显示"两次输入的密码不一致"，并且没有调用 register
test("register: success shows pending notice")          // 显示"注册成功，请等待管理员审核"
test("register: shows server message for registration_closed")   // 显示服务端返回的 message
test("login: 429 shows lock message")                   // 显示服务端返回的 message
test("login: pending user routes to account-status")
test.each([["pending","账号正在等待管理员审核"],["rejected","注册申请未通过"],["disabled","账号已被停用"]])("status page %s", ...)
```

- [ ] **Step 2: 运行，确认失败**

Run: `cd frontend && npx vitest run tests/auth-views.spec.ts`
Expected: FAIL

- [ ] **Step 3: 实现三个页面**

在注册和登录表单里，前端按 Global Constraints 校验用户名和密码的长度，提示文字和后端规则保持一致。账号状态页提供"退出登录"按钮，并显示"如有疑问请联系管理员"。

- [ ] **Step 4: 运行测试和构建**

Run: `cd frontend && npx vitest run && npm run build`
Expected: 测试全部通过；构建成功

- [ ] **Step 5: Commit**

```bash
git add frontend
git commit -m "feat: add register, login and account status pages"
```

---

### Task 13: 管理后台三个选项卡

**Files:**
- Create: `frontend/src/api/admin.ts`、`frontend/src/layouts/AdminLayout.vue`、`frontend/src/views/admin/{PageConfigTab,ModelConfigTab,UsersTab}.vue`
- Test: `frontend/tests/admin.spec.ts`

**Interfaces:**
- Consumes: Task 7、8、9、10 的管理员接口；`request`、`ApiError`（Task 11）
- Produces（`api/admin.ts`，TS 类型和后端 schema 的字段名保持一致）：`listUsers(params)`、`userAction(id, action)`、`resetPassword(id, pw)`、`setRole(id, role)`、`getRegistration()`、`putRegistration(open)`、`getFormFields()`、`putFormFields(cfg)`、`getGenerationParams()`、`putGenerationParams(p)`、`listModelConfigs()`、`putModelConfig(purpose, upd)`、`testModelConfig(purpose)`

页面要求：
- **AdminLayout**：三个选项卡（页面配置、模型配置、用户管理），分别对应三个子路由。
- **页面配置**：上半部分是一张表格，每行一个字段：名称、"老师可见"开关（prompt 这一行的开关禁用，提示"必填，不能隐藏"）、默认值下拉框、可选值编辑（用标签增删，value 和 label 可以分别编辑）。教材版本这一行额外提供"适用科目"多选和"各科目默认版本"编辑；voice 这一行显示"音色在模型配置中维护"；web_search 的默认值用开关。下半部分是"生成参数"表单，每个数字输入框的上下限和后端一致，还有一个"长期记忆"开关。两部分各有一个保存按钮，保存失败时用 `ElMessage.error` 显示服务端返回的 message。
- **模型配置**：表格有 7 行，列为：用途、接口地址、Key（显示掩码；未设置时显示"未设置"；解不开时显示红色的"无法解密，请重新填写"）、模型、状态（正常 / 失败 / 未测试 / 未启用）、操作（编辑、测试）。编辑弹窗里：key 输入框是密码类型，占位文字为"留空表示不修改"，旁边有"清除已保存的 Key"勾选框；tts 一项多一个音色列表编辑器（音色 ID、显示名称）。web_search 的"测试"按钮禁用，提示"第 2 部分接入搜索服务后可测试"。测试结果用 message 显示。页面顶部显示系统是否可用：有必需项不可用时显示警告"老师暂时无法新建视频"。
- **用户管理**：顶部是"开放注册"开关、状态筛选和用户名搜索；表格列为用户名、角色、状态、注册时间、操作。按状态显示不同的操作按钮：待审核为"通过 / 拒绝"，已拒绝为"通过"，正常为"停用 / 重置密码 / 设为管理员（或取消管理员）"，已停用为"启用 / 重置密码"。停用、拒绝、取消管理员前先弹出确认框；重置密码用弹窗，需要输入两次。返回 `last_admin` 错误时显示服务端的 message。

- [ ] **Step 1: 写失败的测试**（mock `api/admin.ts`）

```ts
test("users: action buttons by status")   // pending 行有"通过""拒绝"；active 行有"停用""重置密码"；disabled 行有"启用"
test("users: last_admin error surfaces server message")
test("page config: prompt visible switch is disabled")
test("page config: save error shows server message")   // putFormFields 抛 ApiError 时，ElMessage.error 收到对应的 message
test("model config: undecryptable shows warning text")
test("model config: empty key input omits api_key in payload")   // 调用 putModelConfig 时，参数里没有 api_key 字段
test("model config: web_search test button disabled")
```

- [ ] **Step 2: 运行，确认失败**

Run: `cd frontend && npx vitest run tests/admin.spec.ts`
Expected: FAIL

- [ ] **Step 3: 实现 admin API 和三个选项卡**

- [ ] **Step 4: 运行测试和构建**

Run: `cd frontend && npx vitest run && npm run build`
Expected: 测试全部通过；构建成功

- [ ] **Step 5: Commit**

```bash
git add frontend
git commit -m "feat: add admin console with page, model and user tabs"
```

---

### Task 14: 容器化与端到端冒烟验证

**Files:**
- Create: `backend/Dockerfile`、`frontend/Dockerfile`、`frontend/nginx.conf`
- Modify: `docker-compose.yml`

**Interfaces:**
- Consumes: 以上全部

- [ ] **Step 1: 后端镜像**

基础镜像用 `python:3.12-slim`，从 `ghcr.io/astral-sh/uv` 镜像里复制 uv 可执行文件，执行 `uv sync --frozen --no-dev`。启动命令：`uv run alembic upgrade head && uv run python -m app.cli bootstrap && uv run uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips="*"`。允许所有转发 IP 是因为后端端口不对外暴露，只有 nginx 能访问。

- [ ] **Step 2: 前端镜像**

第一阶段用 `node:22-alpine` 执行 `npm ci && npm run build`；第二阶段用 `nginx:1.27-alpine` 托管 `dist`。`nginx.conf`：`location /api/` 用 `proxy_pass http://backend:8000`，设置 `Host`、`X-Forwarded-For`、`X-Forwarded-Proto` 请求头；`client_max_body_size 100m`（第 2 部分上传素材要用）；其余路径 `try_files $uri /index.html`。

- [ ] **Step 3: 在 compose 里加 backend 和 frontend 服务**

backend：读取 `env_file: .env`，并覆盖 `DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}` 和 `REDIS_URL=redis://redis:6379/0`；`depends_on` 设为 postgres 健康后再启动；不映射端口。frontend：端口 `127.0.0.1:8080:80`，依赖 backend。

- [ ] **Step 4: 启动并检查**

Run: `docker compose up -d --build && sleep 15 && curl -s http://localhost:8080/api/health`
Expected: `{"status":"ok","db":true}`

- [ ] **Step 5: 手动冒烟（在浏览器打开 http://localhost:8080 ）**

1. 用 `.env` 里的初始管理员账号登录，能进入管理后台。
2. 在另一个浏览器窗口注册 `teacher_test`，看到"等待管理员审核"；登录后停在账号状态页。
3. 管理员在"用户管理"里点"通过"；老师刷新页面后进入"我的视频"。
4. 管理员在"页面配置"里隐藏"视频尺寸"并保存。老师的账号调用 `curl` 访问 `/api/config/form`，或者在浏览器开发者工具里看这个接口的返回，确认里面没有 aspect_ratio。
5. 管理员在"模型配置"里填写中转站的写大纲配置，点"测试"，看到"连接正常"或明确的失败原因。Key 由用户本人在页面上填写，不要发到对话里。
6. 管理员停用 `teacher_test`；老师刷新页面后回到登录页。

- [ ] **Step 6: Commit**

```bash
git add backend/Dockerfile frontend/Dockerfile frontend/nginx.conf docker-compose.yml
git commit -m "chore: containerize backend and frontend behind nginx"
```

