# Original Pixel Cast Plan

User authorized replacing the current LPC assets with original local pixel art, with a warm Stardew Valley visual reference and no image API.

Keep existing EduSprites interfaces; add manifest-driven characters, per-action frame metadata and original objects. Draw 20 distinct children, adults and elders with different hairstyles, silhouettes and clothes, four directions and 11 short animation sequences plus three static poses. Use native pixels, binary transparency, nearest-neighbor previews, stable foot origins and per-frame hand anchors. No copied game or LPC pixels.

Verified backup: `.superpowers/backups/sprite-assets-before-original-20261020-132930/sprite-assets.zip` (34 files). Replace only the active art directory after generating and validating a staging directory; preserve unrelated work.

- [x] Add tests and observe expected failures for catalog, distinct designs, actions, transparency and HTML budget.
- [x] Build reproducible original cast and objects; inspect and revise at least twice, then replace old art.
- [x] Integrate manifest-based runtime, original-art guidance and accurate export provenance.
- [x] Verify Python/Node behavior and offline browser rendering, create animated catalog and report deployment boundary.

Review: age proportions, back/side views, hand contacts, nonlooping action endpoints, reverse seeking, payload budgets and removal of obsolete license claims.

## Verified outcome — 2026-10-20

- 20 original characters, 11 animated actions in four directions, three static poses and 12 objects. Active library has 34 files matching staging hashes. Old library is quarantined with a 34-file ZIP and SHA256 inventory.
- Read-only independent review identified backpack/apron back-view visibility; corrected after a failing regression. Existing frozen videos retain embedded historical credits.
- Final Linux backend suite: **423 passed, 1 skipped** in 308.41 seconds. The skipped Node-dependent contact check is covered separately with Windows Node output and renderer Pillow: **10,560 contacts touch opaque atlas pixels**. Windows motion and original sprite browser checks pass.
- Real Chrome offline catalog: 44 action/direction combinations, deterministic reverse seeking, 20 characters, no network requests or browser errors.
- Production renderer validated and exported a six-second 640×360, 12 FPS MP4 using synthetic silence and no provider/API calls. ffprobe confirms duration and original-art provenance.
- Built backend/renderer images; confirmed no active Celery jobs before recreating backend, renderer, worker and scheduler. Running backend/worker/renderer share runtime digest `bbdf45a4d88415072fd0687af46aaaed5bb84b161f180658d19e09ff603bbc48` and 20-character asset digest `22d384eaabe92ab612314f711423eda91fec111c60340d76b626b1bdcf44e84f`. API/DB and worker-to-renderer health pass.
- Evidence: `.superpowers/asset-expansion/{full-tests-final.log,browser-result.json,render-result.json,build.log}`.
- Ruling: preserve all existing unrelated uncommitted changes and keep this change uncommitted; no merge/push or workspace cleanup was requested. Backups and validation evidence remain available.
