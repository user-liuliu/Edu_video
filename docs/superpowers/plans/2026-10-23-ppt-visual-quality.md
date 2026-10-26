# PPT visual quality implementation plan
> Required execution: executing-plans inline; approved direction from user.
Goal: automatic rendered-page review and richer mixed graphics with editable labels.
Architecture: canonical pages -> native deck -> isolated LO PDF/PNG -> vision review -> bounded page repair; JSON graphics -> offline browser renderer -> PNG+native labels.
Tech stack: existing Python/FastAPI/Postgres/Vue, LibreOffice/PyMuPDF, isolated Playwright/AntV.
Spec: ../specs/2026-10-23-ppt-visual-quality.md
Constraints: work in existing isolated codex/ppt-generation-dev; video pipeline unchanged; no production deploy; no paid calls; max two repairs; preserve unselected pages; strict data contracts and no model executable markup.
Review focus: rejected/malformed vision output must not pass; final PPTX render differs from SVG; retry cap and provider failure; cross-project graphic assets; resumed jobs must not accept an unreviewed replacement.

## Task 1: Rendered-page review and repair
Files: new quality.py; generation.py; router.py; tests/test_ppt_quality.py, tests/test_ppt_workflow.py.
Interface: render_review_images(pptx,count)->PNG bytes list; parse_review(data)->bounded issues; audit_pages(pages,...,review,repair,render,progress)->pages/warnings.
- [x] RED tests for final-page images and strict review parse, cap two repairs, selected-page isolation and failure preservation.
- [x] Implement isolated LO render, vision JSON review, bounded orchestration, checkpoints, config checks and page metadata.
- [x] GREEN targeted tests and actual native-deck render.

## Task 2: Offline trusted information graphics
Files: renderer/ppt_graphics.py, renderer/ppt_worker.py, renderer/app.py, vendor AntV; presentations/graphics.py; generation/master_assets/master_runtime; tests.
Interface: GraphicSpec bounded JSON -> PNG plus label geometry; attach source/digest per-page and resolve on read.
- [x] RED validation/path injection and generated asset roundtrip tests.
- [x] Implement pinned package, trusted HTML, offline browser screenshot and native label conversion; introduce graphic generation for process/compare.
- [x] GREEN real browser render and editable PPTX image/text export.

## Task 3: Status UI and verification
Files: frontend PPT types/preview and flow test; runtime docs and example.
- [x] RED tests for passed/needs_attention status and actionable issues in existing preview.
- [x] Implement status display; build improved information-graphic sample and render inspect.
- [x] Full backend/frontend tests and build, fresh independent review, justified fix pass, commit feature branch.

Integration follow-up: user explicitly requested deployment into the current software. See ../../2026-10-23-ppt-integration.md for real service verification and preserved-data evidence.

## Quality publication gate follow-up
User requires internal review and automatic repair before preview. The previous warning-only publication after two failed repairs is superseded.
- Keep bounded two-repair audit; persist checkpoints, but fail the job if any selected page remains unapproved.
- Require current-content approval for the whole result before publishing; retain the previous deck on failure.
- Block preview/export for previously published failed or pending review data; hide their images/download in the existing third step.
- Fix deterministic Chinese line wrapping, clipped experiment reaction zones and meaningless comparison decoration. Version graphics while retaining legacy rendering.
- Verify backend suite, frontend suite/build, actual graphic rasterization and retry the real five-page example.
