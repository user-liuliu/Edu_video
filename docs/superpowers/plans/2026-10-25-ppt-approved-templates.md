# Approved teaching templates integration

> Execute inline using writing-plans, executing-plans and TDD. User approved the reviewed templates and compatibility approach.

Goal: Publish only lively-illustration and academic-formal beside clear-blue-teaching, retaining auto as clear blue.
Architecture: A packaged server catalog provides immutable tokens, the selected approved layout source and design instructions. Page design metadata binds generation, repair, export and fallback to the same template. No schema migration.
Spec: assets/ppt-templates/{lively-illustration,academic-formal}_20261025/templates.
Constraints: old decks/history untouched; no retroactive charging, no production model calls, no paid test generation; current dirty workspace is authoritative. Work in place with exact backups; no commits/reset/cleanup.

Review focus: legacy pages without template metadata; saving a new style after an existing deck; stale checkpoints; fallback tamper protection; direct edits preserving intentional local colors.

- [x] Add red tests for config/create/update/history, selected reference in model prompts, style-consistent deterministic fallback and native export.
- [x] Add packaged styles.py catalog and approved assets; validate schema; resolve metadata on create/update and snapshot history.
- [x] Wire planning/execution/revision/repair/checkpoint/export; preserve clear-blue graphics branch; new styles use model-authored native diagram layouts.
- [x] Add frontend tests for style submission and resolved historical preview name; remove hardcoded preview label.
- [x] Run targeted then full regression checks; compile representative themed fallback decks offline; fresh-context review when available.
- [x] Build containers, verify workers idle before update, deploy and inspect UI without generating a paid job.

Ruling: approved existing workspace includes uncommitted PPT implementation, so a clean git worktree would omit the application under test. Preserve exact backups and operate on current workspace. User approved continuation after compatibility explanation; no extra plan approval.
