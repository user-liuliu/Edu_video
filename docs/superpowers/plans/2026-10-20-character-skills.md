# Direct HTML character guidance integration

User-approved scope: keep model-authored self-contained HTML/CSS/JS/Canvas/SVG, add upstream open-source character/pixel/acting references, prefer simple readable pixel-character actions. No fixed character renderer, action whitelist, extra model/review call, teacher workflow, voice or database change.

1. Add failing tests for character/pixel routing, negative style cases, licensed source validation, bounded context and actual direct-HTML request injection.
2. Vendor only selected upstream Markdown and licenses at fixed commits, with SHA256 metadata. Extend the existing loader with explicit license validation and bounded original sections. Preserve teacher styles; select pixel guidance only for pixel requests; character acting only for relevant narrative/character contexts.
3. Update HTML instructions to internally reuse character definitions, use conservative poses and clear intention/reaction, preserve contacts and deterministic absolute-time rendering; no new animation engine. Apply the same guidance on initial generation and technical repair.
4. Run focused tests then the full backend suite against a verified separate test database; review source provenance, source diffs and packaging. Record actual outcomes and visual-quality limits. No production deployment until verification and no active-job interruption.


## Completion evidence (2026-10-20)

- Added two unchanged pinned upstream sources: 2d-character-rig-animation (MIT) and game-graphics (Apache-2.0). Six total sources and 28 source/license files pass SHA256 verification. The animate candidate was excluded because its beat-cut workflow is unnecessary here.
- Initial generation and checkpoint repair now share a request builder, including teacher request, section visual instructions, frozen narration, selected upstream chapters and the actual model-consumed runtime adapter. No new model step or character engine was added.
- RED/GREEN: six selector cases and the production request-boundary test failed before implementation; 28 focused tests then passed. Review found explicit pixel negation and local-style precedence gaps; four added regression cases failed before the correction, then all 32 focused tests passed. Independent review rechecked 11 routing variants and accepted the fix.
- The first host full-suite attempt yielded 370 passed and nine environment failures: one Alembic working-directory failure and eight cases depending on unavailable host offline-speech binaries. The isolated Docker environment supplied production speech binaries, dev test dependencies, renderer sources and the correct working directory. The final complete backend run passed all 383 tests in 81.78 seconds.
- Test database name and local endpoint were verified distinct from production before database tests. No production test fixtures were executed.
- Backend image built successfully. Deployment checked zero pending/running generation jobs, then recreated only backend, worker and scheduler with no dependency restart or port change. All three containers were verified against hashes of the 10 new/changed executable-reference files. Health endpoint on port 8080 returned 200 with database available. Renderer and frontend remained running.
- Existing compiler digest stayed e44782fcb1a24f2cf5f314db1ce7fc98e0762d46c14731bdf3d5026fa00d051e. Existing sealed previews and export contracts were not invalidated. No audio fingerprint, schema or dependency change.
- Automated coverage establishes source loading, routing, real request injection, repair, audio reuse and export compatibility. It does not prove model artistic quality; inspect newly generated films for visual quality. Existing films are not retroactively redrawn.


## Story pixel defaults follow-up (2026-10-20)

User approved a content-level default: character stories use detailed pixel art; formulas, graphs and experiments use clear graphical animation. Explicit teacher styles and local style revisions win. This applies to all story topics, not named samples, with no new model step or fixed animation engine.

- New style snapshots carry semantic defaults and plain-language instructions; both the expression pass and actual HTML request consume them. Reference selection handles cross-subject stories and mixed scientific scenes, with explicit style/negation precedence. The adapter is now direct-html-skills-3.
- Mixed story/science references exceeded the existing context budget during RED verification. Removed the upstream hierarchy/IK implementation section (unnecessary without a fixed rig engine); retained drawing, acting and contacts sections and kept the 23,500-character bound.
- RED/GREEN covered default stories without the pixel keyword, clear technical graphics, mixed content, unknown subjects, explicit water ink/cut-paper/watercolor and negative styles, local style changes, generated-prompt drift and request wiring. All 73 focused tests passed before full-suite verification.

- Independent review found keyword-negation, English history/story and motion-only revision ambiguities. Added four failing regressions and fixed routing. Reviewer rechecked seven cases and reported no remaining important issue. Final focused run: 77 passed.
- Final complete backend regression in Docker: 410 passed in 89.39 seconds, against the verified separate test database. Production image build exited 0. Checked zero pending/running jobs before recreation; updated only backend, worker and scheduler with --no-deps --no-build. All services became healthy.
- Deployment verified all five changed application/reference-document files against local SHA256 hashes in all three containers. Live worker passed four story/science/explicit-style cases; adapter direct-html-skills-3 loaded. Port 8080 health returned HTTP 200 with db=true, and Celery returned pong. Compiler digest is unchanged, so prior previews/export remain compatible. Existing films require a new full generation to apply the new visual default; no paid model generation or subjective visual-quality claim was made in this verification.
