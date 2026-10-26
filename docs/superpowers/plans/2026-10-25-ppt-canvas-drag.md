# PPT Canvas Drag Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement inline with a final independent review.

**Goal:** Move existing pictures, shapes/groups and text boxes directly on the original preview canvas, with undo and persisted native PPT export.
**Architecture:** Extend existing allowlisted SVG editing API with stable object descriptors and bounded translation patches. Keep Vue/SVG canvas, use pointer capture and page-coordinate deltas. Preserve original nodes, assets, page IDs and version history. Text click still edits; drag threshold separates moving from typing. Provide an explicit move mode and keyboard arrows as alternatives.
**Tech Stack:** Existing Vue 3, TypeScript, Python SVG and native PPT compiler; no added dependencies.
**Spec:** User request in current conversation to support dragging pictures, shapes and text boxes.

## Global Constraints
- Work in existing dirty workspace; targeted backups only, no resets, branch changes or automatic commits.
- Translation only in this increment; backgrounds/definitions stay fixed. Preserve text editing and new text boxes.
- Only server-held SVG may be changed; do not accept replacement SVG or arbitrary transforms. Revision/owner locks and compile/render checks remain authoritative.
- Retain current export acceptance, generated reminders and old version preview/download.

## Review Focus
- Pointer cancellation, editing vs dragging, canvas scale and bounds.
- Existing SVG transforms and nested groups without invalid nested transforms.
- Reopen after movement then edit text or drag again.
- Original geometry, asset authorization and historical snapshot preservation.
- Nonfinite numbers, duplicate/unknown/overlapping parent-child moves, unchanged saves.

### Task 1: Server translations
- [x] Write tests for descriptors, text/image/group movement, bounds and history/native export. Verify RED.
- [x] Implement geometry translation and descriptors; add strict movement schema, integrate existing editor endpoints.
- [x] Verify GREEN, including reopen and actual PPT native export.

### Task 2: Canvas interaction
- [x] Write tests for scaled pointer movement, click vs drag, undo/cancel, new box placement and structured save. Verify RED.
- [x] Implement object selection, pointer capture and move toolbar/keyboard controls with one undo step per drag.
- [x] Verify GREEN, all frontend tests and production build.

### Task 3: Delivery
- [x] Independent review and fix material findings; run final relevant backend regressions.
- [x] Deploy idle services, browser verify actual selection/movement/undo and preserve user deck data.
- [x] Capture screenshot and report scope/verification.


## Completion Evidence
- Extended existing editor descriptor and allowlisted move payload; text/image/path/group translation baked into native SVG geometry; existing transformed groups retain valid local coordinates. Pointer handling uses threshold and capture, keyboard nudging, move-mode selection, undo/cancel, fixed backgrounds.
- Backend final related regression: 58 passed (backend-final3.log), plus actual native image export position test: 1 passed (picture-export.log). These cover original shape geometry, same-occupancy text edit, parent+child order, transformed groups, missing text axes, history/reopen, other pages and version/export gating.
- Frontend full: 319 passed across 31 files (frontend-full-final.log). Production backend/frontend builds successful. Actual localhost browser verified group drag, individual text drag, click-to-edit, undo and fixed background exclusion.
- Independent reviewer identified transformed local bounds and default text coordinates; reproduced RED and fixed GREEN. No paid model jobs used. Native picture remains p:pic, shape stays custom geometry, text stays native text.
- Local Docker services updated with idle generation worker; backend healthy. Demo movement reverted using undo, original user deck unchanged. Browser left in clean editor state; drag-final.png shows actual unsaved demonstration.
- Boundaries: translation only, no resize/rotate or layer ordering. A rare group with three nonidentity scale/rotate operations and no translation reports a specific failure and retains input rather than producing invalid output.
