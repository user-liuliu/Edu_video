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
