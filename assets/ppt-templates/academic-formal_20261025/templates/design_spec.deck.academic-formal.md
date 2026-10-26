---
deck_id: academic-formal
kind: deck
category: scenario
summary: 以定义、图像证据和方法验证组织正式课堂讲授与教学汇报
keywords:
- 教学
- 学术
- 正式
primary_color: '#8B3547'
canvas_format: ppt169
canvas_width: 1280
canvas_height: 720
canvas_viewbox: 0 0 1280 720
replication_mode: standard
native_structure_mode: structured
page_count: 7
placeholders:
  01_cover:
  - '{{EYEBROW}}'
  - '{{TITLE_1}}'
  - '{{TITLE_2}}'
  - '{{SUBTITLE_1}}'
  - '{{SUBTITLE_2}}'
  - '{{AUTHOR}}'
  - '{{CAPTION_1}}'
  - '{{CAPTION_2}}'
  - '{{COURSE_NAME}}'
  - '{{PAGE_NUM}}'
  02a_content_concept:
  - '{{PAGE_TITLE}}'
  - '{{FORMULA}}'
  - '{{PARAM_1}}'
  - '{{EXPLAIN_1_1}}'
  - '{{EXPLAIN_1_2}}'
  - '{{EXPLAIN_1_3}}'
  - '{{PARAM_2}}'
  - '{{EXPLAIN_2_1}}'
  - '{{EXPLAIN_2_2}}'
  - '{{EXPLAIN_2_3}}'
  - '{{PARAM_3}}'
  - '{{EXPLAIN_3_1}}'
  - '{{EXPLAIN_3_2}}'
  - '{{EXPLAIN_3_3}}'
  - '{{COURSE_NAME}}'
  - '{{PAGE_NUM}}'
  02b_content_image_text:
  - '{{PAGE_TITLE}}'
  - '{{OBS_TITLE_1}}'
  - '{{OBS_BODY_1}}'
  - '{{OBS_TITLE_2}}'
  - '{{OBS_BODY_2}}'
  - '{{OBS_TITLE_3}}'
  - '{{OBS_BODY_3}}'
  - '{{FIGURE_CAPTION}}'
  - '{{COURSE_NAME}}'
  - '{{PAGE_NUM}}'
  02c_content_compare:
  - '{{PAGE_TITLE}}'
  - '{{LEFT_LABEL}}'
  - '{{RIGHT_LABEL}}'
  - '{{LEFT_DESCRIPTION}}'
  - '{{RIGHT_DESCRIPTION}}'
  - '{{CONCLUSION}}'
  - '{{COURSE_NAME}}'
  - '{{PAGE_NUM}}'
  02d_content_process:
  - '{{PAGE_TITLE}}'
  - '{{INTRO}}'
  - '{{STEP_TITLE_1}}'
  - '{{STEP_BODY_1_1}}'
  - '{{STEP_BODY_1_2}}'
  - '{{STEP_BODY_1_3}}'
  - '{{STEP_TITLE_2}}'
  - '{{STEP_BODY_2_1}}'
  - '{{STEP_BODY_2_2}}'
  - '{{STEP_BODY_2_3}}'
  - '{{STEP_TITLE_3}}'
  - '{{STEP_BODY_3_1}}'
  - '{{STEP_BODY_3_2}}'
  - '{{STEP_BODY_3_3}}'
  - '{{HINT}}'
  - '{{COURSE_NAME}}'
  - '{{PAGE_NUM}}'
  02e_content_practice:
  - '{{PAGE_TITLE}}'
  - '{{QUESTION_1}}'
  - '{{QUESTION_2}}'
  - '{{TASK_1}}'
  - '{{TASK_2}}'
  - '{{TASK_3}}'
  - '{{HINT_TITLE}}'
  - '{{HINT_BODY_1}}'
  - '{{HINT_BODY_2}}'
  - '{{HINT_BODY_3}}'
  - '{{HINT_BODY_4}}'
  - '{{PRACTICE_FOOTER}}'
  - '{{COURSE_NAME}}'
  - '{{PAGE_NUM}}'
  03_ending:
  - '{{PAGE_TITLE}}'
  - '{{SUMMARY_LEAD}}'
  - '{{TAKEAWAY_1}}'
  - '{{TAKEAWAY_DETAIL_1}}'
  - '{{TAKEAWAY_2}}'
  - '{{TAKEAWAY_DETAIL_2}}'
  - '{{TAKEAWAY_3}}'
  - '{{TAKEAWAY_DETAIL_3}}'
  - '{{ENDING_QUESTION}}'
  - '{{COURSE_NAME}}'
  - '{{PAGE_NUM}}'
---

# 学术正式 · 墨红 — Design Specification

## I. Template Overview
- 课件家族：以定义、图像证据和方法验证组织正式课堂讲授与教学汇报。面向教师课堂投影与课后复习，示例为初三数学“二次函数”。
- 代表角色包括情境封面、概念公式、图像解释、性质比较、方法步骤、课堂练习和总结延伸；不限定未来课件页数和顺序。
- 配色、字体与版式为本轮设计师选择，用户已授权生成两套项目级模板供审阅。未提供机构标志，不加入虚构品牌。

## II. Color Scheme
| Role | HEX |
|---|---|
| bg | #FAFAF7 |
| title | #202D3A |
| body | #34414B |
| accent | #8B3547 |
| secondary | #3E6179 |
| muted | #63717A |
| surface | #F0E6E7 |
| surface2 | #EAF0F3 |
| rule | #CFD4D7 |
| white | #FFFFFF |

## III. Typography
- 中文Microsoft YaHei，西文与数学记号Arial；封面64px，页标题44px，正文28–32px，图注22px，页脚18px；步骤标题32px，提示与延伸25px。

## IV. Signature Design Elements
- 纸白底、深墨文字与酒红论点，蓝灰辅助图像；横线和开放列组织逻辑。
- 封面采用独立图像窄栏，概念由公式引出参数，方法用编号和细线组织验证，结论按条理展开。
- 一个Master统一背景与页脚，七个Layout的槽位或固定几何各不相同；复合图解使用object代理，文字使用文本槽。
- 短公式、图注和页码允许居中，其他正文从框左上方书写；主体区止于650px，页脚线660px。
- 插图为可替换的教学示例；曲线、数学文本可编辑，但不是可自动计算的统计图或公式对象。

## V. Page Roster
| SVG | Layout / picker | Slot frames |
|---|---|---|
| `01_cover.svg` | academic-formal-cover / 课程封面 | eyebrow: 64 60 1000 38; title: 64 209 690 184; subtitle: 64 428 690 108; author: 64 585 690 44; cover-visual: 860 225 336 274; caption: 840 575 376 68; course-footer: 84 673 970 34; slide-number: 1140 673 76 34 |
| `02a_content_concept.svg` | academic-formal-concept / 概念与公式 | page-title: 64 87 1152 70; formula: 96 226 1088 74; param-1: 64 382 348 57; explain-1: 64 463 348 146; param-2: 460 382 348 57; explain-2: 460 463 348 146; param-3: 856 382 348 57; explain-3: 856 463 348 146; course-footer: 84 673 970 34; slide-number: 1140 673 76 34 |
| `02b_content_image_text.svg` | academic-formal-image-text / 图文讲解 | page-title: 64 87 1152 70; teaching-visual: 64 227 542 350; observe-title-1: 736 224 480 47; observe-body-1: 680 287 536 51; observe-title-2: 736 350 480 47; observe-body-2: 680 413 536 51; observe-title-3: 736 476 480 47; observe-body-3: 680 539 536 51; figure-caption: 64 605 1152 42; course-footer: 84 673 970 34; slide-number: 1140 673 76 34 |
| `02c_content_compare.svg` | academic-formal-compare / 双栏对比 | page-title: 64 87 1152 70; left-label: 64 213 544 54; right-label: 674 213 542 54; left-visual: 96 290 464 218; right-visual: 706 290 464 218; left-description: 64 535 544 49; right-description: 674 535 542 49; conclusion: 82 602 1116 42; course-footer: 84 673 970 34; slide-number: 1140 673 76 34 |
| `02d_content_process.svg` | academic-formal-process / 方法与流程 | page-title: 64 87 1152 70; intro: 64 201 1152 54; step-title-1: 64 384 352 54; step-body-1: 64 458 352 144; step-title-2: 460 384 352 54; step-body-2: 460 458 352 144; step-title-3: 856 384 352 54; step-body-3: 856 458 352 144; hint: 64 610 1152 40; course-footer: 84 673 970 34; slide-number: 1140 673 76 34 |
| `02e_content_practice.svg` | academic-formal-practice / 课堂练习 | page-title: 64 87 1152 70; question: 64 204 1152 105; task-1: 64 360 788 58; task-2: 64 442 788 58; task-3: 64 524 788 58; hint-title: 922 360 294 48; hint-body: 922 424 294 156; practice-footer: 64 609 1152 40; course-footer: 84 673 970 34; slide-number: 1140 673 76 34 |
| `03_ending.svg` | academic-formal-summary / 回顾与延伸 | page-title: 64 87 1152 70; summary-lead: 64 222 1152 84; takeaway-title-1: 130 343 265 50; takeaway-detail-1: 421 343 795 50; takeaway-title-2: 130 432 265 50; takeaway-detail-2: 421 432 795 50; takeaway-title-3: 130 521 265 50; takeaway-detail-3: 421 521 795 50; ending-question: 64 609 1152 40; course-footer: 84 673 970 34; slide-number: 1140 673 76 34 |

## VII. Placeholder Overrides
- frontmatter按basename声明语义标记，逐行解释与图注对应sample_content的键。
