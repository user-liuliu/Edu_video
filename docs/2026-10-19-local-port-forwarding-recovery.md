# 2026-10-19 本地端口空响应恢复

- 现象：Chrome访问127.0.0.1:8080显示ERR_EMPTY_RESPONSE；curl直连同样得到Empty reply。
- 定位：frontend容器内首页200，backend通过frontend读取首页200及API健康正常。Docker Desktop重启后恢复了旧转发：8080指向172.20.0.2:80，而frontend实际IP为172.20.0.3。宿主机请求没有到达Nginx。
- 修复：重启frontend容器，日志确认移除旧172.20.0.2转发并添加正确172.20.0.3转发。MinIO也出现旧转发，重启MinIO后恢复。未重建镜像、未更改端口、未删除容器或数据卷。
- 验证：首页8080返回200；/api/health返回status=ok、db=true；9000/minio/health/live与9001返回200。内置浏览器实际打开8080并显示登录页。Celery inspect ping返回pong。
- 修复前后数据计数一致：users3、preferences1、system_settings3、model_configs6、video_projects1、outline_jobs3、video_versions2、video_segments14；MinIO20对象共53197011字节，活动任务0。没有重新清理项目或成片。
- 剩余边界：宿主机Redis6379/Postgres5432探测仍收到空响应，内部应用连接正常。批量停止worker/scheduler并重启数据库/Redis的调用被自动审批拒绝，工具仅返回blocked by policy，未提供具体原因；该调用未执行，未重试绕过限制。

## 21:02 再次空响应（本次恢复于 21:05）

- 本次复现：localhost:8080 和 127.0.0.1:8080 均返回 curl 52 / ERR_EMPTY_RESPONSE，包含项目视频地址；不是单纯 localhost 或 IPv6 差异。frontend 容器内 wget 首页成功。
- 新证据：Docker 日志在 21:00:48 报 WSL bootstrap exit status 0xc00000fd，21:00:58 重新启动引擎，容器在 21:01 左右恢复。21:01:03 端口转发恢复为 8080→172.20.0.3:80，但本次 frontend 实际是 172.20.0.4。MinIO 转发仍为 172.20.0.2，但实际是 172.20.0.7。
- 恢复操作：只重启 frontend、minio；日志确认 8080 更新至 .4，9000/9001 更新至 .7。未重启数据库、Redis或整个Docker，未删除项目、成片、容器、数据卷，未调整端口或全局 WSL 配置。
- 21:05–21:07 实测：localhost 与 127.0.0.1 的项目视频路径均 HTTP 200，两者 API 健康均为 status=ok、db=true；4 个入口 JS/CSS 资源均 HTTP 200；MinIO live 和 console 均 HTTP 200。内置浏览器打开用户给定的 localhost 项目路径，正常进入登录页（该 origin 未登录），不再空响应。
- 数据核对：users=3、preferences=1、system_settings=3、model_configs=6、video_projects=1、outline_jobs=4、video_versions=2、video_segments=14；MinIO 仍为 20 对象、53197011 字节。相较上次新增一个 video_export 任务；本次未创建生成或导出任务。
- 任务核对：Celery ping=pong；video_export a07a5e5f-5664-4747-abfc-14f433f76c02 为 running、attempts=2，worker active 中存在相同任务，21:06:43 仍更新心跳。此次仅确认正在运行，未宣称 MP4 已导出完成。
- 尚未根治：端口空响应的直接原因已确认是旧 IP 转发；引擎为何异常退出尚未查明。主机当时可用物理内存约 600 MB / 16 GB，属于资源压力线索，不能据此认定本次由 OOM 引起；容器 inspect OOMKilled=false。数据库和 Redis 的宿主机映射未在本次重启处理，应用内部连接正常。
