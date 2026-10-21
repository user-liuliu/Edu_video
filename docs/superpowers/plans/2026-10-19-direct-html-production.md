# 整片 HTML 正式集成计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将已认可的整片 HTML 样片链路接入教师正式视频制作、预览、修改及导出。
**Architecture:** 唯一生产链路为 direct-html-film-1；冻结整片讲稿与句级预估时钟，模型一次生成完整 HTML，随后生成配音并建立句级单调时间映射；播放器和导出使用同一封存 HTML 与连续音轨。按用户最新要求删除旧链路，并在已验证备份后清空旧项目及关联产物。
**Tech Stack:** FastAPI / SQLAlchemy / Celery / MinIO / Vue / sandbox iframe / Playwright / FFmpeg。
**Spec:** docs/superpowers/specs/2026-10-18-phase-3-video-design.md；用户本轮已批准正式集成4192验证路线。

## Global Constraints
- 保留大纲审核、每教师任务额度、版本隔离和失败重试，不增加视频阶段 AI 审核；旧视频按用户要求清空。
- HTML 自由原生绘制；仅约束安全、播放接口与时钟，不增加动作白名单或题材专用修补。
- 测试使用系统配音或隔离替身，禁止调用配音模型；正式服务继续现有模型配音。
- 在当前已有未提交第三阶段代码上增量实现，不丢弃工作区，不提交推送。
- 验证后部署8080，保留MinIO9000/9001；备份后删除现有项目、大纲任务、视频版本和关联存储对象，保留账号、偏好、管理员及模型配置；部署前保存镜像回退点并确认无活动任务。

## Review Focus
- 非法/外联/自主播放HTML：隔离沙箱、禁止外部资源、前后seek和冻结时钟运行检查。
- 配音分句不同与静音：按归一化正文匹配真实字幕，连续单调映射，音频格式一致。
- 重试与局部修改：冻结讲稿、可复用音轨；画面修改重生成整片以保连续并明确告知，失败不影响来源版本。
- 导出一致性：预览封存资源哈希、同一HTML和音轨、无需再调用模型。
- 旧版本：删除Scene/逐段HTML生产路径与专属测试，保留新版共享的配音、资源、权限和任务防护测试。

### Task 1: 整片HTML契约和渲染
- [x] 新增 backend/app/videos/direct_html.py、direct_runtime.js、direct_render.py，测试 test_direct_html.py。
- [x] 验证HTML安全、整片句级校时、冻结时钟、反向seek、封存摘要；Canvas累积绘制反例先失败后修复，增加真实像素比较。
- [x] 接入 renderer/app.py、worker.py、render_client.py 的 validate-html / render-html，移除旧渲染路由。

### Task 2: 业务链路、资源与修改
- [x] 新增 direct_pipeline.py，通过现有任务lease守卫存储整片初稿、音轨与校时。
- [x] service.py标记新协议，pipeline仅调度整片链路；删除旧Scene、旧编排和旧逐段播放器。
- [x] test_direct_pipeline.py验证默认链路、无视频审核、跨用户隔离、失败重试、音轨复用及导出无模型。

### Task 3: 连续预览与发布
- [x] HtmlAnimationPlayer仅单文档单音轨；VideoPreviewView保留教学段落导航和范围修改。
- [x] 新增前端测试验证跨段seek不重载；前端18文件176项通过，生产构建通过。
- [x] 后端全量352项通过；独立审查完成，Canvas finding已RED→GREEN；系统音频认可样片完成导出/解码和新版运行检查。
- [x] 备份并清空旧项目、部署候选镜像，检查实际8080和保留配置指纹。

## 验收边界
- 本轮业务流程测试使用隔离替身，未调用配音模型。复用认可样片HTML与系统音频的导出不等同于新业务链路真实模型端到端验收。
- 竖屏/方形仍以1280×720舞台等比居中；未承诺自动重排或所有题材的主观动画质量。

## Progress
- Planning complete. Existing branch codex/phase3-video-pipeline contains required uncommitted work; implement in place to preserve it.
- 2026-10-19：用户明确要求全部采用新版，并删除已有项目和成片。已完成数据库归档与30个MinIO对象逐个SHA256备份验证；删除1项目、3任务、2版本、14片段及37条对应checkpoint记录和30个对象。
- 3账号、1偏好、3系统设置、6模型配置的完整行指纹前后一致。未清数据卷或Redis，未改密钥和端口。
- 镜像构建成功；8080健康、匿名401、教师3种项目列表为空，0005=head，Celery pong，worker调用实际renderer完成1秒1280×720 MP4导出，无模型调用。
- 部署一致性检查：111个backend/app文件、4个renderer文件、41个前端构建文件匹配；backend/worker/scheduler为同镜像；理科/故事真实运行检查和短导出通过。
- 最终重复全量：后端352 passed in128.73s；前端18 files/176 tests，生产构建成功。旧Scene专属测试随退役删除，非屏蔽新版失败。
- 数据备份：.superpowers/backups/direct-html-reset-20261019-172528/；镜像回退tag before-direct-20261019。源码未提交/推送/合并。
