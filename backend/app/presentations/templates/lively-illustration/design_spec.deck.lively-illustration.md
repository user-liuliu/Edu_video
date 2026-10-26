---
deck_id: lively-illustration
kind: deck
category: scenario
summary: 以生活情境与图像探究组织课堂讲授、练习和复习
keywords:
- 教学
- 插画
- 情境
primary_color: '#B84A26'
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
  - '{{CAPTION}}'
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
  - '{{FIGURE_CAPTION}}'
  - '{{OBS_TITLE_1}}'
  - '{{OBS_BODY_1}}'
  - '{{OBS_TITLE_2}}'
  - '{{OBS_BODY_2}}'
  - '{{OBS_TITLE_3}}'
  - '{{OBS_BODY_3}}'
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

# 活泼插画 · 橙光 — Design Specification

## I. Template Overview
- 课件家族：以生活情境与图像探究组织课堂讲授、练习和复习。面向教师课堂投影与课后复习，示例为初三数学“二次函数”。
- 代表角色包括情境封面、概念公式、图像解释、性质比较、方法步骤、课堂练习和总结延伸；不限定未来课件页数和顺序。
- 配色、字体与版式为本轮设计师选择，用户已授权生成两套项目级模板供审阅。未提供机构标志，不加入虚构品牌。

## II. Color Scheme
| Role | HEX |
|---|---|
| bg | #FFF9ED |
| title | #243C36 |
| body | #344841 |
| accent | #B84A26 |
| secondary | #23756A |
| muted | #63736C |
| surface | #F9E6CE |
| surface2 | #E0EEE6 |
| rule | #D5DED5 |
| white | #FFFFFF |

## III. Typography
- 中文Microsoft YaHei，西文与数学记号Arial；封面64px，页标题44px，正文28–32px，图注22px，页脚18px；步骤标题32px，提示与延伸25px。

## IV. Signature Design Elements
- 奶油底、橙色重点和青绿图线；圆角场景承载生活插图与公式。封面的可编辑篮球和抛物线建立生活情境，图文页左图右解释。
- 圆编号连接探究任务，方法页连续线表达顺序；右侧青绿提示区承接练习，课堂小结使用共同背景联结结论。
- 一个Master统一背景与页脚，七个Layout的槽位或固定几何各不相同；复合图解使用object代理，文字使用文本槽。
- 短公式、图注和页码允许居中，其他正文从框左上方书写；主体区止于650px，页脚线660px。
- 插图为可替换的教学示例；曲线、数学文本可编辑，但不是可自动计算的统计图或公式对象。

## V. Page Roster
| SVG | Layout / picker | Slot frames |
|---|---|---|
| `01_cover.svg` | lively-illustration-cover / 课程封面 | eyebrow: 64 108 620 44; title: 64 204 620 180; subtitle: 64 419 620 108; author: 64 571 620 46; cover-visual: 732 196 456 344; caption: 744 564 434 46; course-footer: 84 673 970 34; slide-number: 1140 673 76 34 |
| `02a_content_concept.svg` | lively-illustration-concept / 概念与公式 | page-title: 64 94 1152 70; formula: 104 218 1072 74; param-1: 120 337 298 55; explain-1: 82 420 338 160; param-2: 516 337 298 55; explain-2: 478 420 338 160; param-3: 912 337 298 55; explain-3: 874 420 338 160; course-footer: 84 673 970 34; slide-number: 1140 673 76 34 |
| `02b_content_image_text.svg` | lively-illustration-image-text / 图文讲解 | page-title: 64 94 1152 70; teaching-visual: 86 228 490 322; figure-caption: 82 605 1116 42; observe-title-1: 686 202 530 48; observe-body-1: 686 263 530 52; observe-title-2: 686 338 530 48; observe-body-2: 686 399 530 52; observe-title-3: 686 474 530 48; observe-body-3: 686 535 530 52; course-footer: 84 673 970 34; slide-number: 1140 673 76 34 |
| `02c_content_compare.svg` | lively-illustration-compare / 双栏对比 | page-title: 64 94 1152 70; left-label: 92 218 496 52; right-label: 692 218 496 52; left-visual: 106 280 468 208; right-visual: 706 280 468 208; left-description: 90 504 500 48; right-description: 690 504 500 48; conclusion: 84 592 1112 55; course-footer: 84 673 970 34; slide-number: 1140 673 76 34 |
| `02d_content_process.svg` | lively-illustration-process / 方法与流程 | page-title: 64 94 1152 70; intro: 64 188 1152 54; step-title-1: 64 373 352 55; step-body-1: 64 447 352 145; step-title-2: 460 373 352 55; step-body-2: 460 447 352 145; step-title-3: 856 373 352 55; step-body-3: 856 447 352 145; hint: 64 602 1152 42; course-footer: 84 673 970 34; slide-number: 1140 673 76 34 |
| `02e_content_practice.svg` | lively-illustration-practice / 课堂练习 | page-title: 64 94 1152 70; question: 90 205 1100 100; task-1: 64 346 804 58; task-2: 64 426 804 58; task-3: 64 506 804 58; hint-title: 924 351 264 48; hint-body: 924 414 264 155; practice-footer: 64 600 1152 42; course-footer: 84 673 970 34; slide-number: 1140 673 76 34 |
| `03_ending.svg` | lively-illustration-summary / 回顾与延伸 | page-title: 64 94 1152 70; summary-lead: 92 223 1096 68; takeaway-title-1: 132 332 252 49; takeaway-detail-1: 420 332 796 49; takeaway-title-2: 132 420 252 49; takeaway-detail-2: 420 420 796 49; takeaway-title-3: 132 508 252 49; takeaway-detail-3: 420 508 796 49; ending-question: 64 605 1152 43; course-footer: 84 673 970 34; slide-number: 1140 673 76 34 |

## VII. Placeholder Overrides
- frontmatter按basename声明语义标记，逐行解释与图注对应sample_content的键。
