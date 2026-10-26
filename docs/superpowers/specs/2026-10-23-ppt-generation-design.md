# Independent PPT generation

Approved scope: preserve the existing creation page layout; add a video/PPT switch. PPT accepts a name, requirement, optional reference files and web search. Only style is configurable; use the accepted clear-blue-teaching 1.0.0 template, fixed 16:9.

## Contracts
- Separate /api/presentations routes, project/material/job tables, Celery tasks and persisted outbox. No video generation or video credit charges. Shared authentication, file validation/parser, private object storage and JSON model client are permitted.
- Outline: 1–40 pages, stable UUIDs, title, teaching content, layout. User can add, delete, reorder, edit, or rewrite selected IDs with full deck context. Server rejects missing/extra IDs and applies selected changes only.
- Confirmation persists the exact outline revision before rendering. Each page has structured template content. Export and SVG preview derive from the same content and template geometry. Text and basic shapes remain editable in the complete PPTX.
- Template uses seven accepted layouts. Runtime bundles authored SVG/tokens only; never depends on the developer's skill installation. Model supplies text fields; template determines geometry. No arbitrary executable model SVG/code. Page rewrite preserves other pages; outline edits invalidate old rendering and export.
- Page snapshots are revisioned JSON stored with the project; previous rendering retained as history. Downloads require owner, current revision, and a complete deck.
- All mutations use revision checks and per-project locks. Jobs are database outbox entries with idempotency, expiring leases, heartbeat, owner status checks, and stale-result rejection. A separate scheduler recovers unacknowledged or expired work. Both job types share user concurrency limits.
- Reference files are owned by PPT project, validated and stored privately on upload, parsed inside outline generation. Image-only sources require configured vision model. File parse failures block generation and surface actionable errors. Search only runs if opted in and configured.
- Preview editing initially means selecting pages and asking the model to revise their content. WPS-style direct canvas editing and additional themes are deferred.

## Builder decisions
Use bounded token slots extracted from the authored SVG templates, clear sample graph object groups before filling them with topic-specific diagram labels, and render PPTX with native text/shape primitives. Use the existing outline model configuration (no new model setting), structured content validation and explicit capacity errors instead of shrinking text. Reuse existing upload UI with a default-video namespace prop. Lists gain a PPT filter within the existing page, not a new sidebar entry.

## Verification
Database-backed API and worker tests use a dedicated test database, provider/storage fakes at external boundaries, and no paid network calls. Test selected-page isolation, revision races, job recovery, ownership, complete export and escaped preview. Run frontend tests/build, backend tests and render an exported fixture for visual review.
