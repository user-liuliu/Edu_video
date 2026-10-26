# Textbox Resize and Drag Implementation Plan
> Execute inline using executing-plans, TDD and one final independent review.
Goal: Existing and newly added text boxes support explicit movement from the editing state, width adjustment and proportional enlargement/reduction on the original canvas.
Architecture: Preserve native SVG/text. Extend allowlisted text patches with width, persist as text width and existing manual group bounds; reflow spans on width change. Corner scales width and font within supported 18–72px range; side handle changes width and reflows. Visible dedicated move handle avoids textarea interception. Buttons and numeric width are pointer/keyboard alternatives. No new dependency.
Constraints: manual save remains direct without quality gate. Preserve old versions, allowlisted data/security/revision, original shapes and image drag behavior. Current dirty workspace with targeted backups; no reset or automatic commits. Complex transformed/formula text remains read-only for resizing.
- [x] Backend RED: width change persists/reflows, readonly rejection, invalid widths, actual save/reopen/native export, combinations with movement.
- [x] Backend GREEN: width patch/schema/descriptor, group bounds consistent, no semantic content/outline corruption when reflow only.
- [x] Frontend RED: handles remain accessible while typing; scaled pointer width/corner update; move from overlay; undo/cancel; new box movement in move mode.
- [x] Frontend GREEN: handles+numeric controls, proper scaled canvas deltas, one undo per gesture, bounds and focus management.
- [x] Verify regression suites/builds, independent review, deploy idle services, browser drag/resize/undo and screenshot. Do not save demo content to user deck.

User clarification: WPS-style frame resize is authoritative. Single click selects; double click enters text editing; eight control points change frame width/height, keeping font size unchanged. Drag border moves frame. Persist exact native PPT text frame using supported data-pptx-frame. Include height and x/y in allowlisted text patches for top/left handles; do not add SVG groups or change object keys.


Completion 2026-10-25:
- User clarified WPS frame resizing, so removed proportional font-scaling concept. Single click selects, eight handles resize native frame, font stays fixed; border and move handle move; double click edits. Numeric width/height and keyboard alternatives retained.
- Backend width/height/x/y strict patches persist data-pptx-frame. Native compiler supports exact frames; single-line writes plain text and multiline uses canonical x/dy paragraphs so frame is not lost during tspan lowering. Actual export tests assert native shape width/height/font, source geometry and history.
- text_layout preserves authored content separately from automatic wrapping; editor GET restores source; outline/title updates use authored text. No new quality checks on teacher save.
- Combined movement and resize apply translation first, final-coordinate geometry second, final bounds validation last. New/existing box constraints aligned. West/east handles both cap width at1200. Independent reviewer findings fixed and confirmed.
- Backend broad run 79 passed (backend-final.log); after last combined bounds fix text/canvas suite33 passed plus targeted shrink1 passed (backend-release.log/shrink-green.log). Frontend full329 passed (frontend-release2.log); final stable layout/frame double-click focused34 passed (frontend-frame-last.log). Backend/frontend production builds pass and deployed; backend healthy.
- Actual browser verified eight-point corner enlargement width476.32/height125.48 unchanged32px font, side shrink reflow, undo and real double click correct selected subtitle. Selection now keeps SVG node and reserves properties height; frame handles also accept double click. Screenshot wps-frame-final.png. Demo undone, user's deck/version untouched; clean editor remains open.
- Limit: existing transformed/formula text remains read-only for frame resize. No image/shape scaling requested this turn.
