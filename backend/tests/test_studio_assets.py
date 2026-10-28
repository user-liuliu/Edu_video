import hashlib
import json
import re

import pytest

from app.studio.runtime import assets


def test_manifest_covers_every_vendor_file_with_matching_hash():
    manifest = json.loads((assets.VENDOR_DIR / 'manifest.json').read_text('utf-8'))
    on_disk = {p.relative_to(assets.VENDOR_DIR).as_posix() for p in assets.VENDOR_DIR.rglob('*')
               if p.is_file() and p.name not in ('manifest.json', 'NOTICE.md')}
    assert set(manifest['files']) == on_disk
    for name, entry in manifest['files'].items():
        assert entry['sha256'] == hashlib.sha256((assets.VENDOR_DIR / name).read_bytes()).hexdigest()
        assert entry['license'] in ('GSAP-Standard-No-Charge', 'MIT', 'OFL-1.1')
        assert entry['version'] and entry['package']


def test_required_vendor_files_present_and_digest_stable():
    for name in assets.VENDOR_FILES:
        assert (assets.VENDOR_DIR / name).is_file(), name
    assert re.fullmatch(r'[0-9a-f]{64}', assets.runtime_digest())
    assert assets.runtime_digest() == assets.runtime_digest()
    assert assets.runtime_url('gsap.min.js') == f'/studio-runtime/{assets.runtime_digest()}/gsap.min.js'


def test_read_runtime_file_rejects_unknown_and_traversal():
    for bad in ('../assets.py', 'nope.js', '/etc/passwd'):
        with pytest.raises(KeyError):
            assets.read_runtime_file(bad)


LICENSE_TEXTS = {
    'licenses/gsap/GSAP-Standard-No-Charge.txt': ('gsap', 'Standard "No Charge" GSAP License'),
    'licenses/katex/LICENSE': ('katex', 'Permission is hereby granted'),
    'licenses/three/LICENSE': ('three', 'Permission is hereby granted'),
    'licenses/roughjs/LICENSE': ('roughjs', 'Permission is hereby granted'),
    'licenses/roughjs/hachure-fill/LICENSE': ('hachure-fill', 'Permission is hereby granted'),
    'licenses/roughjs/path-data-parser/LICENSE': ('path-data-parser', 'Permission is hereby granted'),
    'licenses/roughjs/points-on-curve/LICENSE': ('points-on-curve', 'Permission is hereby granted'),
    'licenses/roughjs/points-on-path/LICENSE': ('points-on-path', 'Permission is hereby granted'),
    'licenses/noto-sans-sc/LICENSE': ('@fontsource/noto-sans-sc', 'SIL OPEN FONT LICENSE'),
    'licenses/lxgw-wenkai/OFL.txt': ('lxgw-wenkai-webfont', 'SIL OPEN FONT LICENSE'),
    'licenses/lxgw-wenkai/LICENSE': ('lxgw-wenkai-webfont', 'Permission is hereby granted'),
}


def test_every_vendored_package_ships_its_license_text():
    manifest = json.loads((assets.VENDOR_DIR / 'manifest.json').read_text('utf-8'))['files']
    for name, (package, phrase) in LICENSE_TEXTS.items():
        assert name in manifest and manifest[name]['package'] == package, name
        assert phrase in (assets.VENDOR_DIR / name).read_text('utf-8'), name
    notice = (assets.VENDOR_DIR / 'NOTICE.md').read_text('utf-8')
    for name in LICENSE_TEXTS:
        assert f'`{name}`' in notice, name
    assert 'keep their original license headers' not in notice  # no longer claimed for every file


def test_three_bundle_keeps_its_license_header():
    tail = (assets.VENDOR_DIR / 'three.iife.js').read_text('utf-8')[-2000:]
    assert '@license' in tail and 'Three.js Authors' in tail and 'SPDX-License-Identifier: MIT' in tail
    head = (assets.VENDOR_DIR / 'gsap.min.js').read_text('utf-8')[:400]
    assert '@license' in head and 'standard-license' in head
