"""Stage 2 (D-30, S4): the waking-up watch list read from the daily trends_runs files. No network."""
from __future__ import annotations

import json
import os
from datetime import date, timedelta

import pytest

from api.data import cache
from api.data.attention import trends_runs as tr
from api.tests.trends_fixtures import block_network

DAY = date(2026, 10, 31)


@pytest.fixture(autouse=True)
def _env(monkeypatch, tmp_path):
    block_network(monkeypatch)
    monkeypatch.setattr(cache, "CACHE_ROOT", tmp_path)
    return tmp_path / "attention" / "trends_runs"


def put(day: date, coins: dict, *, runs=False):
    d = cache.CACHE_ROOT / "attention" / "trends_runs"
    d.mkdir(parents=True, exist_ok=True)
    recs = {s: (v if isinstance(v, dict) else {"outcome": v}) for s, v in coins.items()}
    doc = {"coins": recs}
    if runs:
        doc = {"runs": [{"coins": {}}, doc]}
    (d / f"{day.isoformat()}.json").write_text(json.dumps(doc), encoding="utf-8")


def back(n):
    return DAY - timedelta(days=n)


S = "quiet-then-surge"


def test_streak_counts_consecutive_surge_days_ending_at_the_newest_file():
    put(back(3), {"QNT": "ok", "KAS": S})
    put(back(2), {"QNT": S, "KAS": S})
    put(back(1), {"QNT": S, "KAS": "ok"})
    put(back(0), {"QNT": S, "KAS": S, "ETH": "ok"}, runs=True)
    assert tr.watch_list(DAY) == [{"symbol": "QNT", "days_held": 3}, {"symbol": "KAS", "days_held": 1}]


@pytest.mark.parametrize("neutral", ["failed", "capped", "time-budget"])
def test_transient_outcomes_neither_extend_nor_break(neutral):
    put(back(2), {"QNT": S})
    put(back(1), {"QNT": neutral})
    put(back(0), {"QNT": S})
    assert tr.watch_list(DAY) == [{"symbol": "QNT", "days_held": 2}]


def test_missing_file_date_is_neutral():
    put(back(3), {"QNT": S})
    put(back(0), {"QNT": S})
    assert tr.watch_list(DAY) == [{"symbol": "QNT", "days_held": 2}]


def test_a_different_keyword_breaks_the_streak():
    put(back(2), {"QNT": {"outcome": S, "keyword": "quant crypto"}})
    put(back(1), {"QNT": {"outcome": S, "keyword": "quant network"}})
    put(back(0), {"QNT": {"outcome": S, "keyword": "quant network"}})
    assert tr.watch_list(DAY) == [{"symbol": "QNT", "days_held": 2}]
    put(back(3), {"QNT": {"outcome": S}})          # an old file without keyword does not break it
    put(back(2), {"QNT": {"outcome": S}})
    assert tr.watch_list(DAY) == [{"symbol": "QNT", "days_held": 4}]


def test_coin_absent_from_newest_file_is_not_listed_and_leaving_drops_it():
    put(back(1), {"QNT": S})
    put(back(0), {"KAS": S})
    assert tr.watch_list(DAY) == [{"symbol": "KAS", "days_held": 1}]
    put(back(0), {"KAS": "ok"})
    assert tr.watch_list(DAY) == []


def test_corrupt_newest_file_gives_an_empty_list(_env):
    put(back(1), {"QNT": S})
    _env.joinpath(f"{DAY.isoformat()}.json").write_text("{bad", encoding="utf-8")
    assert tr.watch_list(DAY) == []
    _env.joinpath(f"{DAY.isoformat()}.json").write_text('{"x": 1}', encoding="utf-8")
    assert tr.watch_list(DAY) == []


def test_oversized_older_file_is_skipped_silently(_env, monkeypatch):
    monkeypatch.setattr(tr, "WATCH_MAX_FILE_BYTES", 200)
    put(back(1), {"QNT": {"outcome": S, "pad": "x" * 500}})
    put(back(0), {"QNT": S})
    assert tr.watch_list(DAY) == [{"symbol": "QNT", "days_held": 1}]


def test_symlink_is_skipped(_env, tmp_path):
    put(back(0), {"QNT": S})
    target = tmp_path / "elsewhere.json"
    target.write_text(json.dumps({"coins": {"QNT": {"outcome": S}}}), encoding="utf-8")
    try:
        os.symlink(target, _env / f"{back(1).isoformat()}.json")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not available")
    assert tr.watch_list(DAY) == [{"symbol": "QNT", "days_held": 1}]


def test_cap_at_30_files():
    for n in range(40):
        put(back(n), {"QNT": S})
    out = tr.watch_list(DAY)
    assert out == [{"symbol": "QNT", "days_held": tr.WATCH_MAX_FILES}] and tr.WATCH_MAX_FILES == 30
    assert isinstance(out[0]["days_held"], int)


def test_unsafe_symbols_are_filtered_and_list_is_capped(monkeypatch):
    monkeypatch.setattr(tr, "WATCH_MAX_COINS", 2)
    put(back(0), {"<script>": S, "a b": S, "AAA": S, "BBB": S, "CCC": S, "DDD": 5, "EEE": {"outcome": None}})
    out = tr.watch_list(DAY)
    assert [x["symbol"] for x in out] == ["AAA", "BBB"]


def test_files_after_the_date_and_missing_folder():
    assert tr.watch_list(DAY) == []
    put(DAY + timedelta(days=1), {"QNT": S})
    assert tr.watch_list(DAY) == []
