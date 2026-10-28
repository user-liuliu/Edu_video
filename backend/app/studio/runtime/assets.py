"""Offline runtime assets (vendored libs + in-house runtime scripts) for the studio pipeline.

Headless Chromium loads these from ``/studio-runtime/<digest>/<name>`` with no network
access. The digest changes whenever any file name or content changes, so URLs can be
cached forever.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

RUNTIME_DIR = Path(__file__).resolve().parent
VENDOR_DIR = RUNTIME_DIR / 'vendor'

VENDOR_FILES: tuple[str, ...] = (
    'gsap.min.js',
    'DrawSVGPlugin.min.js',
    'MorphSVGPlugin.min.js',
    'MotionPathPlugin.min.js',
    'SplitText.min.js',
    'katex.min.js',
    'katex.min.css',
    'three.iife.js',  # global: THREE
    'rough.js',  # global: rough
    'fonts.css',
)

# In-house scripts added by later tasks; listed only when they exist.
_OPTIONAL_RUNTIME_SCRIPTS: tuple[str, ...] = ('edu_motion.js', 'film_runtime.js')
_NON_RUNTIME_VENDOR_FILES = frozenset({'manifest.json', 'NOTICE.md'})


def _runtime_file_map() -> dict[str, Path]:
    files: dict[str, Path] = {}
    for path in VENDOR_DIR.rglob('*'):
        if path.is_file() and path.name not in _NON_RUNTIME_VENDOR_FILES:
            files[path.relative_to(VENDOR_DIR).as_posix()] = path
    for name in _OPTIONAL_RUNTIME_SCRIPTS:
        path = RUNTIME_DIR / name
        if path.is_file():
            files[name] = path
    return files


def runtime_files() -> list[Path]:
    """All servable runtime files, sorted by their served name."""
    files = _runtime_file_map()
    return [files[name] for name in sorted(files)]


_digest_cache: tuple[tuple, str] | None = None


def runtime_digest() -> str:
    """sha256 over every runtime file (sorted by name) hashing ``name + content``."""
    global _digest_cache
    files = _runtime_file_map()
    names = sorted(files)
    signature = tuple((n, files[n].stat().st_mtime_ns, files[n].stat().st_size) for n in names)
    if _digest_cache is not None and _digest_cache[0] == signature:
        return _digest_cache[1]
    digest = hashlib.sha256()
    for name in names:
        digest.update(name.encode('utf-8'))
        digest.update(files[name].read_bytes())
    value = digest.hexdigest()
    _digest_cache = (signature, value)
    return value


def runtime_url(name: str) -> str:
    return f'/studio-runtime/{runtime_digest()}/{name}'


def read_runtime_file(name: str) -> bytes:
    """Return the bytes of a runtime file; unknown names (incl. traversal) raise KeyError."""
    files = _runtime_file_map()
    if name not in files:
        raise KeyError(name)
    return files[name].read_bytes()
