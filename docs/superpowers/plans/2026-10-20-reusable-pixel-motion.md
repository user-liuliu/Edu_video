# Reusable Pixel Motion Implementation Plan

**Goal:** Use licensed sprite assets and reusable deterministic motion helpers in normal story-video generation, eliminating emote cycling and disconnected object movement.

**Architecture:** Keep the complete model-authored HTML pipeline. Provide a compact semantic asset catalog and a program-owned EduSprites helper; embed only selected pinned PNG sheets into generated HTML. Drive movement, poses, anchors and transfers from absolute time so preview, seeking and export agree. No additional AI review, TTS model, engine install, or teacher approval page.

**Scope authorized:** User requested that the sample motion improvements work generally when generating videos in the program. Existing thread approves the asset-library route; implement in this workspace without reset, push or unrelated changes.

## Tasks

- [x] Add failing Python packaging/integration tests and real JavaScript motion tests: independent poses must not cycle; walking spans joined paths without internal stops; hand anchors follow scale/direction/frame; transfers remain continuous and seekable.
- [x] Vendor only required LPC assets and upstream attribution with hashes. Add sprite_assets.py and sprite_motion.js. Expose role-neutral variants, eight-frame walking and named static poses; document limits without treating unsupported actions as a generation error.
- [x] Route character/pixel stories to the catalog respecting explicit style overrides. Let the model choose scene composition and use the helper. Expand assets from a reserved marker after model output; add preload readiness to the existing sandbox bridge; include runtime and assets in compiler identity.
- [x] Run focused tests, production pipeline tests, JavaScript motion checks and full backend suite against the test database. Exercise missing/corrupt resources, no-network playback, repairs, scientific content without sprites and teacher style overrides.
- [x] Generate a fresh short story using the actual production helpers with system speech only. Inspect motion visually, check deterministic seeking and export, then update affected application containers only after verification. Preserve existing ports and services.

## Review Focus

- A base atlas can contain unrelated poses; the runtime must not infer these are an animation cycle.
- A multi-waypoint path must have one continuous distance clock; turn direction must not alternate at diagonal ties.
- Images must be decoded before readiness, including export screenshots and reverse seek.
- Existing non-sprite HTML must work, and teacher-requested non-pixel/science styles must not receive forced sprites.
- Files are trusted local pinned assets, never model-selected filesystem paths or remote URLs; embedded payload stays within limits and carries attribution.

## Progress

Five new Python tests initially failed on missing implementation, and Node failed on missing runtime. First focused pass: 59 Python tests and real Node path/contact checks passed. Offline Chrome decoded all assets and rendered eight frames with identical reverse seeking, zero network requests and no runtime errors. Extra corrupt PNG, repair and non-sprite regressions were added. Docker images built. Full suite is now running in a separate test-database container; Windows full-suite environment had a pytest internal failure and is not counted as passing. Actual configured writer is generating a fresh source using production html_generation_request and generate_html, with the identical existing offline system narration for comparison. No hand-edited model animation.

## Completed Verification

- Separate test database, full backend release suite: 419 passed, 1 skipped (Node unavailable in Python test image), 273.21 seconds. Skipped atlas-contact test passed on Windows with Node; latest local sprite tests: 10 passed, 1.83 seconds. Node motion checks passed. First and second whole-suite runs passed 418 and 419 tests before the extra atlas-contact check.
- Independent reviewer found repair-context base64 bloat, short style override gaps, lateral pose contact error, lost MP4 attribution and opaque grass mismatch; each addressed with focused regression/real atlas verification. All 108 pose contact samples touch opaque atlas pixels. Source pin and complete OGA-BY license retained.
- Actual configured writer sample: production html_generation_request plus generate_html, 176.09 seconds; model source not manually edited. Library packaged by production code, audio is identical existing offline system speech with zero TTS model calls.
- Real browser checks: offline decoded assets, eight motion frames with reverse-seek pixel equality, generated whole-film preview seeks with no errors. Prefab environment objects replace exposed construction atlases; grass/water backgrounds removed to avoid rectangular patches. Rendered contact-sheet inspected.
- Actual production rendering functions validate the new source and export 1280x720, 22.933333 second MP4; final export 64.86 seconds. MP4 retains asset copyright and license metadata, verified by ffprobe. Playback, pause, speed, HTML switch, media 206 ranges and mobile layout passed with zero browser errors.
- Updated only backend, renderer, worker and scheduler containers. Deployed backend/worker/renderer compile digest agrees: 9d5795872c6754dd8c4c047baac6dba0d67d8e156100379cb3e9fc843f58af29. Frontend still 8080; MinIO/Postgres/Redis unchanged. API health reports status ok and db true. Sample viewer opened on 4196.
- Evidence: .superpowers/sdd/2026-10-20-reusable-motion/{backend-tests-release.log,generation.json,render-release.log,motion-browser-result.json,viewer-check.json,mp4-attribution.json,deploy.log}. No Git commit or push requested or performed.

## Limits

This improves reusable rendering/motion and contact conventions rather than guaranteeing every model-authored complex performance. Library has three adult palette variants, not a complete child/historical costume collection. Model still chooses semantic staging; no extra AI video review or story-specific hand editing was added. Already-frozen prior videos retain old HTML; generate a new preview to use this runtime.
