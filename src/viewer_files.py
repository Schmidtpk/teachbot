"""
IID-UI-CONTENT-VIEW
Serving the viewer panel's HTML files fast: compressed once, revalidated with 304.

A Quarto deck is ~7 MB (3.4 MB gzipped) and the panel's iframe is recreated every time the
panel opens. Two things made every open slow:

  * Starlette's FileResponse sends an ETag but never answers `If-None-Match` with 304 (only
    StaticFiles does), so the browser's revalidation always got the full file again;
  * Chainlit's GZipMiddleware compressed that file anew on every request (~0.4 s CPU).

Here each file is gzipped once (kept in memory, ~15 MB for the time series decks) and
`not_modified` lets the route answer a matching `If-None-Match` with an empty 304.
A file changed on disk (new mtime/size) gets a new ETag and is compressed again.
"""

import gzip
import hashlib
import threading
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PreparedFile:
    etag: str     # quoted strong ETag, from mtime + size (same idea as Starlette's)
    gzip: bytes   # the whole file, gzip-compressed


_CACHE: dict[Path, tuple[tuple[int, int], PreparedFile]] = {}
_LOCK = threading.Lock()


def prepared_file(path: Path) -> PreparedFile:
    """The ETag and gzipped bytes of `path`, compressed only on the first call (or after the
    file changed). Blocking — call it via `asyncio.to_thread` from the event loop."""
    st = path.stat()
    stamp = (st.st_mtime_ns, st.st_size)
    hit = _CACHE.get(path)
    if hit and hit[0] == stamp:
        return hit[1]
    with _LOCK:  # two first requests at once compress once
        hit = _CACHE.get(path)
        if hit and hit[0] == stamp:
            return hit[1]
        tag = hashlib.md5(f"{stamp[0]}-{stamp[1]}".encode(), usedforsecurity=False).hexdigest()
        prepared = PreparedFile(etag=f'"{tag}"', gzip=gzip.compress(path.read_bytes(), 9))
        _CACHE[path] = (stamp, prepared)
        return prepared


def not_modified(if_none_match: str | None, etag: str) -> bool:
    """True if the request's `If-None-Match` names `etag` (or is `*`). Weak tags (W/"…")
    match too — RFC 9110 uses weak comparison for If-None-Match."""
    if not if_none_match:
        return False
    tags = [t.strip() for t in if_none_match.split(",")]
    return "*" in tags or any(t.removeprefix("W/") == etag for t in tags)


def warm(paths: list[Path]) -> None:
    """Compress `paths` in a background thread so the first student does not wait for it."""
    def run() -> None:
        for p in paths:
            try:
                prepared_file(p)
            except OSError:
                pass  # the route reports a missing file when it is actually requested
    threading.Thread(target=run, name="viewer-gzip-warm", daemon=True).start()
