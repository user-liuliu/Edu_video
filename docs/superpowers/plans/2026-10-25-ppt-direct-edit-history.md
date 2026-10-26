# PPT direct page editing and version preview

Goal: Apply user edits to current page SVG and preserve old completed decks for preview/download.
Approved scope: User accepted direct model edits and requested old PPT preview after new generation.
Architecture: Keep existing worker, owner checks, validated native export and bounded quality/repair/downgrade sequence. Direct edit contract receives original instruction and current SVG. Content changes synchronize to outline after editing, with knowledge checks. Fetch selected history snapshot on demand; use explicit version query for preview/export.
Tech: FastAPI, SQLAlchemy/PostgreSQL, Vue3/TypeScript.
Constraints: Atomic publication; unchanged pages remain exact; no fake review pass; no production-deck mutations for testing; preserve last-10 history policy and support legacy page-only snapshots. Historical snapshots are read-only.
Review focus: stale version identity must not silently serve latest; rapid version switches must not mix content; unselected pages remain exact; knowledge corrections update SVG and outline; checkpoint recovery retains budgets.

- [x] Task 1: RED tests for direct SVG edit and request verification, implement current SVG plus instruction contract and bounded quality repair, synchronize content after editing.
- [x] Task 2: RED API tests for version isolation and owner checks, implement version summaries, snapshot retrieval and historical preview/export, deduplicate snapshots.
- [x] Task 3: RED UI tests for switching, navigation, download and return to current; implement compact version selector.
- [x] Task 4: Focused/full suites, native export check, frontend build, independent review, resolve material findings and deploy after no-active-job check.
