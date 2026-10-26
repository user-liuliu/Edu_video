# 学术正式 · 墨红

2026-10-25 项目级模板原型，版本1.0.0。纸白底色、深墨文字与酒红强调，以开放分栏和细线突出论证。

当前用于审阅视觉方向，尚未接入网站风格选择与线上生成。既有清蓝模板保持原状。

## 可用内容

- 16:9，1280×720；1个母版、7个原生版式。
- 七种教学角色：课程封面、概念与公式、图文讲解、双栏对比、方法步骤、课堂练习、总结延伸。
- `exports/academic-formal_sample.pptx`：填充“二次函数”示例，可编辑文本、曲线和几何对象。
- `exports/academic-formal_template_preview.pptx`：带填写提示的版式审阅文件。
- `templates/*.svg`：保留双花括号标记的可复用模板源。
- `templates/design_spec.deck.academic-formal.md`：配色、字体、版式规范与占位符清单。
- `templates/tokens.json`、`templates/style_prompt.md`：后续接入的风格标识、设计参数与提示词。
- `sources/build_template.py`：重建模板和样例SVG；`sources/sample_fixture.json`：教学内容。
- `validation/`：规范检查、原生PPTX结构审计与最终PPTX回读预览。

## 本地重建

在仓库根目录使用项目测试虚拟环境执行：

```powershell
.superpowers/test-venv/Scripts/python.exe assets/ppt-templates/academic-formal_20261025/sources/build_template.py
.superpowers/test-venv/Scripts/python.exe assets/ppt-templates/academic-formal_20261025/sources/export_review.py
```

导出依赖本机PPT Master工具路径；输出已存在时导出器会拒绝覆盖，应先备份旧文件后显式处理。新内容应按规范控制长度、拆行，并重新检查，不应缩小文字硬塞。

## 检查与边界

模板SVG与样例SVG各7页通过canonical authoring检查；样例PPTX严格回读7页、0警告。结构审计确认文本和图形为原生DrawingML对象，无整页截图。浏览器展示的是从最终PPTX解析的SVG，已进行视觉检查，但不等同于在PowerPoint或WPS中打开的渲染结果。

本轮只生成模板，未注册到全局技能库，也未修改网站、用户课件或积分。插图与曲线为可编辑矢量；曲线图用作教学示意，非测量数据。
