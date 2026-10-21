# Animation first sample implementation plan
> **For agentic workers:** Use superpowers:executing-plans inline, with one fresh final review.
**Goal:** Produce two representative two-minute samples through production functions used for new previews.
**Architecture:** New snapshot timing protocol selects estimated sentence cues -> Scene draft -> real narration -> deterministic piecewise time mapping. Persist draft/cues before speech. Carry adjacent verified Scene references, separate from same-scene revision. Preserve frozen previews and unselected revision assets.
**Tech Stack:** Existing Python/Pydantic/SQLAlchemy, HTML/SVG runtime, configured writer and TTS, isolated renderer and MinIO.
**Spec:** `.superpowers/sdd/2026-10-19-animation-first-samples/scope.md` and approved chat.
## Global Constraints
- No video AI audit or separate director planning call; approved whole-film expression pass is required; no arbitrary generated HTML/JS execution.
- No manual sample scene/audio edits, time stretching or filler to hit duration.
- Keep old sealed resources, compiler/runtime, local revision selection and audio reuse.
- No production deployment, push or commit in this task.
## Review Focus
- Provider sentence splitting differs: map exact normalized transcript, fail on changed content.
- Gaps and nonuniform speech: monotonic mapping, keyframes/actions/camera all retimed.
- Revisions: selected only, same-segment old reference separate from left/right references.
- Failure after Scene draft: reuse checkpoint without repeating accepted generation.
- Samples: ordinary API outline generation/review/confirmation, preview and export; exact sealed bytes.
### Task 1: Deterministic timing
- [x] RED: Test estimated cues, nonuniform sentence timing, all Scene time fields, gaps/mismatched transcript.
- [x] GREEN: Implement estimated_cues and whole-animation playback clock mapping. Preserve the frozen legacy runtime for no-clock scenes.
- [x] Run timing tests and regression.
### Task 2: Production animation-first preview
- [x] RED: Test order/sealed output, adjacent references, retry checkpoints, unselected revision reuse.
- [x] GREEN: Mark new snapshots, persist draft/cues, generate speech, retime/validate/compile. Prompts distinguish estimated/actual timing and reference meanings.
- [x] Run backend and runtime tests, inspect scoped source changes.
### Task 3: Real two-minute samples
- [x] Isolated DB/bucket, production ASGI routes, real configured providers, exact renderer. Request two minutes via teacher prompt.
- [x] Save outlines/inputs/events/hashes and exact MP4. Export zero model calls.
- [x] Decode entire MP4, verify durations, inspect joins and speech signal metrics; report subjective limits. No sample-only repair.
- [x] Fresh review, fix important findings, rerun checks. Provide samples; production unchanged.

## Approved route update (2026-10-19)
- [x] Freeze a whole-film final script + visual generation prompt using the configured writer. Preserve approved knowledge, formulas, conditions and story meaning. Maintain source section/segment mapping. No teacher intermediate approval.
- [x] Persist before animation and reuse on retry or local revision. Animation first with estimated sentence windows, then real TTS and automatic retiming. No video AI audit.
- [x] Visual revisions preserve narration/audio and unselected resources; voice-only revisions preserve frozen visual design and automatically retime. Knowledge changes return to outline review.
- [x] Production-path integration tests, backend/frontend/runtime regressions, fresh review, actual samples and export integrity checks. No commit, push or deployment.

Review focus additions: adjacent real captions without silence; trailing whitespace; long model calls and lease renewal; retries after script freeze; local revisions must not replace final script with source outline text.
