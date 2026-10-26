# PPT practical review integration - 2026-10-24

Approved scope: existing input / outline / preview flow. Outline checks knowledge, formulas, calculations, exercise answers and necessary conditions only. Corrected text is shown before user confirmation. Editing invalidates exact-content approval.

PPT checks substantive correctness and basic usability. Visual refinement suggestions allow preview/export without automatic repair; real teaching, readability, export and service failures cannot be downgraded by model severity. Definitions, formulas and exercises may use text-only pages. Serious failures keep bounded automatic repair and one simplified rebuild; approved pages remain independently deliverable.

## Verification
- Feature branch backend: 685 passed, 3 skipped. Frontend: 238 passed; build exit 0.
- Runtime frontend, with existing shared loading animation retained: 244 passed; build exit 0.
- Integrated runtime backend PPT API/workflow/knowledge/quality/native-export regression: 82 passed; dedicated test database removed.
- Independent review fixes: restrict selected-page knowledge repair; allow title formula correction; never downgrade teaching errors to suggestions.
- Live model corrected x=b/(2a) to x=-b/(2a), and example x=2 to x=-2. Browser confirmed before/after correction, then started generation from the existing outline page.
- Real generated page passed final PPTX-render review with zero repairs, exported 14,788 bytes, and contains native editable text.
- Desktop 1440px and mobile 375px: three steps, preview image loads, full download succeeds, no horizontal overflow or browser errors. Editing outline disables generation until recheck.
- Isolated synthetic suggestion fixture: preview/export both HTTP 200 and included in completed listing; browser shows nonblocking suggestion and downloads. Fixture deleted after verification.
- Real sample retained in software: project 8b7d23e6-8e03-4dfe-8da4-d6589b8fc4b0, title 自动核查实测：二次函数对称轴.

## Runtime
Scoped backend overlay: edu-video-backend:ppt-practical-review-20261024. Frontend overlay: edu-video-frontend:ppt-practical-review-20261024. Backend, worker, scheduler and frontend recreated after confirming no active PPT/video outline jobs. No schema migration, renderer replacement or unrelated main-worktree edits discarded. Prior runtime images and file backups retained for rollback. Main worktree has unrelated edits and is intentionally not committed wholesale.

## Limits
Model checks reduce confirmed factual errors but do not guarantee absolute correctness. User still confirms the corrected outline. Repair remains bounded; service failure remains distinct from content rejection. Existing outlines without knowledge metadata require checking once before generating again. Minor legacy validation error text still refers to illustrations for malformed page plans; valid text plans are accepted and tested.

Local verification artifacts and rollback manifest: .superpowers/sdd/2026-10-24-ppt-practical-review/.


## Follow-up: selected failed-page revision and preview warning removal

A page rejected before SVG creation has no renderer version. The previous revision guard treated every such selected placeholder as a legacy deck and failed with a misleading instruction to regenerate all slides. Renderer compatibility is now required only for pages being retained; every selected page is rebuilt, validated and audited with the current renderer. Unselected legacy pages remain rejected.

Removed the preview-level generation warnings block at user request. Per-page review statuses, issues and suggestions remain available. Existing runtime loading animations are preserved.

Regression evidence: two new selected-page cases reproduced the original failure before the fix; selected missing/old renderer pages now pass and unselected legacy pages still reject. Backend full suite: 688 passed, 3 skipped; feature frontend: 238 passed; runtime frontend: 244 passed. Both frontend builds exit 0. Desktop 1440px/mobile 375px live browser verification confirms no generation warning block, retained page statuses, and no overflow or page errors.

A temporary live fixture with one approved page and one failed placeholder was revised through the real browser and model. The selected page passed, the approved page remained byte-for-byte equal, both previews returned HTTP 200, and full export succeeded (17,232 bytes). The fixture was deleted after verification. Existing user presentation 7da65770-c9fa-4dc1-8427-5f3f54fbd25e remains intact with 15 pages. Runtime images: edu-video-backend:ppt-selected-repair-20261024 and edu-video-frontend:ppt-selected-repair-20261024.


## Follow-up: lock repeated outline knowledge checks

Passed, unchanged outlines display a disabled 已审查 button. Editing the outline enables 重新审查 and disables PPT generation; checking saves pending edits first. Saving alone does not restore approval. Selecting pages or typing unsubmitted rewrite instructions does not unlock review. Reverting unsaved content to the reviewed outline restores its approval. Unchecked or rejected outlines remain blocked from generation by both UI and existing backend enforcement.

Verification: 242 feature frontend tests and 248 integrated runtime frontend tests passed; both production builds exited 0. The backend exact-outline review gate regression passed in a disposable test database, which was removed. Browser checks at 375px and 1440px verified disabled approval, edit/revert transitions, blocked generation and no horizontal overflow or page errors. An intercepted unchecked-outline response also blocked generation. Existing user project data was not saved or regenerated during browser verification.

Runtime frontend image: edu-video-frontend:ppt-review-lock-20261024. Existing loading animations and their tests were preserved; backend services were unchanged. Scoped backups and verification artifacts: .superpowers/sdd/2026-10-24-ppt-review-lock/.


## Follow-up: administrator-controlled PPT web search

PPT now shares the administrator creation-form web_search visibility/default policy. Hidden search uses the administrator default; visible search accepts a project choice and otherwise starts with the default. An unavailable/disabled search provider forces search off. Configuration, project creation/update, job submission and worker reference collection use the same policy. Frontend draft restoration cannot override hidden or unavailable search settings. The admin page explains that its search settings also apply to PPT.

Verification: failing regressions reproduced the original leak before implementation. Full backend suite: 704 passed, 3 skipped. Feature frontend: 246 passed; runtime frontend: 252 passed; both production builds exited 0. Integrated runtime PPT API/workflow/search regression: 41 passed. Test databases were isolated and removed. Independent review found no blocking issues.

Deployed backend/worker/scheduler and frontend images: edu-video-backend:ppt-search-policy-20261024 and edu-video-frontend:ppt-search-policy-20261024. Deployment occurred with no active PPT/outline jobs. Existing runtime loading animations, unrelated backend changes and current administrator settings were preserved. No migrations or external search/model calls were needed for acceptance.

Live administrator settings remain visible=false, default=false with provider available=true. Browser checks at 375px and 1440px confirm the search switch is hidden, no horizontal overflow and no page errors. Actual create/update requests attempting web_search=true were saved as false; the temporary draft was deleted. Intercepted browser configuration checks also covered visible/default-on and hidden/default-on without changing the real administrator settings. Local backups, images, regression logs and browser evidence: .superpowers/sdd/2026-10-24-ppt-search-policy/.
