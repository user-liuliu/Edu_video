# PPT Preview Layout Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for this localized approved UI change.

**Goal:** Implement the user-approved PPT preview sample with the video preview's layout conventions.
**Architecture:** Keep the existing presentation API and review/export guards. Move preview content before the right-hand page directory, reveal a multi-page revision panel on demand, and isolate layout styles to the preview component.
**Tech Stack:** Vue 3, TypeScript, Element Plus, Vitest; existing Docker frontend.
**Spec:** User-approved sample at .superpowers/brainstorm/2026-10-25-ppt-preview-sample/index.html and approval dated 2026-10-25.

## Global Constraints
- Only change the PPT preview frontend, its scoped stylesheet, and related tests.
- Keep real rendering, polling, confirmation, review gating, partial delivery, download URLs and revision requests intact.
- Do not overwrite unrelated dirty/untracked work or commit it.
- Keep the approved sample's title, player-first order, compact summary, on-demand editing, and preview-adjacent download action.

## Review Focus
- Pending/failed/unconfirmed outlines never generate merely by opening preview.
- Unapproved pages cannot expose images or downloads; partial approved output remains usable.
- Advice opens the revision panel for exactly the advised page with complete editable instructions.
- Switching pages, cancel/reopen and job polling preserve valid page selection and disabled states.
- Long titles, 12+ pages and narrow viewports keep the preview readable without horizontal overflow.

### Task 1: Apply approved preview layout and editing interactions
**Files:** Modify frontend/src/views/workbench/PptPreviewView.vue; create frontend/src/styles/ppt-preview.css; create frontend/tests/ppt-preview-layout.spec.ts; adjust existing selectors only where structure changes.
**Interfaces:** Keep startPptJob(project, kind, extra), pptExportUrl, pptPreviewUrl and usePptProject unchanged. New visible editing state is local to PptPreviewView.
- [x] Add tests for player-before-directory order, preview-local actions, collapsed review and no default edit controls.
- [x] Add tests for current-page preselection, multi-select revise payload, cancel/reopen, advice opening, stale review and export gating.
- [x] Observe the new tests fail on missing layout/interaction.
- [x] Implement the scoped layout and minimal local editing behavior.
- [x] Run new tests plus ppt-flow and ppt-confirmation; run all frontend tests and production Docker build.
- [x] Request a focused independent review against snapshots; resolve material regressions.
- [x] Deploy frontend only, verify real generated preview and responsive layout with browser screenshots.

## Execution notes
Continue in the existing checkout because the approved PPT implementation is untracked work in this shared active development workspace; a HEAD-only worktree would omit it. Preserve before snapshots and leave changes uncommitted.
