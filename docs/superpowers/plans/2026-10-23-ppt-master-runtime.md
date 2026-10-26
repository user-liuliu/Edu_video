# PPT Master runtime implementation plan
Spec: ../specs/2026-10-23-ppt-master-runtime.md
Goal: real illustrated editable PPTX using the official runtime.
Architecture: bounded validated model plans/SVG -> private workspace -> official canonical checks/finalize/export -> canonical SVG pages -> fenced publication; deterministic export on demand.
Stack: Python/FastAPI/Celery/Postgres/MinIO, official ppt-master Python tools.
Constraints: isolated codex/ppt-generation-dev worktree; video unchanged; accepted UI unchanged; fixed16:9; no model-authored executable code; package attribution intact.
Review focus: SVG input security, exact selected IDs, image ownership/digest, lease/revision publication, true native editable export.

- [x] Task1: tests RED for safe SVG/real diagrams/exact plans, package unmodified official toolchain, implement guarded bounded runtime and design artifacts, actual exporter integration test GREEN. Produces: validated SVG/plan and compiled deck/previews.
- [x] Task2: tests RED for reference image retention and orchestrated role prompts, implement Strategist/Executor generation/checkpoints with selected-page preservation. Consumes runtime; produces canonical SVG and per-page metadata.
- [x] Task3: tests RED for artifact publication/invalidation/owner access/cleanup, retain existing schema, integrate canonical SVG preview and pinned runtime export, prove failed/stale jobs cannot publish.
- [x] Task4: run targeted backend + frontend checks, create and render illustrated biology sample, inspect all pages, final fresh-context review and one justified fix pass, commit.

5 boundary cases: malicious SVG/external image; model omits selected ID; missing/broken photo; render retry/stale lease; outline changed after generation.

Completion evidence (2026-10-23): backend full 625 passed / 3 skipped; frontend 24 files / 220 tests, production build passed. Independent review findings fixed and targeted 40 passed. Seven-page official native export rendered via LibreOffice; auto-fit line break regression corrected in generated XML. Biology sample source is backend/examples/ppt_master_biology.py. No production deployment or paid-model quality claim.
