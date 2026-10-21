# New Cast Integration

User scope: read the 素材库 chat and use its replacement original cast for narrative stories. Missing characters use the nearest available character. Formula, function graph and experiment visuals remain clear native graphics.

Keep the existing uncommitted shared workspace and installed assets. No model speech calls, project deletion, git reset or unrelated UI edits.

- [x] Add failing regressions for absent characters, story/science/mixed routing and real sprite use.
- [x] Route narrative requests to the new catalog, make nearest-character selection deterministic and preserve age before clothing when approximating.
- [x] Require actual character drawing during existing offline playback checks; use existing bounded code repair, without adding AI content review.
- [x] Verify Python/Node behavior, offline playback and MP4 export; review only this change.
- [x] Update runtime services after successful checks and verify matching asset/runtime digests and health.

Verification risks: old frozen previews retain their own runtime; missing role or ancient child must not fall back to adult geometry; mixed scientific stories retain vector diagrams; a library injected but never called must fail runtime checks; catalog-only previews are not story generation.

## Verified 2026-10-20

- Read the 素材库 thread 01a157c0-04f7-7c62-a360-8239d6b2cc93 and confirmed the actual replacement manifest: original-cast-1, 20 characters.
- Added RED/GREEN cases for missing roles, named stories without literal story keywords, scientific exceptions, explicit teacher styles and detached/offscreen drawing.
- Windows focused Python: 68 passed. Node motion, original cast actions, contacts and reverse seeking passed.
- Full isolated backend regression: 436 passed, 3 skipped (282.57 seconds); no production test data mutations.
- Existing real writer produced the 孔融让梨 HTML using boy_blue/boy_sage/student_m/scholar; generated scene code was not edited. Offline system speech only, zero speech-provider calls. Preview validation and 1280x720 MP4 export passed (18.166667 seconds).
- Mixed story/native parabola smoke passed: nearest child and elder roles, deterministic reverse seek, actual MP4 export. Unused required sprites rejected by the existing technical validation/repair route.
- Read-only review found two Important gaps (named-story routing and detached/offscreen usage), both fixed and covered before deployment.
- Verified no pending/running database generation jobs and no active/reserved/scheduled Celery tasks before recreating backend, renderer, worker and scheduler. Frontend/data services and ports retained.
- All four deployed containers have asset digest 22d384eaabe92ab612314f711423eda91fec111c60340d76b626b1bdcf44e84f and runtime digest f7d8f0560f4ed8cfafa745b1ef17e5f6c4299b8884066ce919ede3dd2160a45d. API/DB and renderer health passed. Real deployed worker-to-renderer validate/render endpoints exported the model-authored sample successfully.
- Evidence: .superpowers/sdd/2026-10-20-new-cast/{focused-final.log,full-tests-final.log,runtime-result.json,actual-result.json,deployed-result.json}. The sprite-use counter is a minimum technical check, not an aesthetic or every-character guarantee. Existing frozen videos require a new generation to adopt the changed assets/policy.
