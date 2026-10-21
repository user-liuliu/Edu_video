# 原创像素人物素材库

按暖色乡村 RPG 方向逐像素绘制，参考星露谷的亲切比例和配色氛围。所有人物、服装和环境图像均由本目录源码新绘，未使用星露谷或 LPC 图像层。

## 文件
- `build.py`：绘画源文件，只依赖 Pillow；`python pixel-art/original-cast/build.py` 重新生成 staging 图集、角色总览和动作 GIF。
- `generated/*.png`：20 个完整人物图集和 12 个独立物体，每张人物图集 512×3072 像素，透明背景，64×64 单格；索引 PNG 无损保留绘制颜色和二值透明度。
- `generated/manifest.json`：角色描述、动作帧数/FPS/循环规则、四方向顺序、每帧手部连接点与文件 SHA256。
- `catalog.html`：可离线打开的动画预览，切换动作/朝向/角色，拖动时间检验倒退定位。由 `python pixel-art/original-cast/catalog.py` 使用生产打包器生成。
- `cast-preview.png`、`actions-preview.gif`：角色总览与动作预览。
- `backend/app/videos/sprite_assets/`：动画生成实际加载的副本。修改 `build.py` 后先生成 staging，再验证和复制到该目录；仅重新生成 staging 不改变运行库。

## 内容
20 种角色：农夫/农妇、四种儿童、男女学生、男女教师、爷爷/奶奶、医生、工人、商人、书生、古风少女、旅人、厨师、古风长者。不同发型、年龄比例、肤色、衣服、职业配件，不是同一人物换色。古风角色为通用原创衣着，不代表特定历史人物。

11 种动态动作：待机、走、跑、挥手、点头、说话、拾取、端物走、坐下、跳跃、劳动手势。四方向均绘制；另有 neutral/hands_front/raised_arms 三张独立姿态。

代码例子：
```javascript
const a = EduSprites.actor({
  variant: 'girl_rose', x: 320, y: 480, scale: 3, direction: 'right',
  ...EduSprites.animate('wave', t, {start: 2})
});
EduSprites.drawActor(ctx, a);
const hand = EduSprites.anchor(a, 'hand');
```
移动继续用 `travel`；端物行走使用 `travel({...route,action:'carry'},t)`。物品需要每帧跟随手部连接点；坐下需要场景座椅，劳动手势需要配套道具。跳跃自带离地位移。一次性动作到末帧停止，重播要使用新的 start。`ochre/teal/linen` 保留为新角色别名；已冻结视频继续使用其内嵌旧图像和原署名。

PNG 采用原始像素，建议整数缩放、nearest-neighbor。绘画采用 Pixel Art Studio 的 palette/parameterized pose/visual critique 工作流；运行无需安装 Aseprite、调用生图 API 或联网。工作流来源 `Gamezxz/pixel-art-studio`，MIT；图像来源见 `CREDITS.txt`，不对 AI 辅助图像主张未经核实的排他著作权。

旧库 34 文件已移出实际目录，可恢复 ZIP 和原目录保留于 `.superpowers/backups/sprite-assets-before-original-20261020-132930/`。

## 接入验证（2026-10-20）
新库已部署到本地 backend、worker 和 renderer，三个服务的素材及运行时摘要一致；新生成的像素动画会使用这套素材。已保存的视频保留其内嵌图像和原署名。后端 423 项通过、1 项因 Linux 测试镜像缺少 Node 跳过；另行验证了 10,560 个手部接触点、44 组动作/方向的离线播放与倒退定位，并通过生产渲染器导出 6 秒 MP4。
