"""Pure freshness decision used by the attention-refresh workflow verifier."""
from __future__ import annotations

from datetime import date

import pytest

from api.scripts import attention_freshness as f

TODAY = date(2026, 10, 17)


def test_same_day_rerun_passes() -> None:
    assert f.judge("wikipedia", "2026-10-15", TODAY).ok
    assert f.judge("coingecko", "2026-10-16", TODAY).ok


@pytest.mark.parametrize("src,latest,ok", [
    ("wikipedia", "2026-10-14", True),   # exactly today - 3
    ("wikipedia", "2026-10-13", False),
    ("coingecko", "2026-10-15", True),   # exactly today - 2
    ("coingecko", "2026-10-14", False),
])
def test_boundaries(src: str, latest: str, ok: bool) -> None:
    assert f.judge(src, latest, TODAY).ok is ok


def test_no_data_fails() -> None:
    v = f.judge("wikipedia", None, TODAY)
    assert not v.ok and "no data" in v.reason


def test_threshold_reported() -> None:
    assert f.judge("wikipedia", "2026-10-15", TODAY).threshold == "2026-10-14"
    assert f.judge("coingecko", "2026-10-15", TODAY).threshold == "2026-10-15"


def test_unknown_source_rejected() -> None:
    with pytest.raises(KeyError):
        f.judge("universe", "2026-10-15", TODAY)
