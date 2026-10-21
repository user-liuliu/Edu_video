# 视频助手v1.0

- 节点日期：2026-10-21（Asia/Hong_Kong）
- Git 标签：`视频助手v1.0`（附注标签，指向包含本文档的快照提交）
- 创建分支：`codex/phase3-video-pipeline`
- 范围：当前工作区的前后端代码、数据库迁移、动画生成服务、渲染器、离线人物素材、项目内技能参考、测试及设计文档。

## 本阶段功能

- 需求与参考素材生成大纲，大纲审核及确认后制作完整 HTML 动画。
- HTML 预览、字幕与配音校时、满意后导出 MP4。
- 故事人物支持离线素材；教师明确非像素风时由模型原生绘制，并携带人物和动物姿态规范。
- 系统配音选项、预览绘帧确认、模型连接与代码修复、渲染资源限制等现有改进。

## 回到节点

先保存当前未提交修改，再从标签创建恢复分支，不直接覆盖后续开发分支：

```powershell
git switch -c codex/restore-video-assistant-v1.0 '视频助手v1.0'
```

若以后已经使用同名恢复分支，换一个新的分支名。创建恢复分支仅还原代码；运行环境需要按当时环境重新构建和部署。涉及数据库迁移时先检查数据库兼容性。

## 当前本机容器镜像

为以下实际运行镜像保留本机标签，方便对照和恢复运行服务；这些标签不替代镜像导出备份，清理 Docker 镜像时仍需保留：

| 服务 | 节点镜像标签 | 当前镜像 ID |
| --- | --- | --- |
| backend / worker / scheduler | `edu-video-backend:video-assistant-v1.0` | `sha256:e76059e700f924135cb60000b7b0a30e2c3d3192a6aaf1aa8dd30da29f719f68` |
| frontend | `edu-video-frontend:video-assistant-v1.0` | `sha256:1424adc612cce3aa4e1401becc388f15526e2593e671a2f1aa242ffab6ed49bb` |
| renderer | `edu-video-renderer:video-assistant-v1.0` | `sha256:b65c15d4a0e123d225a804f74c3401c2c3fb90be1190c46c6aaf3aa72f8b09d0` |

## 边界

这是代码与本机镜像检查点，未备份 PostgreSQL 数据卷、MinIO 对象、Redis 数据或 `.env` 中的密钥配置；运行数据不随 Git 标签回滚。临时诊断目录、依赖缓存和构建产物按现有 `.gitignore` 排除。

创建节点不改变业务代码，不重新调用生成或配音模型；本次核对快照文件、标签指向及镜像标签，不代表新增一轮画面质量或全流程测试。此前测试记录见 `docs/2026-10-20-non-pixel-drawing-guidance.md` 与其他阶段验证文档。
