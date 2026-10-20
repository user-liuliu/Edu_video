# HTML 预览首帧确认

## 现象和证据

用户截图中《曹冲称象》第四版可播放但画面全空。第四版 ID 为 `07f4487a-22a5-42cf-ba21-981aabd0020d`。本次在正式 8080、Windows Chrome、Edge 和隔离 Chromium 验证实际播放器，不仅检查资源 API。原截图的全空现象未稳定复现，不能将某一个浏览器缓存或 GPU 原因当作已确定根因。

确认原播放器的缺陷：只收到 `edu-preview:ready` 即启用播放，未等待任何帧绘制结果；画面 seek 不等待完成，可积压多个请求；首帧无绘制确认。新增失败测试实证仅 ready、无 rendered 时旧代码仍启用播放。

## 修改

- 只在前端给封存 HTML 追加可信播放桥，不改原资产、摘要和历史版本。
- 每次定位前重新计算舞台缩放，等待实际 `window.seek` 完成；首帧再等待浏览器绘制机会，才启用播放。
- 一次只允许一个未确认绘制请求，快速拖动和音频时钟只保留最新时间，避免渲染积压。
- 校验 iframe 来源、channel 和请求编号，忽略外来或过期确认。
- 定位失败或超时则暂停并提示重新加载，不再空白时继续假装可播放。
- 保持 sandbox 仅 allow-scripts，无新增外联权限。

## 验证

- 原 ready 无绘制回归测试先失败，再通过。
- 执行真实注入脚本测试，覆盖封存运行时含字面量 body 结束标签和等待绘制确认。
- Windows Chrome/Edge：重复进入五次、调整宽度、第一/第四版切换、0/35/80/120/150 秒定位和播放暂停。
- 隔离 Chromium：上述五个时间点直接读取 1280×720 Canvas，采样均有 467–513 种颜色；保存实际播放器截图。
- 未重新调用动画生成模型或付费配音，未修改项目已导出状态。

浏览器诊断脚本和截图保存在 `.superpowers/sdd/preview-render-fix` 和本机临时目录，不包含在产品代码中。

最终前端全量测试 `19 files / 186 passed`，`npm run build` 成功。已部署 `edu-video-frontend:render-ack-20261020` 至正式 8080，部署后再次通过 Windows Chrome、Edge 和隔离 Chromium 的上述检查，截图为 `.superpowers/sdd/preview-render-fix/preview-deployed.png`。保留回退镜像 `edu-video-frontend:before-render-ack-20261020`；临时候选容器与临时测试会话文件已清理。
