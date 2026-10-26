# PPT Outline Confirmation Implementation Plan

> Execute inline using executing-plans and test-driven-development.

**Goal:** Separate confirming the saved PPT outline from starting page generation, matching the approved interactive sample.
**Architecture:** Add revision-checked POST /api/presentations/{id}/confirm that persists confirmed_revision without adding a job. Require that revision for render jobs. Use existing outline/preview views and preserve editing, reviews, retry, partial delivery and export.
**Tech Stack:** FastAPI, SQLAlchemy/PostgreSQL, Vue, Element Plus, pytest, Vitest.
**Spec:** User-approved sample ppt-outline-confirmation.html and current chat: outline saves/checks/confirms; preview explicitly starts generation.

## Constraints
- Keep existing product shell and PPT editing controls. No new dependencies or database migration.
- Confirmation requires an owned, idle, saved, reviewed outline at the exact current revision. No model calls or generation jobs during confirmation.
- Edits invalidate prior confirmation using existing invalidation. Preserve previously generated decks and retries.
- Work against current uncommitted integrated feature state; snapshot touched files; do not commit or revert unrelated work. User asked to apply this version in the shared workspace.

## Review Focus
- Cancelling confirmation leaves outline editable and submits no job.
- Stale revisions, other owners, active jobs and edited review content reject confirmation.
- Direct preview without confirmation cannot start generation.
- Existing confirmed decks, retry and partial delivery remain available.
- Missing vision model must block generation but must not block independent confirmation.

### Task 1: Backend confirmation boundary
Files: backend/app/presentations/{schemas,router}.py; backend/tests/test_ppt_confirmation.py.
Interface: POST /{id}/confirm with {revision:int}; returns project view. Render rejects unconfirmed current revision.
- [x] Write tests for no job creation/model call, repeated confirm, stale/invalid/missing review, ownership, busy, editing invalidation and explicit render start.
- [x] Run tests RED, implement boundary, run tests GREEN.

### Task 2: Frontend explicit steps
Files: frontend/src/api/presentations.ts; views/workbench/Ppt{Outline,Preview}View.vue; components/workbench/CreationSteps.vue; tests/ppt-flow.spec.ts.
- [x] Add tests RED for confirmation dialog/cancel, confirm-only navigation, failure retention, preview gating, refresh and explicit start.
- [x] Replace combined action with confirm API and modal. Keep Save + knowledge checks; show enter-preview for confirmed outline.
- [x] Add initial confirmed preview state with Start generation, direct access guard; preserve existing retry and completed-deck behavior.
- [x] Run frontend tests and build GREEN.

### Task 3: Verification and local deployment
- [x] Run all frontend and backend tests; report any failures.
- [x] Review changes against scope and add missing coverage if found.
- [x] Update docs, build backend/frontend and deploy local services without interrupting active jobs.
- [x] Verify real browser and save screenshot.

