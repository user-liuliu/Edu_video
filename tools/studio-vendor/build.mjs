// Offline vendor bundle builder for the studio video pipeline.
// Usage: cd tools/studio-vendor && npm ci && node build.mjs
// Output: backend/app/studio/runtime/vendor/** (committed to the repo).
import { build } from 'esbuild';
import { createHash } from 'node:crypto';
import {
  copyFileSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync,
} from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const NM = join(HERE, 'node_modules');
const OUT = resolve(HERE, '../../backend/app/studio/runtime/vendor');

const GSAP_LICENSE = 'GSAP-Standard-No-Charge';

function pkgInfo(name) {
  const pkg = JSON.parse(readFileSync(join(NM, name, 'package.json'), 'utf8'));
  return { name: pkg.name, version: pkg.version };
}

const files = {}; // relative posix path -> { package, version, license }

function register(rel, pkgName, license) {
  const { name, version } = pkgInfo(pkgName);
  files[rel] = { package: name, version, license };
}

function copy(src, rel, pkgName, license) {
  const dest = join(OUT, rel);
  mkdirSync(dirname(dest), { recursive: true });
  copyFileSync(src, dest);
  register(rel, pkgName, license);
}

function write(rel, content, pkgName, license) {
  const dest = join(OUT, rel);
  mkdirSync(dirname(dest), { recursive: true });
  writeFileSync(dest, content);
  register(rel, pkgName, license);
}

// Always rebuild from scratch so stale files never linger.
rmSync(OUT, { recursive: true, force: true });
mkdirSync(OUT, { recursive: true });

// --- GSAP core and plugins (public npm package, 3.13+) ---
for (const name of [
  'gsap.min.js', 'DrawSVGPlugin.min.js', 'MorphSVGPlugin.min.js',
  'MotionPathPlugin.min.js', 'SplitText.min.js',
]) {
  copy(join(NM, 'gsap/dist', name), name, 'gsap', GSAP_LICENSE);
}

// --- KaTeX: js, css (font urls rewritten to katex-fonts/), woff2 fonts ---
copy(join(NM, 'katex/dist/katex.min.js'), 'katex.min.js', 'katex', 'MIT');
let katexCss = readFileSync(join(NM, 'katex/dist/katex.min.css'), 'utf8');
const katexFonts = new Set();
// Keep only the woff2 source of each @font-face; Chromium always supports woff2.
katexCss = katexCss.replace(/src:\s*url\(fonts\/([^)]+?)\.woff2\)\s*format\("woff2"\)[^;}]*/g, (_m, base) => {
  katexFonts.add(`${base}.woff2`);
  return `src:url(katex-fonts/${base}.woff2) format("woff2")`;
});
if (/url\(fonts\//.test(katexCss) || katexFonts.size === 0) {
  throw new Error('katex.min.css contains url() paths that were not rewritten');
}
write('katex.min.css', katexCss, 'katex', 'MIT');
for (const f of [...katexFonts].sort()) {
  copy(join(NM, 'katex/dist/fonts', f), `katex-fonts/${f}`, 'katex', 'MIT');
}

// --- three.js: no classic global build any more, bundle as IIFE exposing THREE ---
const threeResult = await build({
  stdin: { contents: "export * from 'three';", resolveDir: HERE, sourcefile: 'three-entry.js' },
  bundle: true,
  format: 'iife',
  globalName: 'THREE',
  minify: true,
  legalComments: 'eof',  // keeps three's @license headers (MIT), gathered at the end of the file
  target: 'chrome110',
  write: false,
});
const threeBanner = `/*! three r${pkgInfo('three').version.split('.')[1]} (${pkgInfo('three').version}) | MIT | bundled as IIFE, global THREE */\n`;
write('three.iife.js', threeBanner + threeResult.outputFiles[0].text, 'three', 'MIT');

// --- Rough.js: prebuilt bundled IIFE exposing global `rough` ---
copy(join(NM, 'roughjs/bundled/rough.js'), 'rough.js', 'roughjs', 'MIT');

// --- Fonts: keep the packages' unicode-range subsets, woff2 only ---
function fontCss({ cssPath, srcDir, familyOut, prefix, pkgName }) {
  const css = readFileSync(cssPath, 'utf8');
  const blocks = css.match(/@font-face\s*\{[^}]*\}/g) ?? [];
  const out = [];
  for (const block of blocks) {
    const m = block.match(/url\(['"]?\.\/files\/([^'")]+?\.woff2)['"]?\)/);
    if (!m) throw new Error(`no woff2 source in ${cssPath}: ${block.slice(0, 120)}`);
    const file = m[1];
    const weight = block.match(/font-weight:\s*(\d+)/)[1];
    const range = block.match(/unicode-range:\s*([^;}]+)/)[1].trim();
    const target = `fonts/${file}`;
    if (!files[target]) copy(join(srcDir, file), target, pkgName, 'OFL-1.1');
    out.push(
      `@font-face{font-family:"${familyOut}";font-style:normal;font-weight:${weight};font-display:block;`
      + `src:url(${target}) format("woff2");unicode-range:${range}}`,
    );
  }
  if (out.length === 0) throw new Error(`no @font-face found in ${cssPath}`);
  return `/* ${prefix} */\n${out.join('\n')}\n`;
}

const noto = join(NM, '@fontsource/noto-sans-sc');
const wenkai = join(NM, 'lxgw-wenkai-webfont');
const notoParts = [400, 700].map((w) => fontCss({
  cssPath: join(noto, `${w}.css`),
  srcDir: join(noto, 'files'),
  familyOut: 'Noto Sans SC',
  prefix: `Noto Sans SC ${w}`,
  pkgName: '@fontsource/noto-sans-sc',
}));
const wenkaiPart = fontCss({
  cssPath: join(wenkai, 'lxgwwenkai-regular.css'),
  srcDir: join(wenkai, 'files'),
  familyOut: 'LXGW WenKai',
  prefix: 'LXGW WenKai 400',
  pkgName: 'lxgw-wenkai-webfont',
});
const fontsCss = [...notoParts, wenkaiPart].join('\n');
const notoInfo = pkgInfo('@fontsource/noto-sans-sc');
const wenkaiInfo = pkgInfo('lxgw-wenkai-webfont');
files['fonts.css'] = {
  package: `${notoInfo.name} + ${wenkaiInfo.name}`,
  version: `${notoInfo.version} + ${wenkaiInfo.version}`,
  license: 'OFL-1.1',
};
writeFileSync(join(OUT, 'fonts.css'), fontsCss);

// --- License texts: each package's own files, shipped next to the code they cover ---
// GSAP's npm package has no license file; its terms are kept in tools/studio-vendor/licenses/.
// Rough.js's bundle includes its four small MIT dependencies, so their licenses ship too.
const LICENSES = [
  [join(HERE, 'licenses/GSAP-Standard-No-Charge.txt'), 'licenses/gsap/GSAP-Standard-No-Charge.txt', 'gsap', GSAP_LICENSE],
  [join(NM, 'katex/LICENSE'), 'licenses/katex/LICENSE', 'katex', 'MIT'],
  [join(NM, 'three/LICENSE'), 'licenses/three/LICENSE', 'three', 'MIT'],
  [join(NM, 'roughjs/LICENSE'), 'licenses/roughjs/LICENSE', 'roughjs', 'MIT'],
  ...['hachure-fill', 'path-data-parser', 'points-on-curve', 'points-on-path'].map(
    (dep) => [join(NM, dep, 'LICENSE'), `licenses/roughjs/${dep}/LICENSE`, dep, 'MIT']),
  [join(noto, 'LICENSE'), 'licenses/noto-sans-sc/LICENSE', '@fontsource/noto-sans-sc', 'OFL-1.1'],
  [join(wenkai, 'OFL.txt'), 'licenses/lxgw-wenkai/OFL.txt', 'lxgw-wenkai-webfont', 'OFL-1.1'],
  [join(wenkai, 'LICENSE'), 'licenses/lxgw-wenkai/LICENSE', 'lxgw-wenkai-webfont', 'MIT'],
];
for (const [src, rel, pkgName, license] of LICENSES) copy(src, rel, pkgName, license);

// --- manifest.json ---
const sha256 = (rel) => createHash('sha256').update(readFileSync(join(OUT, rel))).digest('hex');
const manifest = { files: {} };
for (const rel of Object.keys(files).sort()) {
  manifest.files[rel] = { ...files[rel], sha256: sha256(rel) };
}
writeFileSync(join(OUT, 'manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`);

// --- NOTICE.md ---
const packages = new Map();
for (const [rel, e] of Object.entries(manifest.files)) {
  if (rel.startsWith('licenses/')) continue;  // code and font files decide a package's license
  for (const [i, p] of e.package.split(' + ').entries()) {
    packages.set(p, { version: e.version.split(' + ')[i], license: e.license });
  }
}
for (const [, , pkgName, license] of LICENSES) {  // packages only bundled inside another file
  if (!packages.has(pkgName)) packages.set(pkgName, { version: pkgInfo(pkgName).version, license });
}
const licenseFiles = new Map();
for (const [, rel, pkgName] of LICENSES) {
  licenseFiles.set(pkgName, [...(licenseFiles.get(pkgName) ?? []), `\`${rel}\``]);
}
const lines = [
  '# Third-party notices',
  '',
  'Generated by `tools/studio-vendor/build.mjs`. Do not edit by hand.',
  '',
  '| Package | Version | License | License text |',
  '| --- | --- | --- | --- |',
  ...[...packages].sort().map(([p, e]) => `| ${p} | ${e.version} | ${e.license} | ${(licenseFiles.get(p) ?? []).join(', ')} |`),
  '',
  'hachure-fill, path-data-parser, points-on-curve and points-on-path are bundled inside `rough.js`.',
  '',
  '## Where the notices are',
  '',
  "- Every package's full license text is under `licenses/` (copied unmodified from the package; GSAP's",
  '  npm package has none, so its terms come from `tools/studio-vendor/licenses/`).',
  '- GSAP files are copied unmodified and keep their `@license` header.',
  "- `three.iife.js` is bundled with esbuild `legalComments: 'eof'`: three's `@license` headers are kept",
  '  at the end of the file.',
  "- `katex.min.js`, `katex.min.css` and `rough.js` are the packages' own builds, which carry no license",
  '  header; their notices are the files under `licenses/`.',
  '- Do not delete `licenses/` or strip the remaining headers when updating these files.',
  '',
  '## GSAP (Standard "No Charge" license)',
  '',
  'GSAP core and the DrawSVG, MorphSVG, MotionPath and SplitText plugins are distributed under the GSAP',
  'Standard "No Charge" License: https://gsap.com/standard-license',
  '',
  'Prohibited uses (Section III of the license, summarised):',
  '',
  '- Using GSAP Products in tools that let users build visual animations without code, where the tool',
  '  encourages, induces or materially assists in creating a solution that competes with Webflow\'s',
  '  visual animation building capabilities ("Prohibited Uses"), without prior written consent.',
  '- Reverse engineering GSAP Products for the purpose of creating Competitive Products.',
  '- Removing or altering proprietary notices or branding from GSAP Products.',
  '',
  'AI-generated code that calls GSAP is not a Prohibited Use. This product renders code-driven',
  'teaching videos and does not offer a visual animation builder.',
  '',
  '## Other licenses',
  '',
  '- KaTeX, three.js and Rough.js (with its bundled dependencies): MIT.',
  '- Noto Sans SC (via @fontsource) and LXGW WenKai: SIL Open Font License 1.1, full text in',
  '  `licenses/noto-sans-sc/LICENSE` and `licenses/lxgw-wenkai/OFL.txt`. Font files are shipped',
  '  unmodified (woff2 subsets) under their original family names, which the OFL permits for bundling.',
  '  The lxgw-wenkai-webfont packaging itself is MIT (`licenses/lxgw-wenkai/LICENSE`).',
  '',
];
writeFileSync(join(OUT, 'NOTICE.md'), lines.join('\n'));

// --- summary ---
let total = 0;
const walk = (d) => {
  for (const n of readdirSync(d)) {
    const p = join(d, n);
    if (statSync(p).isDirectory()) walk(p);
    else total += statSync(p).size;
  }
};
walk(OUT);
console.log(`vendor files: ${Object.keys(files).length}, total ${(total / 1048576).toFixed(2)} MiB -> ${relative(process.cwd(), OUT)}`);
if (!existsSync(join(OUT, 'three.iife.js'))) throw new Error('three.iife.js missing');
