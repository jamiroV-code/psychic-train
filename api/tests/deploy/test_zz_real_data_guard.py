"""Isolation guard added at VALIDATE (P2, E2): after every other test in this
package has run (this module sorts last), the real `api/data/watchlist.json`
and `api/data/cache/` tree are byte-size- and mtime-identical to when the
package started. The package-scoped fixture in conftest.py re-checks the same
thing at teardown."""
from __future__ import annotations

import pytest

from api.tests.deploy.conftest import REAL_CACHE_DIR, REAL_DATA_AT_START, REAL_WATCHLIST, snapshot_real_data


def test_real_data_paths_untouched():
    if not REAL_CACHE_DIR.exists() and not REAL_WATCHLIST.exists():
        pytest.skip("no real cache or watchlist on this checkout")
    assert snapshot_real_data() == REAL_DATA_AT_START
