"""Tooling test isolation: the owner's real cache is never read or written."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# Must happen before the first `api.data.cache` import so CACHE_ROOT is never the real tree.
_BOOT_ROOT = Path(tempfile.mkdtemp(prefix="dit-cache-"))
os.environ["SCREENER_CACHE_ROOT"] = str(_BOOT_ROOT)

import pytest  # noqa: E402

from data_integration import paths  # noqa: E402

paths._repo_root()  # puts the repo root on sys.path

from api.data import cache  # noqa: E402

REAL_CACHE_DIR = cache.DEFAULT_CACHE_ROOT


def _snapshot(root: Path) -> list[tuple[str, int, int]]:
    if not root.exists():
        return []
    rows = []
    for p in sorted(root.rglob("*")):
        if p.is_file():
            st = p.stat()
            rows.append((str(p.relative_to(root)), st.st_size, st.st_mtime_ns))
    return rows


_REAL_AT_START = _snapshot(REAL_CACHE_DIR)


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_ROOT", tmp_path)
    assert Path(cache.CACHE_ROOT).resolve() != REAL_CACHE_DIR.resolve()
    return tmp_path


@pytest.fixture(scope="session", autouse=True)
def real_cache_untouched():
    yield
    assert _snapshot(REAL_CACHE_DIR) == _REAL_AT_START, "real cache tree changed during tooling tests"
    assert str(REAL_CACHE_DIR) not in {p for p in sys.path if p == str(REAL_CACHE_DIR)}
