# Practical PPT Review Implementation Plan
> **For agentic workers:** Use superpowers:executing-plans inline. User approved the chat design and direct execution.
**Goal:** Check outline knowledge before user confirmation; deliver PPT based on substantive correctness and usability.
**Architecture:** Digest-bound outline review, explicit check job, blocking issues versus suggestions, optional illustrations with SVG security preserved.
**Tech Stack:** Python/FastAPI/Postgres, Vue/TypeScript/Vitest, existing native PPT adapter.
**Spec:** ../specs/2026-10-24-ppt-practical-review.md
## Global Constraints
Preserve unrelated backend/video edits, existing three steps, old successful decks and exact-content gates. No migration or relaxed SVG script/external-resource validation.
## Review Focus
- Edited formula requires checking exact saved content before render.
- Suggestions remain visible/exportable without repair; true blockers still repair/fail.
- Invalid provider output/service failures never become approval.
- Text-only formula exports editable; unsafe SVG remains rejected.
- Selected revisions preserve other pages and previous deck on failure.
### Task 1: Outline knowledge review
Files: new knowledge.py; generation.py, schemas.py, router.py; test_ppt_knowledge.py/test_ppt_workflow.py.
Interface: check_outline(config,outline,refs,progress=None)->reviewed outline; require_reviewed_outline(outline). New check job returns corrected outline for user confirmation.
- [x] RED tests for correction, malformed output, stale approval and edits.
- [x] Implement bounded knowledge-only review for generated/rewritten/check outlines and pre-render gate.
- [x] GREEN focused backend tests.
### Task 2: Practical page review
Files: quality.py, generation.py, master_runtime.py, router.py; quality/native tests.
Interface: issue severity blocking/suggestion; blocking_issues(issues); passed may contain suggestions.
- [x] RED tests for suggestion delivery, serious blockers, text-only export and overlap false positives.
- [x] Implement repair only blockers, service/generation labels, optional illustrations and native export.
- [x] GREEN tests plus actual editable formula render.
### Task 3: Existing UI and integration
Files: presentations.ts, PptOutlineView.vue, PptPreviewView.vue, PptList.vue; ppt-flow.spec.ts.
- [x] RED UI tests for explicit knowledge checking and suggestion preview/export.
- [x] Implement review changes and invalidation after edits, retain three steps.
- [x] Run backend/frontend suites, build and independent final review.
- [x] Deploy scoped files, verify live API/export/browser and commit feature branch.
