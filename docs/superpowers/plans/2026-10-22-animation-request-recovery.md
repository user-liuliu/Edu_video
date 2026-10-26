# Animation request recovery

Goal: reduce redundant frozen input and recover long HTML generation responses without changing narration, timestamps, shared visual definitions or local revision scope.

- [x] Add regressions for compact requests, slow 502 recovery, append validation and permanent errors.
- [x] Compact duplicate context, keeping unique approved facts and all sentence timing.
- [x] Keep default three transient retries; allow long whole-film failures to switch once to shared-first, ordered module generation. Never expand a local revision.
- [x] Validate complete mapping, joins and runtime; run isolated backend tests and build/deploy only verified affected services.
- [x] Verify runtime files and service health; report remaining upstream limitations honestly.

Verified 2026-10-23: full isolated backend run 600 passed/3 skipped; final reviewed recovery-focused Linux run 59 passed; offline Chromium/encoder regressions 23 passed. Independent review findings fixed and reproduced RED/GREEN. Deployed backend/worker/scheduler/renderer source hashes match; frozen renderer digest unchanged; frontend image preserved. Production-worker smoke simulates one slow 502, assembles the existing three-module quadratic sample without changes, validates the whole animation, and exports/decodes a 6-second 1280x720 MP4. No real provider calls or credit changes in smoke. Failed task reservations remain released. No guarantee of external provider availability; actual upstream 502 behavior requires a subsequent real generation attempt. Code-generation deadline is 900 seconds.
