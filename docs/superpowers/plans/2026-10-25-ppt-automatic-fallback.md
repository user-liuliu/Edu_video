# Automatic PPT completion
User-approved spec: after bounded model repairs, use a deterministic readable fallback from the confirmed outline; paginate rather than truncate; check actual exported pages; retain passed pages. Do not ask the user to complete individual failed pages. Preserve prior delivery if a genuine content or infrastructure failure prevents completion.

Task 1: tests RED then GREEN for fixed SVG, exact text preservation, stable continuation IDs, checked-outline derivation, bounds, escaping, and page limit. New fallback.py only.
Task 2: tests RED then GREEN for fallback after generation/review failures, planning failure, checkpoint restart, retention of approved pages, and refusal to approve unavailable/failed review. Change generation.py and optional repair in quality.py. Publish complete decks only for new runs.
Task 3: focused tests, backend suite in isolated test database, actual native PPTX render and visual QA. Fresh final review. Deploy local services only if no active jobs, with rollback image.

Constraints: preserve unrelated work; no commits/reset/clean. Existing 40-page resource boundary remains; overflow beyond it is a bounded production error rather than data loss or false approval. Pagination copies exact source content and retains title/layout; provenance records the original reviewed digest and new partition digest. No new teaching claims. No unreviewed delivery.
Review focus: resume after partially audited fallback; source provenance and UUID collisions; revised subsets; failed planning; content mismatch across pagination; prior deck preservation; malicious SVG text; real exported text clipping.

Completion: all three tasks complete. Evidence: .superpowers/sdd/2026-10-25-ppt-automatic-fallback/progress.md, final-focused.log, final-integration.log, deployment-verification.json. Independent reviewer findings fixed; final verdict unavailable due upstream failure.
