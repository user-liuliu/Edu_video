# Conservative animation context integration plan

> Required sub-skill: executing-plans.

**Goal:** Integrate the user-approved sample compaction at the real film exchange entry without discarding teaching facts or continuity.
**Architecture:** A pure copied-request adapter used only for shared_first/append_modules. Keep original frozen data and digest unchanged; request shaping affects outgoing JSON only.
**Spec:** User approved the conservative sample after reviewing its seamless quadratic animation. No deployment or real model regeneration required in this integration turn.

- [x] Write exchange-entry RED tests: all-route facts, active timing and immutable shared/previous code preserved; seed future cues removed; unique narration/extra fields preserved; non-ordered requests unchanged; actual ordered generation uses adapter.
- [x] Implement small film_context adapter; integrate before schema serialization; adjust prior neighbor expectation to ignore only redundant sentence cues. Run focused generation and checkpoint tests GREEN.
- [x] Run dedicated-DB direct pipeline and continuation regression, verify sample equivalence and runtime digest, independent read-only review, document results and git diff --check.

## Verification evidence
- RED: exchange tests failed as intended before adapter integration (2 failed, 4 passed).
- GREEN, final: 59 focused generation/context/checkpoint/transport tests passed, exit 0.
- Dedicated temporary database: 28 direct pipeline and continuation tests passed, exit 0; database removed.
- Replayed all three approved sample module requests through the formal ordered generator: same requests excluding prototype-only empty navigation lists, same validated bundle, original request and checkpoint fingerprint unchanged. No provider calls.
- Runtime digest matches the approved sample: `7cde2df2e763409daab2f5771f385bd2e7872fe79e4c102fd70c7508610c8dee`.
- Independent read-only reviewer found no important or blocking issues in the scoped integration.
- No running service restart, deployment, git commit, push, merge, or unrelated PPT/UI edits performed.

This is conservative request shaping only, not a complete large-input gateway fallback implementation.
