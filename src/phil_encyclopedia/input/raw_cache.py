from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from pathlib import Path

from .sep_urls import sep_slug


@dataclass(frozen=True)
class CachedSource:
    path: Path
    content_hash: str


class RawCache:
    def __init__(self, root: Path, retention_days: int) -> None:
        self.root = root
        self.retention_days = retention_days

    def put(self, sep_url: str, html: str) -> CachedSource:
        slug = sep_slug(sep_url)
        path = self.root / f"{slug.replace('/', '__')}.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
        return CachedSource(path=path, content_hash=hashlib.sha256(html.encode("utf-8")).hexdigest())

    def purge_expired(self) -> int:
        if not self.root.exists():
            return 0
        cutoff = time.time() - self.retention_days * 86400
        purged = 0
        for path in self.root.glob("*.html"):
            if path.stat().st_mtime < cutoff:
                path.unlink()
                purged += 1
        return purged
