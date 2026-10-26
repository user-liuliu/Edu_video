# Natural narration implementation plan

> **For agentic workers:** Use executing-plans to implement this plan in the current session. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the user-approved continuous narration experiment to normal video generation so adjacent complete short paragraphs share one TTS request.

**Architecture:** Keep semantic VideoSegments, scene modules, existing per-segment audio fingerprints, playback and export contracts. Group only consecutive uncached complete paragraphs with the same speaking instruction (maximum 300 characters and 3 paragraphs). Use existing chapter title prefixes to reserve space for adjacent paragraphs of the same chapter when a length limit would otherwise split them. Split returned PCM only at subtitle-confirmed inter-sentence pauses on the 30 fps frame grid. A bounded fallback uses separate requests when subtitle boundaries are unsuitable. Store group audio/subtitles before distributing individual audio assets so recovery can reuse the successful synthesis.

**Tech Stack:** Existing Python backend, SQLAlchemy, WAV/PCM, existing TTS adapter, isolated PostgreSQL tests and Docker Compose.

**Approved scope:** The user approved continuous synthesis after listening to the trial. Correcting terminology remains unresolved and is not part of this change. Existing video versions remain available. Existing credits, subtitles, visual-only edits and selected voice-edit boundaries must hold. No new model dependency, no frontend controls, no real paid generation in automated tests.

## Task 1: Safe grouping and lossless splitting

- [x] Add tests in `backend/tests/test_continuous_speech.py` for grouping bounds, cached/instruction/fragment boundaries, PCM preservation, subtitle offsets and refusal to cut through spoken text.
- [x] Observe RED, then add `backend/app/videos/continuous_speech.py`: `plan_blocks(texts, instructions, reusable, enabled=True, force_single=())`, `split_narration(narration, texts)` and a dedicated `UnsplittableNarration` error.
- [x] Verify joined split audio exactly retains the original PCM, with only existing frame-alignment tail padding, and each chunk's captions match its original paragraph.

## Task 2: Integrate synthesis, checkpoints and selected edits

- [x] Add real pipeline integration regressions for one grouped call, unsafe subtitles falling back once, no cached/unselected audio regeneration, grouped resume after interrupted publication, and one credit settlement.
- [x] Observe RED and integrate grouping into `backend/app/videos/direct_pipeline.py`. Save group assets in version-owned checkpoints before publishing per-segment audio. Reuse matching checkpoints across task continuation and retry-version lineage.
- [x] Document the behavior and limitations; run focused and complete backend tests. Run a fresh review and fix important findings.
- [x] Build backend, check active production jobs, deploy backend/worker/scheduler when idle, and verify source hashes, HTTP health and worker ping. Remove any temporary test containers left by these checks.

## Final verification

- Initial focused suite: 86 passed. Review-fix focused suite: 92 passed. Final grouping and pipeline suite: 30 passed.
- Complete final backend suite: 920 passed, 3 skipped in 800.79 seconds. Earlier interrupted runs are not counted as passing verification.
- Real accepted 51.9-second audio splits with identical PCM and caption text. The original project's quadratic-function paragraphs are grouped in the same request by the final chapter-aware planner.
- Deployed backend, worker and scheduler source hashes match the verified workspace. Website and API health return 200; worker ping returns pong.
- Existing video version count, duration, source audio checksum and object size remain unchanged; its preview runtime remains compatible. Final Docker inventory contains only the 9 production containers; test containers used auto-removal.
- Verification did not make new speech-provider requests or create paid project jobs. Pronunciation remains outside the achieved result.

## Review focus

- Cached audio and unselected voice-edit segments are hard boundaries; no unnecessary paid work.
- Subtitle normalization must use the current punctuation/whitespace contract and fail closed on mismatches, overlaps, or boundaries inside a caption.
- Chunk WAVs must align to 30 fps without adding silence at internal boundaries or dropping/duplicating PCM samples.
- Persist group checkpoints before distribution; resume and retry must not repeat a successful grouped provider call.
- Service failures and lost leases must not trigger fallback generation outside the existing job/retry/credit guards.
