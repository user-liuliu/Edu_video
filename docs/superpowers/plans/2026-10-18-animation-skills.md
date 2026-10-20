# Existing Animation Skills Runtime Integration Plan

> Execute inline with executing-plans; use TDD and verification-before-completion.

**Goal:** Vendor selected existing MIT upstream skills and feed relevant guidance to the real scene-generation request, without extra model calls.
**Architecture:** Preserve original sources at pinned commits with SHA256 provenance. A local allowlisted loader selects common/SVG guidance plus science-diagram or story-character guidance, bounded in size. A system adapter preserves the Scene contract and narration clock; extend deterministic playback only where needed for draw-on and natural easing. Include skill digest in visual cache keys; preserve audio caching.
**Spec:** User-approved existing upstream skills, same models, no new video-stage AI review or planning call. HTML-preview-first remains separately tracked in 2026-10-18-html-preview.md.
**Tech Stack:** Python, JSON, existing SVG runtime, pytest, Chromium.

## Global Constraints
Install inside backend application (not global Codex); retain upstream files and licenses unchanged; do not execute downloaded scripts or fetch remote content during generation. Do not change outline review or introduce new calls. Existing dirty phase-three work remains intact. No production-data tests; no interruption of active jobs.

## Review Focus
Path traversal and modified assets; irrelevant skill selection; deterministic seek including backwards; cache invalidation must not regenerate audio; conflicting upstream storyboard/audio/QC instructions must be overridden.

### Task 1: Vendor and load
- [x] Pin and install four selected upstream directories, required references and licenses; record hashes.
- [x] Write failing loader/routing/integrity tests; implement bounded allowlisted loader and adapter.
- [x] Verify source and license hashes and test failure cases.

### Task 2: Wire real generation and playback
- [x] Write failing request-boundary test for actual skill instructions and narration timestamps, no extra call.
- [x] Inject skill guidance into build_scene and version visual cache fingerprint.
- [x] Add deterministic draw-progress and easing support with invalid-input tests and real browser seek checks.

### Task 3: Verify and record
- [x] Backend suite, renderer checks, build packaging verification and isolated real-model science/story samples where available.
- [x] Review diff; document installed paths, tests and limits. Deploy only after verification and checking production tasks.

## Final verification (2026-10-18)

- Four pinned upstream MIT skills, 21 unchanged upstream Markdown/license files; actual model requests contain original relevant excerpts.
- Routing regression RED: 3 failures; corrected unclassified-subject fallback. Skill tests GREEN: 19 passed. Complete backend: 410 passed in 118.68s. Chromium runtime: 18 passed in 15.539s.
- Real existing-model samples: science 9.1s and story 11.3s, each one scene-generation request with selected skills; geometry/export/full decode passed. This is no comparative quality or performance guarantee.
- Backend/renderer candidate source hashes match all 43 video-module files. Independent review found one Important routing issue (fixed) and one Minor compound-path usage documentation suggestion (deferred).
- Deployment: two zero-active-task checks; retained old image tags and 986186-byte database backup, validated archive index; deployed candidates to backend/worker/scheduler/renderer. Health, worker ping, renderer connection, 0005 migration, schema consistency and running bundle digest verified. Formal renderer produced 9.1s/271094-byte MP4, full decode passed.
- Existing branch/dirty work preserved, no commit, push or merge. HTML-preview-first migration remains pending in its separate plan; this release does not remove legacy video planning/review calls.
