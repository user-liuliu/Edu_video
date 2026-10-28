# studio-vendor

Builds the offline library bundle used by the studio video pipeline. Headless Chromium loads these
files from `/studio-runtime/<digest>/<name>` with no network access, so everything must be self-contained.

Rebuild (output is committed, `node_modules` is not):

```bash
cd tools/studio-vendor && npm ci && node build.mjs
```

Output goes to `backend/app/studio/runtime/vendor/` (libs, `fonts/`, `katex-fonts/`, `fonts.css`,
`licenses/`, `manifest.json`, `NOTICE.md`). Versions are pinned exactly in `package.json` / `package-lock.json`.

Notes:

- `three` has no classic global build, so it is bundled with esbuild as an IIFE (`THREE`) into `three.iife.js`,
  with `legalComments: 'eof'` so three's `@license` headers stay in the file.
- Each package's license file is copied into `vendor/licenses/`. The `gsap` npm package ships none, so its
  Standard "No Charge" terms are kept in `licenses/GSAP-Standard-No-Charge.txt` here; refresh that file from
  https://gsap.com/standard-license when upgrading GSAP.
- Rough.js uses the package's prebuilt `bundled/rough.js` (global `rough`).
- GSAP DrawSVG / MorphSVG / MotionPath / SplitText come from the public npm package (3.13+).
- Fonts keep the packages' `unicode-range` subsets (woff2 only); `font-family` is `Noto Sans SC` (400, 700) and `LXGW WenKai` (400).
- If the default npm registry is slow, add `--registry=https://registry.npmmirror.com`.
- After rebuilding, run `cd backend && uv run --env-file ../.env pytest tests/test_studio_assets.py -q`.
