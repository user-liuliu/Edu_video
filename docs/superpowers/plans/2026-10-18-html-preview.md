# HTML Preview First Implementation Plan

> **For agentic workers:** Use executing-plans to implement sequentially.

**Goal:** Produce narrated HTML previews before explicit MP4 export, without video-stage AI review.
**Architecture:** New snapshot workflow isolates existing legacy jobs. Preview preparation checkpoints final audio, captions, validated Scene and compiled HTML. Export consumes immutable assets with no provider calls.
**Tech Stack:** FastAPI, SQLAlchemy/Postgres, Celery, MinIO, Playwright, Vue/ElementPlus.
**Spec:** docs/superpowers/specs/2026-10-18-html-preview-design.md

## Global Constraints
Keep existing outline gates, models, ownership checks, task capacity and historical videos. Preserve uncommitted phase-three work. No new model or dependency. No production-data tests.

## Review Focus
- Audio/HTML readiness and private media isolation.
- Rapid seek/version change cannot revive old playback.
- Export retry never regenerates provider assets or alters preview.
- Newer preview failure leaves prior MP4 available.
- Model configuration changes after preview cannot prevent exact export.

### Task 1: Preview preparation and state
- [x] Add failing tests for default preview readiness, zero reviewer/planning calls, no early render, final audio and timeline checkpoints.
- [x] Implement preview pipeline and API state fields, retaining legacy-job path.
- [x] Run focused tests.

### Task 2: Explicit export and private preview resources
- [x] Add failing tests for export gates, capacity/idempotency, owner-only assets, failures preserving preview, unchanged bytes.
- [x] Implement export job, validate-only renderer and private HTML/audio access with bounded reads.
- [x] Run backend regression suite.

### Task 3: Narrated HTML player and UI
- [x] Add failing frontend tests for HTML readiness, explicit export and no automatic submission.
- [x] Implement audio-clock player, safe iframe messaging, seeking, errors, version selection and export labels.
- [x] Preserve existing styling and update task notifications.
- [x] Run frontend suite and production build.

### Task 4: End-to-end verification
- [x] Exercise runtime, short export, preview playback/seeking and asset identity in real browser.
- [x] Review full diff and run appropriate full regression suites.
- [x] Record results and provide trial entry; deploy only after verification and checking active production tasks.

## Verification record
- Backend: 428 passed; frontend: 171 passed / 18 files; runtime: 20 passed. Production build passed.
- Four Important review findings reproduced with failing tests and fixed. No review findings deferred.
- Real configured-model science/story previews and MP4 exports passed. Final 16.933s combined export reused sealed assets, no model calls, complete decode passed.
- Browser verified sandbox readiness, play/pause, seeking/cross-segment playback, segment selection, responsive width and explicit export.
- Deploy result and rollback/backup details: .superpowers/sdd/2026-10-18-html-preview/deployment-manifest.json.
