"""Shared test fixtures.

`isolated_cache` exists because the adapter's cache-first path writes to the
real `api/data/cache/` tree. Any test that drives `fetch_ohlcv` without it
merges fixture bars into the user's live Parquet files and overwrites them —
`write_ohlcv` replaces the whole series on every call.

This is the same defect class as the RFC-005 watchlist incident (parent plan
Deviations item #1), where a router test deleted BTC from the live watchlist
because a default argument bound the real path at import time. There the
cause was path binding; here it is an unredirected module-level constant.

Opt-in rather than autouse on purpose: making it autouse across the whole
suite would silently change what every existing cache-touching test reads,
and that change has not been run. Tests that drive `fetch_ohlcv` should
request it explicitly.
"""
from __future__ import annotations

import os
os.environ.setdefault("SCREENER_REFRESH_WORKER", "0")
import pytest

from api.data import cache


@pytest.fixture
def isolated_cache(tmp_path, monkeypatch):
    """Redirect the Parquet cache root at a throwaway directory for one test.

    `cache.ohlcv_path` reads `CACHE_ROOT` at call time, so patching the module
    attribute is sufficient — no path is bound at import.
    """
    monkeypatch.setattr(cache, "CACHE_ROOT", tmp_path)
    cache.bootstrap_cache_dirs()
    return tmp_path
