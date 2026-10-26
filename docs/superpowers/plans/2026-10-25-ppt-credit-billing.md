# PPT Credit Billing Implementation Plan
> Execute inline with test-driven-development and executing-plans; final independent review.
Goal: PPT generation costs 10 shared account credits, matching video success-only billing.
Policy: render and AI revise are each billed once per successful full output. Outline/rewrite/check/manual text+layout edits/export/download free. Reserve10 on submit; settle with publication transaction; release on failure/cancellation/exhausted retries/partial output. Duplicate requests or workers never double-charge. Existing predeployment jobs without a hold remain free.
Architecture: Dedicated PPT reservation table with PPT-job FK, reuse same wallet row lock, include active PPT holds in account reserved/available balance alongside video holds. Add ppt_generation ledger kind and ppt_cost balance field; publish result and debit atomically. Keep video mechanism intact. No retrospective charging.
Constraints: Existing dirty workspace, target backups, no reset or auto commits; use TEST_DATABASE_URL only for tests; never run paid generation against user data as verification.
Review focus: last10credits video/PPT race; stale lease must neither charge nor release newer owner; idempotent API/worker; late errors rollback output and charge; ledger survives project deletion; migration alignment.
- [x] RED tests insufficient, hold/replay, full success once, failure/cancel/exhaustion/refund, mixed video/PPT concurrency, old jobs, free operations and ledger.
- [x] GREEN reservation schema+migration, shared wallet balance service, submit/worker settlement and release.
- [x] UI cost notice/balance preflight/refresh and ledger text; tests show10 and block insufficient; preserve manual editing/export.
- [x] Run billing/PPT/migration+frontend regressions, independent review, build/deploy idle services and validate migration+UI without charging user.


Completion 2026-10-25:
- Added dedicated PPT credit reservations, migration0010, shared wallet lock and combined video/PPT active holds. PPT render/revise reserve10, publication atomically settles; failure/cancel/exhaustion/partial releases. Duplicate API/worker and stale lease do not charge twice. Legacy jobs without holds remain free. Ledger preserved on deletion.
- Outline/rewrite/check/manual edits and download/export remain free. UI shows10credit policy, preflights balance and refreshes global balance on job transitions. Balance page labels PPT consumption separately.
- Verification: initial red9 billing failures, green30 billing/video/credits/migration tests. Full related PPT+credit+migration regression251 passed (backend-regression.log). Final PPT billing suite15 passed, including post-settlement rollback and zero-balance manual/export (backend-billing-final.log). Frontend336 tests/31files passed (frontend-full.log). Backend/frontend production builds pass.
- Independent reviewer confirmed no blocking issue in concurrency/atomic rollback/idempotency/lease/refund/schema/ledger scope.
- Deployment: confirmed zero active video/PPT jobs, deployed backend/worker/scheduler/frontend. Migration0009->0010 verified. Aggregate wallet930 and ledger count19 unchanged before/after. PPT holds0. No real generation submitted, no user debit or content mutation.
- Browser: existing孔融让梨preview displays10credits, free-outline/manual/download message and available930. Screenshot ppt-credit-final.png, tab retained.
