# Animation checkpoints and bounded continuation implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Persist each validated animation module and resume interrupted video jobs without redrawing completed work or billing twice.
**Architecture:** Immutable MinIO shared/part objects with a guarded index in VideoVersion.snapshot; stable render keys and a canonical frozen-input fingerprint. Ordered module batches yield the same leased job back to the existing dispatcher, leaving its reservation and capacity identity intact.
**Tech Stack:** Python, SQLAlchemy async/Postgres JSONB, MinIO, Celery, pytest.
**Spec:** User-approved checkpoint/resume design in this conversation; captured below.

## Global constraints
- Preserve frozen approved content, timing, characters, shared code, and local revision scope.
- Only complete, validated responses become checkpoints; storage success precedes index advancement.
- A changed generation fingerprint starts fresh; a damaged part retains only the verified contiguous prefix.
- Stable segment keys survive retry-version UUID remapping; references remain owned by the same project.
- Normal continuation is neither failure nor success: same job, one capacity slot, reserved credits, no failure-attempt increment. Crashes still consume recovery attempts.
- Keep existing runtime digest and existing previews valid; no production model calls or deployment as part of verification.
- Preserve current work-in-progress in codex/ppt-generation-dev; no commits, pushes or merges requested.

## Review focus
- Crash after object put before index commit cannot advertise a missing or partial result.
- Stale lease and deleted/edited project cannot publish a checkpoint or yield a newer worker's job.
- Retry-version ID changes must not force regeneration, while actual content/model/prompt/runtime changes must.
- Corrupt middle checkpoint cannot mix a regenerated boundary with dependent old suffix.
- Intentional batching must not exhaust retry budget or settle/release credits; actual errors must release.

### Task 1: Ordered generation checkpoints
**Files:** backend/app/videos/film_modules.py; backend/tests/test_film_checkpoints.py.
**Interfaces:** generate_film(..., checkpoint=None, save_checkpoint=None, max_modules=None); FilmBatchPending(completed,total).
- [x] Add failing tests for interruption after module 2, resumption at module 3, immutable shared resources/timing, and bounded batches.
- [x] Run tests and verify expected RED.
- [x] Implement validated prefix resume and await a persistence hook after each complete module. Prefer ordered generation for long videos, retain short whole response path.
- [x] Run new tests and existing film/model-stream tests GREEN.

### Task 2: Guarded checkpoint objects and pipeline integration
**Files:** backend/app/videos/film_checkpoints.py (new); backend/app/videos/direct_pipeline.py; backend/tests/test_film_checkpoints.py; backend/tests/test_direct_pipeline.py.
**Interfaces:** checkpoint fingerprint/restore/save helpers; wrapper forwarding checkpoint options without changing the sealed HTML runtime source.
- [x] Add failing tests for UUID-stable fingerprint, corrupt-prefix recovery, upload failure/index atomicity and guarded writes.
- [x] Implement content-addressed shared/part object references, guarded snapshot index, persisted progress, and pipeline hooks.
- [x] Verify retry version inheritance, downstream audio/render reuse, project cleanup and full-source precedence.
- [x] Run focused tests GREEN.

### Task 3: Same-job bounded continuation
**Files:** backend/app/jobs/continuation.py (new); backend/app/jobs/tasks.py; backend/tests/test_video_continuation.py (new).
**Interfaces:** ContinueJob(stage); fenced transition running -> pending with lease/dispatched reset and failed-attempt neutral continuation.
- [x] Write RED tests for multiple batches with max_retries=0, same job/capacity/credit hold, duplicate dispatch, stale worker, crash recovery, and eventual single settlement.
- [x] Implement intentional continuation handling without entering failure handler or settlement.
- [x] Cover lease expiry and persisted checkpoint survival across reclaims.
- [x] Run focused tests GREEN.

### Task 4: Integrated verification and independent review
- [x] Run current video backend regression against a dedicated test database (never production tables); exclude concurrent unfinished test_ppt*.py development.
- [x] Run native renderer checks on shared runtime and resumed film; report test limits.
- [x] Obtain fresh read-only code review, fix substantive findings with RED/GREEN.
- [x] Run git diff --check, verify production container identities unchanged, document final regression evidence.
