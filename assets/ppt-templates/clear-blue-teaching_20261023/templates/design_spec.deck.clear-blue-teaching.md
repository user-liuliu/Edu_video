---
deck_id: clear-blue-teaching
kind: deck
category: scenario
summary: 面向课堂讲授与知识复习的清晰教学课件
keywords: [教学, 简洁, 清蓝, 知识讲解, 课堂练习]
primary_color: '#2465D9'
canvas_format: ppt169
canvas_width: 1280
canvas_height: 720
canvas_viewbox: '0 0 1280 720'
replication_mode: standard
native_structure_mode: structured
page_count: 7
placeholders:
  01_cover: ["{{EYEBROW}}", "{{TITLE_1}}", "{{TITLE_2}}", "{{SUBTITLE_1}}", "{{SUBTITLE_2}}", "{{AUTHOR}}", "{{CAPTION}}", "{{COURSE_NAME}}", "{{PAGE_NUM}}"]
  02a_content_concept: ["{{PAGE_TITLE}}", "{{FORMULA}}", "{{PARAM_1}}", "{{EXPLAIN_1_1}}", "{{EXPLAIN_1_2}}", "{{EXPLAIN_1_3}}", "{{PARAM_2}}", "{{EXPLAIN_2_1}}", "{{EXPLAIN_2_2}}", "{{EXPLAIN_2_3}}", "{{PARAM_3}}", "{{EXPLAIN_3_1}}", "{{EXPLAIN_3_2}}", "{{EXPLAIN_3_3}}", "{{COURSE_NAME}}", "{{PAGE_NUM}}"]
  02b_content_image_text: ["{{PAGE_TITLE}}", "{{OBS_TITLE_1}}", "{{OBS_BODY_1}}", "{{OBS_TITLE_2}}", "{{OBS_BODY_2}}", "{{OBS_TITLE_3}}", "{{OBS_BODY_3}}", "{{FIGURE_CAPTION}}", "{{COURSE_NAME}}", "{{PAGE_NUM}}"]
  02c_content_compare: ["{{PAGE_TITLE}}", "{{LEFT_LABEL}}", "{{RIGHT_LABEL}}", "{{LEFT_DESCRIPTION}}", "{{RIGHT_DESCRIPTION}}", "{{CONCLUSION}}", "{{COURSE_NAME}}", "{{PAGE_NUM}}"]
  02d_content_process: ["{{PAGE_TITLE}}", "{{INTRO}}", "{{STEP_TITLE_1}}", "{{STEP_BODY_1_1}}", "{{STEP_BODY_1_2}}", "{{STEP_BODY_1_3}}", "{{STEP_TITLE_2}}", "{{STEP_BODY_2_1}}", "{{STEP_BODY_2_2}}", "{{STEP_BODY_2_3}}", "{{STEP_TITLE_3}}", "{{STEP_BODY_3_1}}", "{{STEP_BODY_3_2}}", "{{STEP_BODY_3_3}}", "{{HINT}}", "{{COURSE_NAME}}", "{{PAGE_NUM}}"]
  02e_content_practice: ["{{PAGE_TITLE}}", "{{QUESTION_1}}", "{{QUESTION_2}}", "{{TASK_1}}", "{{TASK_2}}", "{{TASK_3}}", "{{HINT_TITLE}}", "{{HINT_BODY_1}}", "{{HINT_BODY_2}}", "{{HINT_BODY_3}}", "{{HINT_BODY_4}}", "{{PRACTICE_FOOTER}}", "{{COURSE_NAME}}", "{{PAGE_NUM}}"]
  03_ending: ["{{PAGE_TITLE}}", "{{SUMMARY_LEAD}}", "{{TAKEAWAY_1}}", "{{TAKEAWAY_DETAIL_1}}", "{{TAKEAWAY_2}}", "{{TAKEAWAY_DETAIL_2}}", "{{TAKEAWAY_3}}", "{{TAKEAWAY_DETAIL_3}}", "{{ENDING_QUESTION}}", "{{COURSE_NAME}}", "{{PAGE_NUM}}"]
---
# 简洁教学 · 清蓝 — Design Specification

## I. Template Overview
- Template ID: clear-blue-teaching; version: 1.0.0; scope: project.
- 用途：课堂讲授、知识梳理、方法演示、练习与复习。示例为初三数学二次函数；其他学科可替换内容和图示。
- 课堂投影优先：白底、清楚的层级、充分留白；每页围绕一个教学目标。
- 七页为可选版式原型，不限制实际页数和顺序。同一版式可重复使用。
- 整份课件使用同一 template_id/version，画布统一为16:9。

## II. Color Scheme
| Role | Value | Use |
|---|---|---|
| Background | #FFFFFF | 全页底色 |
| Title | #173359 | 标题 |
| Body | #273B53 | 正文 |
| Accent | #2465D9 | 重点、公式、图线与编号 |
| Muted | #61738A | 次要说明、页脚 |
| Accent surface | #EAF1FC | 图示与重点区域 |
| Rule | #DCE5F1 | 细分隔线 |
只在教学语义确有需要时增加辅助色，不允许逐页重新配色。

## III. Typography
- 中文 Microsoft YaHei；拉丁字母与数字 Arial。不依赖联网字体。
- title: 48 px / 36 pt；body: 30 px / 22.5 pt。
- 封面标题64px；正文28–32px；图注22–26px；页脚18px。
- 教学正文默认至少28px，短说明允许26px。
- 左对齐为主，公式与图注可以居中。多行正文约1.48倍行距。
- 标题优先一行，封面最多两行。溢出时精简或拆页，不缩小正文塞入长内容。

## IV. Signature Design Elements
- 1280×720；左右安全区64px；内容标题y=87–159；教学区y=176–640；页脚线y=660。
- 白底深蓝标题，清蓝重点，浅蓝公式与图示区；页脚一枚7px蓝色方块。
- 不用渐变、厚阴影、无意义卡片或装饰性图表。
- 概念用公式聚焦；图文页用左右信息互证；对比页保持对称；方法页使用有序步骤。
- 课程内容、公式和基础图形可编辑；复杂插图可以局部图片形式嵌入。禁止整页栅格化。
- Master统一背景、页脚线和标识；Layout包含固定分隔；Slot承载课程内容。图解用object+proxy可替换绑定。

## V. Page Roster
| SVG | Layout | Role | Capacity / Frame |
|---|---|---|---|
| `01_cover.svg` | cover | 课程封面 | 双行标题每行最多9字；副标题每行19字；右图438×394 |
| `02a_content_concept.svg` | concept | 概念与公式 | 一条公式、三栏参数；每栏正文3行，每行约11字 |
| `02b_content_image_text.svg` | image-text | 图文讲解 | 三组短要点；图示490×354；一行图注 |
| `02c_content_compare.svg` | compare | 双栏对比 | 两个对称图示，短标题、单行说明和共同结论 |
| `02d_content_process.svg` | process | 方法与流程 | 三步；每步短标题、3行正文，每行约12字 |
| `02e_content_practice.svg` | practice | 课堂练习 | 两行题干、3条小题、4行提示；解析可另起一页 |
| `03_ending.svg` | summary | 回顾与延伸 | 核心结论、3组回顾和延伸问题 |

## VI. Placeholder Rules
- frontmatter按SVG basename覆盖语义标记；原型保留{{TOKEN}}，真实示例在svg_output。
- 同一Layout的槽位ID、类型、索引与尺寸固定；修改单页不改变全局模板和其他页内容。
- 图解为二次函数演示内容，不是固定风格。其他学科需替换为适配图示。
- 数学曲线使用原生基础图形，不是可自动重算的数据图表。正式统计图应独立使用原生图表。
- 超出容量必须精简、换合适版式或拆页，不能叠字越界。
