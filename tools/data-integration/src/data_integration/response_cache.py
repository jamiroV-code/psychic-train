"""On-disk cache of successful responses (machine-local, outside the repo). Errors are never cached."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from data_integration import paths, status
from data_integration.types import FetchOutcome


class ResponseCache:
    def __init__(self, root: Path | None = None, tier: int = 1):
        self.tier = tier
        self.root = Path(root) if root is not None else paths.scrape_dir() / "responses"

    def _key(self, url: str, tier: int) -> str:
        return hashlib.sha256(f"{tier}\n{url}".encode("utf-8")).hexdigest()

    def put(self, url: str, http_status: int, body: bytes) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        key = self._key(url, self.tier)
        (self.root / f"{key}.body").write_bytes(body)
        (self.root / f"{key}.json").write_text(json.dumps({"url": url, "tier": self.tier, "http_status": http_status}), encoding="utf-8")

    def get(self, url: str) -> FetchOutcome | None:
        key = self._key(url, self.tier)
        try:
            meta = json.loads((self.root / f"{key}.json").read_text(encoding="utf-8"))
            body = (self.root / f"{key}.body").read_bytes()
            if meta["url"] != url or meta.get("tier") != self.tier or not isinstance(meta["http_status"], int):
                return None
        except (OSError, ValueError, KeyError, TypeError):
            return None
        return FetchOutcome(status.CACHE_HIT, url, meta["http_status"], body, "served from response cache",
                            hashlib.sha256(body).hexdigest())
