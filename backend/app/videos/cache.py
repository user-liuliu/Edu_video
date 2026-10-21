"""Content-addressed local sample cache; metadata never contains model credentials."""
import hashlib
import json
from pathlib import Path


def cache_fingerprint(inputs: dict) -> str:
    payload = json.dumps(inputs, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def read_cached_bytes(path: Path, fingerprint: str) -> bytes | None:
    try:
        metadata = json.loads(path.with_suffix(path.suffix + '.cache.json').read_text(encoding='utf-8'))
        if metadata['fingerprint'] != fingerprint:
            return None
        data = path.read_bytes()
        return data if data and hashlib.sha256(data).hexdigest() == metadata['sha256'] else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def write_cached_bytes(path: Path, data: bytes, fingerprint: str) -> None:
    path.write_bytes(data)
    path.with_suffix(path.suffix + '.cache.json').write_text(json.dumps({
        'fingerprint': fingerprint, 'sha256': hashlib.sha256(data).hexdigest(),
    }), encoding='utf-8')
