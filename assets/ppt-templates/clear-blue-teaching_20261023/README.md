# 简洁教学 · 清蓝

项目级教学课件模板原型，ID：`clear-blue-teaching`，版本：`1.0.0`。由本机安装的 ppt-master v6.7.0 进行原生 DrawingML 编译和结构校验。当前状态为 prototype，尚未接入项目的生产生成服务。

## 已包含的内容

- `templates/design_spec.deck.clear-blue-teaching.md`：画布、配色、字体、版式与容量规范。
- `templates/style_prompt.md`：固定风格、大纲生成、单页生成、选页改写与自动推荐边界提示词。
- `templates/tokens.json`：模板 ID、版本、设计参数与可选版式清单。
- `templates/*.svg`：7 个带语义槽位的可复用版式原型，保留 `{{TOKEN}}`。
- `svg_output/*.svg`：以初三数学“二次函数”为内容的 7 页样例。
- `sample_content.json`：示例槽位内容。
- `exports/clear-blue-teaching_template_preview.pptx`：结构化模板审阅文件。
- `exports/clear-blue-teaching_sample.pptx`：整份中文示例课件，文字、公式文本与基础图形可编辑。
- `preview.html`：SVG 设计预览。
- `validation/native-preview.html`：从最终 PPTX 独立读回的 SVG 预览；不是 PowerPoint/WPS 应用截图。
- `validation/native-preview.jpg`：浏览器预览截图。
- `validation/build-report.json`、`pptx-readback.json`：编译与文件读回记录。

## 使用边界

画布固定16:9，1280×720，对应PPTX约13.333×7.5英寸。用户无需在制作页面设置比例。

七种版式分别是封面、概念与公式、图文讲解、双栏对比、方法与流程、课堂练习、回顾与延伸。它们不是固定的七页顺序；正式课件依据确认后的大纲选择版式、重复使用、增删和排序。

整份课件锁定同一 template_id/version。自动推荐应从已发布的模板目录选一个模板。选页修改须保留稳定页面ID，只应用到选中页面。

数学曲线和公式示例以可编辑的基础图形/文字导出；它们不是可自动重算的统计图或原生公式对象。复杂插图未来可用局部图片，整页不可栅格化。示例抛物线为教学示意，不是实测投篮数据。

本套资源包含可复用设计与提示词，不包含文件解析、模型接口、队列、页版本、在线预览和导出API。WPS式手动编辑器仍属于后续功能。

## 本地复现

需要Python 3.10+、PyYAML、python-pptx，以及安装完整的ppt-master v6.7.0（含scripts及其依赖）。模板工具属于本机开发依赖，未复制整个skill到项目。

```powershell
# 重新生成原型及示例SVG；会覆盖对应资源，不修改业务代码。
python sources/build_template.py

# 通过规范校验后导出两份PPTX；替换已有文件须显式--force。
python sources/export_review.py --skill-dir C:/Users/Lenovo/.codex/skills/ppt-master --force

# 预览设计稿，使用空闲端口。
python -m http.server 8767 --bind 127.0.0.1
```

从该目录执行命令。`build_template.py`是原型构建源；直接编辑已生成SVG后再次执行会覆盖修改。需要调整模板时应同步修改构建源、规范和tokens，再重建与验收。`preview.html`为静态目录页。

本次导出使用本机bundled Python 3.12，PyYAML从本机已安装版本临时放入被git忽略的`.superpowers/ppt-template-tools/python`。这不是项目服务端运行依赖配置。

## 验证范围

- 7个原型与7个示例SVG均通过canonical-authoring规范检查：0报错、0警告。
- 两份PPTX均读回确认：7页、1个母版、7个版式、71个完整区域内容槽位。
- 中文示例PPTX固定16:9，主题字体Arial/Microsoft YaHei，主色#2465D9，无未填充标记，无整页图片。
- 最终文件经OOXML导入重新得到7页SVG，转换诊断0警告，并在浏览器预览。
- 未在PowerPoint或WPS桌面应用内打开验证，实际应用中的字体替换和显示仍需最终验收。

## 后续接入建议

模板人工验收后再改为published并注册到业务模板目录。首先以本套打通独立PPT生成链路；随后制作其他风格，沿用相同的模板ID/版本与页面模型契约。
