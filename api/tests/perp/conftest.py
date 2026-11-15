"""Perp test isolation (VA-36, VA-48).

Every perp test gets one temp root: `SCREENER_CACHE_ROOT` is exactly the path
`isolated_cache` returned, so the seeder's guard and the patched
`cache.CACHE_ROOT` name the same folder. The perp variables are SET (not only
unset) so a value left in the developer's shell cannot leak in.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _perp_isolation(isolated_cache, monkeypatch):
    root = isolated_cache
    monkeypatch.setenv("SCREENER_CACHE_ROOT", str(root))
    monkeypatch.setenv("SCREENER_PERP_ROOT", str(root / "perp"))
    monkeypatch.setenv("SCREENER_PERP_LOG_PATH", str(root / "perp-local" / "confirmations.jsonl"))
    monkeypatch.delenv("SCREENER_PERP_MODEL_MODULES", raising=False)
    return root
