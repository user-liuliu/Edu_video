# 教师工作台 UI 改版实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有“黑板与作业本”样式改造成适合中小学教师反复使用的清晰、稳重、现代的“教师工作台”界面，同时保持现有业务行为和接口不变。

**Architecture:** 保留 Vue 3 + Element Plus + Pinia + Vue Router，集中重写 `tokens.css` 的语义令牌，并在 AppLayout、认证页和后台布局中复用同一套间距、颜色、圆角、焦点和响应式规则。桌面端使用稳定的侧边导航，移动端退化为顶部导航；页面内容继续由现有路由和组件提供。

**Tech Stack:** Vue 3.5、TypeScript、Element Plus、Vitest、Vue Test Utils、Vite。

**Spec:** `docs/superpowers/specs/2026-10-16-edu-video-agent-design.md`；视觉依据为项目级 `.agents/skills/ui-ux-pro-max/SKILL.md` 和 `design-system/default/MASTER.md`。

## Global Constraints

- 所有界面文字使用简体中文。
- 不改变现有 API、路由名称、认证流程和表单校验行为。
- 继续使用仓库已有 Element Plus，不新增图标或字体依赖；不加载外部字体。
- 颜色必须通过语义 CSS 变量管理，正文对比度至少 4.5:1。
- 交互控件保留可见键盘焦点、加载态、错误提示和 `prefers-reduced-motion` 支持。
- 适配 375px、768px、1024px、1440px 宽度，不产生横向滚动。

## Review Focus

- 未登录/登录后/管理员三种状态的导航层级不能混淆；由 `app-layout.spec.ts` 覆盖。
- 认证页在窄屏上必须保持表单可用且不被装饰区域挤压；由 `auth-views.spec.ts` 的结构断言和浏览器窄屏检查覆盖。
- 管理后台的三个子路由仍需保持可访问的 tab 语义；由 `admin-layout.spec.ts` 覆盖。
- 表格和操作按钮在窄屏上不能撑破页面；由管理页 CSS 规则和浏览器截图检查覆盖。
- 主题令牌和 Element Plus 映射必须统一，避免页面仍出现旧黑板绿/楷体样式；由构建和源码扫描覆盖。

### Task 1: 语义令牌与应用壳层

**Files:**
- Modify: `frontend/src/styles/tokens.css`
- Modify: `frontend/src/layouts/AppLayout.vue`
- Modify: `frontend/src/layouts/AdminLayout.vue`
- Test: `frontend/tests/app-layout.spec.ts`
- Test: `frontend/tests/admin-layout.spec.ts`

**Interfaces:**
- Consumes: 现有 `useAuthStore()` 用户状态和 admin 路由。
- Produces: `app-shell`、侧边导航、顶部工具栏、`admin-shell` 视觉结构；不改变路由跳转和退出逻辑。

- [ ] **Step 1: Write the failing tests**
  - 断言 `AppLayout` 包含品牌、`我的视频` 导航、管理员入口条件显示、用户名和退出按钮。
  - 断言 `AdminLayout` 保留三个 tab 文本和当前路由对应的选中状态，并新增后台页面标题。
- [ ] **Step 2: Run tests to verify they fail**
  - Run: `cd frontend && npx vitest run tests/app-layout.spec.ts tests/admin-layout.spec.ts`
  - Expected: 新增的导航/标题断言失败，现有行为断言仍可执行。
- [ ] **Step 3: Implement tokens and shell**
  - 将色板收敛为墨绿文字、青绿色主色、暖橙 CTA、纸白背景和冷灰边框。
  - 统一 4/8px 间距、6px 圆角、低阴影或无阴影表面、焦点环和 reduced-motion。
  - AppLayout 改为桌面侧栏 + 顶部账号区，移动端改为顶部横向导航；管理页使用同一壳层的标题和 tab 区。
- [ ] **Step 4: Run tests to verify they pass**
  - Run: `cd frontend && npx vitest run tests/app-layout.spec.ts tests/admin-layout.spec.ts`
  - Expected: PASS。

### Task 2: 认证与账号状态体验

**Files:**
- Modify: `frontend/src/components/AuthCard.vue`
- Modify: `frontend/src/views/LoginView.vue`
- Modify: `frontend/src/views/RegisterView.vue`
- Modify: `frontend/src/views/AccountStatusView.vue`
- Test: `frontend/tests/auth-views.spec.ts`

**Interfaces:**
- Consumes: 现有表单字段、校验规则、`useAuthStore()`、路由链接。
- Produces: 认证页双栏/单栏响应式视觉结构，所有原有表单和错误行为保持不变。

- [ ] **Step 1: Write the failing tests**
  - 断言认证页包含品牌区、产品定位短句、表单区和登录/注册入口。
  - 断言账号状态页保留状态提示和退出操作，并使用新的状态容器类。
- [ ] **Step 2: Run tests to verify they fail**
  - Run: `cd frontend && npx vitest run tests/auth-views.spec.ts`
  - Expected: 新增结构断言失败。
- [ ] **Step 3: Implement the responsive auth surface**
  - 左侧使用静态“课堂到视频”的信息区和纸张/分镜装饰，右侧承载真实表单；小屏隐藏装饰区但保留品牌与标题。
  - 统一表单间距、输入高度、按钮层级、错误/成功提示，不改变提交事件和文案语义。
- [ ] **Step 4: Run tests to verify they pass**
  - Run: `cd frontend && npx vitest run tests/auth-views.spec.ts`
  - Expected: PASS。

### Task 3: 首页与管理后台内容层

**Files:**
- Modify: `frontend/src/views/HomeView.vue`
- Modify: `frontend/src/views/admin/UsersTab.vue`
- Modify: `frontend/src/views/admin/PageConfigTab.vue`
- Modify: `frontend/src/views/admin/ModelConfigTab.vue`
- Modify: `frontend/src/views/admin/ModelConfigDialog.vue`
- Modify: `frontend/src/views/admin/OptionDialog.vue`
- Test: `frontend/tests/admin.spec.ts`

**Interfaces:**
- Consumes: 现有列表、配置加载、保存、弹窗和操作 API。
- Produces: 首页空状态工作台、后台摘要/工具栏/数据表格视觉层；不改变 API 参数和事件。

- [ ] **Step 1: Write the failing tests**
  - 断言首页有主标题、主 CTA 占位和最近项目空状态说明。
  - 断言后台各表格保留原有列、按钮文本和表单可访问标签。
- [ ] **Step 2: Run tests to verify they fail**
  - Run: `cd frontend && npx vitest run tests/admin.spec.ts`
  - Expected: 新增首页结构断言失败；后台行为断言保持可运行。
- [ ] **Step 3: Implement content-level visual hierarchy**
  - 首页改为“欢迎区 + 新建视频主操作 + 最近项目空状态”的工作台布局。
  - 后台增加页面标题、说明、状态摘要和工具栏留白；表格使用更清晰的状态徽标、操作组和窄屏横向滚动容器。
  - 弹窗统一标题、底部操作和表单间距，避免嵌套卡片和装饰性阴影。
- [ ] **Step 4: Run tests and full verification**
  - Run: `cd frontend && npx vitest run`
  - Run: `cd frontend && npm run build`
  - Run: 浏览器检查登录页、首页和后台页在 375px、768px、1440px 的截图和横向溢出。
  - Expected: 测试全部通过、构建退出码为 0、页面无横向滚动和明显文字重叠。
