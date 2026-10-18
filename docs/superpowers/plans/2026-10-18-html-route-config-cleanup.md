# HTML 动画路线配置清理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 移除管理员生图模型及图片数量配置，并解除大纲对旧配置的依赖。

**Architecture:** 保持FastAPI/Vue；从有效模型用途和生成参数契约删除退役字段，读取旧数据库行时忽略；用户后续明确要求清除旧生图密钥，已在部署环境完成核验和清理。保留画面描述及结构大小保护。

**Tech Stack:** Python/FastAPI/Pydantic/PostgreSQL、Vue/Element Plus/Vitest。

**Spec:** docs/superpowers/specs/2026-10-18-phase-3-video-design.md；2026-10-18用户批准纯HTML动画路线。

## Global Constraints
- 保留看图识别、配音、审核、偏好、搜索及已有配置内容。
- 保留同时生成任务数、失败重试次数、时长允许偏差、长期记忆。
- 不删除旧image_gen配置行；旧生成参数多余字段忽略。密钥清理遵循用户后续的明确授权，不影响其他模型配置。
- 大纲画面描述类型及1—12条结构保护不变，不将其作为图片/HTML镜头配额。
- 仅使用独立测试库，不调用真实模型，不输出凭据。
- 本次清理不表示正式HTML生成/MP4链路已实现。初始实施范围不含提交/推送；用户现已明确授权写明修改注释并推送当前分支。

## Review Focus
- 旧image_gen行不导致列表异常或可用性误判。
- 旧generation_params可读写，其余设置不丢失。
- 生成、改写、重新审核不受旧画面数量范围限制。
- 退役用途不能写入/测试，看图识别保留。
- 教师任务额度、审核和时长提示不退化。

### Task 1: 前后端配置清理
**Files:** backend/app/purposes.py、model_configs/{service,probe}.py、settings_store/schemas.py、outline/{policy,graph,service}.py；frontend/src/api/admin.ts、views/admin/{PageConfigTab,ModelConfigDialog}.vue；对应tests。
**Interfaces:** 六项有效模型用途；四项GenerationParams；旧JSON字段忽略。
- [x] 更新回归：列表、旧数据、禁用入口、系统可用性、参数读写、1及7条画面生成/重审、管理员控件保存。
- [x] 运行定向测试记录预期失败。
- [x] 实现退役项清理并验证测试转绿。
- [x] 后端全量pytest、前端全量Vitest及构建通过。

### Task 2: 文档、审查及部署
**Files:** README.md、任务存档.md、第三阶段设计及本计划。
**Interfaces:** 8080现有页面不再显示生图和图片数量配置。
- [x] 同步HTML主路线及实施边界，旧设计留作历史依据。
- [x] 独立审查兼容性及遗漏引用，git diff --check通过。
- [x] 活跃任务为0后更新backend/worker/scheduler/frontend，保留所有数据卷。
- [x] 核验健康、实际管理员API与部署资源；当前教师会话未切换，管理员视觉验收不计入通过。组件DOM测试覆盖控件。
