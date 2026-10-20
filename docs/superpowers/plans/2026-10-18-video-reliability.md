# Video Generation Reliability Implementation Plan

> **For agentic workers:** Use executing-plans inline. Reuse codex/phase3-video-pipeline and preserve existing uncommitted work.

**Goal:** Correct shared scene scope, camera/action and recovery contracts and validate complete science/story production paths.
**Architecture:** Preserve coherent approved teaching sections inside conservative narration bounds. Explicitly plan local visual scope for genuinely split and legacy segments. Add trusted camera and prop pickup primitives shared by generator, reviewer and geometry validation. Use bounded provider recovery and versioned dependent caches.
**Tech Stack:** Existing FastAPI/SQLAlchemy/Celery/MinIO, Vue, controlled Scene JSON, Chromium/FFmpeg.
**Spec:** docs/superpowers/specs/2026-10-18-phase-3-video-design.md and user request for shared reliability and full workflow validation.

## Global Constraints
- No approved narration/content deletion or audit bypass.
- Preserve old versions, private ownership, teacher capacity and checkpoint safety.
- No keys or raw provider responses in logs or artifacts.
- Isolated test DB only; never parallelize DB reset tests and business acceptance.
- Production deployment only after full tests and real complete video acceptance; do not commit/push without request.

## Review Focus
- Long and legacy-split narration must have explicit local visual scope and exact text preservation.
- Camera changes cannot trigger walking or move title/captions; geometry still enforced.
- Pickup and handoff must keep hands/props connected at boundaries and repeated seeks deterministic.
- Repairs must retain all accumulated content/layout requirements and correct cache dependencies.
- Provider timeout/429/5xx recovery bounded; authentication/content failures remain explicit.

### Task 1: Narrative scope and legacy recovery
- [x] Add failing tests for 181-char story, long balanced chunks, shared parent/local scope and legacy retries.
- [x] Implement conservative coherent chunking and validated per-child visual allocation for split groups.
- [x] Preserve exact narration, reviewed parent requirements and old successful clips.
- [x] Run targeted tests and record results.

### Task 2: Camera and object actions
- [x] Add failing schema and real-browser tests for unified camera push, stationary characters, pickup grip, seek determinism and safety.
- [x] Implement camera transform and pickup data primitives with matching model/review contracts.
- [x] Verify geometry under camera transformations, three aspect ratios and rendered MP4 decoding.

### Task 3: Recovery and checkpoints
- [x] Add failing tests for accumulated repair feedback, independent layout/content budgets, transient TTS failures and changed-rule caches.
- [x] Implement bounded recovery, safe diagnostics and separate audio/visual cache versions; retain authentication fail-fast.
- [x] Run complete backend, frontend and real-browser regression suites.

### Task 4: Full workflow acceptance and deployment
- [x] Run real configured models from requirements/reference upload through generated outline, review/save/confirm, full science/story MP4.
- [x] Run original complete Kong Rong approved outline through all segments and final assembly.
- [x] Verify preview playback, seek, private Range/download and failure/retry recovery; inspect frames/audio evidence.
- [x] Review all changes, record exact results/limits, then deploy only after green acceptance and idle jobs.

### Task 5: General expression freedom requested during acceptance
- [x] RED: general drawable props, character variation, implicit animation/static hold and entrance/camera cropping exercise the real builder/runtime/renderer.
- [x] Remove semantic action/component mandates and exact identity rejection; keep executable scene validation. Treat visual plan as identity guidance and storyboard presentation as replaceable, while retaining teaching/story meaning and explicit teacher intent.
- [x] Clip scene world below title/above captions; allow non-text entrances/cropping, retain finite geometry and teaching-text readability checks.
- [x] GREEN: pure regressions and real Edge runtime, then serial backend suite after existing acceptance cleanup. Rebuild isolated renderer and rerun actual models before production deployment.

## Final evidence
- Backend391 passed118.25s after real acceptance cleanup; frontend159/17files and production build pass; Edge runtime15; real export3; isolated renderer three-aspect matrix pass.
- Actual configured-model acceptance run b41c3f1197e94ec2b012a4323d635d18: fresh DOCX->outline/review/save/confirm->science3/50.866s and story3/42.833s; original complete Kong Rong7/274.1s. All private Range/download and real Edge playback/seek/modification-selection/download equality pass. Full MP4 decode and audio signal checks pass, subjective listening not established.
- Deployed8080 after two idle checks, database dump verification and old image tags. Exact candidate IDs verified;0005head/no drift/health/worker pong/renderer connection passed. Production browser preview empty state passed; no existing completed production video available for playback, so playback evidence comes from isolated complete acceptance.
- Evidence and rollback manifest: .superpowers/sdd/2026-10-18-video-reliability/. No commit/push/merge in this pass.

