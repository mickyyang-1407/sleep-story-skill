#!/usr/bin/env python3
"""Content versions for the upload manifests (Codex needs to know which uploaded file changed).

file_version(path) → first 12 hex of the file's sha256, cached in .version-cache.json by (size, mtime), so the
10-minute collector only re-hashes files that were rewritten. A re-render that produces identical bytes keeps
its version, so it never triggers a re-upload.
meta_version(*parts) → 12 hex over text parts and/or file paths (title, description, tags, thumbnail, subtitles):
what YouTube lets you edit in place without a new upload.
"""
import hashlib, json, os
from pathlib import Path

CACHE = Path(__file__).resolve().parent.parent / ".version-cache.json"
_cache = None


def _load():
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(CACHE.read_text())
        except (OSError, ValueError):
            _cache = {}
    return _cache


def save():
    if _cache is not None:
        tmp = CACHE.with_suffix(".tmp")
        tmp.write_text(json.dumps(_cache, ensure_ascii=False))
        os.replace(tmp, CACHE)


def file_version(p):
    p = Path(p)
    st = p.stat()
    key, stamp = str(p.resolve()), f"{st.st_size}:{st.st_mtime_ns}"
    c = _load()
    if c.get(key, {}).get("stamp") == stamp:
        return c[key]["v"]
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for block in iter(lambda: f.read(1 << 22), b""):
            h.update(block)
    c[key] = {"stamp": stamp, "v": h.hexdigest()[:12]}
    return c[key]["v"]


def meta_version(*parts):
    h = hashlib.sha256()
    for x in parts:
        if isinstance(x, Path):
            h.update(file_version(x).encode() if x.exists() else b"-")
        else:
            h.update(json.dumps(x, ensure_ascii=False).encode())
        h.update(b"\0")
    return h.hexdigest()[:12]
