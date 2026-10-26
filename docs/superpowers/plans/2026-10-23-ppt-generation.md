# PPT generation implementation plan

Goal: deliver the approved independent PPT generation loop.
Architecture: FastAPI/Postgres outbox + separate Celery tasks, bounded template slots, SVG/PPTX rendering, Vue creation/outline/preview views.
Tech Stack: SQLAlchemy, Pydantic, python-pptx, existing JSON model client, Vue/Element Plus.
Spec: docs/superpowers/specs/2026-10-23-ppt-generation-design.md
Global Constraints: preserve dirty video work; no live provider calls; never use the video pipeline for PPT; use isolated worktree E:/AIdemo/edu-video-ppt on codex/ppt-generation-dev because the shared original workspace changed branches during development.
Review Focus: cross-owner access, stale publication, retries, references, text overflow, native full-deck export, unsaved outline handling.

## Task 1: Domain and renderer
Files: backend/app/presentations/{schemas,rendering}.py, templates/, backend/tests/test_ppt_rendering.py.
Test first: slot validation, selected-ID isolation, native shapes, entire slide count, 16:9, escaping and no sample data leakage. Implement bounded page schemas, locked template metadata and deterministic native/SVG rendering.

## Task 2: Independent persistence and HTTP API
Files: backend/app/presentations/{models,router,service}.py; migration 0008; main.py; jobs/service.py.
Test first: ownership, project CRUD, optimistic revision, upload limits and export gating. Implement standalone project/material/job models, locked mutations, outbox enqueue and authenticated preview/download. Include cross-flow concurrency.

## Task 3: Model orchestration and durable jobs
Files: backend/app/presentations/{generation,tasks}.py; jobs/celery_app.py; tests/test_ppt_workflow.py.
Test first: fixture model full workflow, selection only, stale worker discard, broker recovery and idempotency. Implement bounded references/search, two-phase outline/render, heartbeat, claim/publish lease checks and revisioned page history.

## Task 4: Shared layout and PPT UI
Files: frontend/src/api/presentations.ts, views/workbench/*Ppt*.vue; components/workbench/{CreationMode,CreationSteps,MaterialUpload}.vue; router; AppLayout; ProjectList.
Test first: mode switching retains drafts, PPT settings only style, outline edit/reorder/select rewrite, polling and complete-deck download. Implement on current layout with mobile reflow and accessible controls.

## Task 5: Integration and review
Run backend suite serially, frontend suite/build, migration checks, exported fixture rendering and desktop/mobile browser review. Request one fresh whole-feature code review using requesting-code-review skill, fix important findings with reproducing tests. Update README with operation/deployment contracts and limitations.


## Completion record (2026-10-23)
Tasks 1–4 implemented. Fresh whole-feature review completed; four important findings fixed with regression coverage: logout/unmount memory race, newly saved draft identity across mode switches, historical render reopening outline, and actionable persisted reference parsing failures. Task 5 validation includes backend full-suite baseline (590 passed, 3 skipped), final PPT/migration regression (16 passed), frontend tests/build, and eight desktop/mobile browser checks using fixture APIs. Final test counts are recorded in docs/ppt-generation.md and the development ledger after the last run.

Deployment was not performed. No live provider calls, video billing, web canvas editor or true illustration generation are included. The old HTML prototype remains separate.
