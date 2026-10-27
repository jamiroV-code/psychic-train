"""T202: trends_runs reader (both shapes), adaptive campaign depth, waking-up report, --report on a missing state.
Fake TrendReq only: no network, no real sleeping."""
from __future__ import annotations

import io
import json

import pytest

from api.scripts import probe_trends as p
from api.scripts import trends_campaign as tc
from api.tests.scripts.test_probe_trends_campaign import (
    NOW,
    ROWS,
    AutoTrendReq,
    _coin,
    _metrics,
    _report,
    sent,
)


def coin(outcome="ok", **kw):
    return {"outcome": outcome, "reason": None, "keyword_kind": "term", "median": 10, "zero_share_pct": 0,
            "last7_vs_prior28_ratio": 1.2, "attempts": 1, "retried": False, **kw}


def single(coins, started="2026-10-26T04:00:00Z"):
    return {"run_started_utc": started, "run_finished_utc": started, "pytrends_version": "4.9.2", "budget_s": 900,
            "coins": coins, "totals": {}}


def write(d, name, doc):
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(doc if isinstance(doc, str) else json.dumps(doc))


# --- reader ---

def test_reader_accepts_a_single_run(tmp_path):
    write(tmp_path, "2026-10-26.json", single({"AKE": coin("ok"), "BTW": coin("quiet-then-surge")}))
    assert tc.read_runs(tmp_path) == ({"AKE": "ok", "BTW": "quiet-then-surge"}, None)


def test_reader_uses_the_latest_run_of_a_runs_file(tmp_path):
    first = single({"AKE": coin("failed"), "BTW": coin("ok")})
    second = single({"AKE": coin("ok")}, "2026-10-26T18:00:00Z")
    write(tmp_path, "2026-10-26.json", {"runs": [first, second]})
    assert tc.read_runs(tmp_path) == ({"AKE": "ok"}, None)      # BTW is not in the latest run: not borrowed


def test_reader_uses_the_latest_file(tmp_path):
    write(tmp_path, "2026-10-25.json", single({"AKE": coin("ok")}))
    write(tmp_path, "2026-10-26.json", single({"AKE": coin("too-little-interest")}))
    write(tmp_path, "notes.json", "{not json")       # not a run file name: never "latest"
    assert tc.read_runs(tmp_path) == ({"AKE": "too-little-interest"}, None)


def test_unknown_outcome_strings_are_unknown(tmp_path):
    write(tmp_path, "2026-10-26.json", single({"AKE": coin("exploded"), "BTW": coin("capped"), "GRAM": "weird"}))
    assert tc.read_runs(tmp_path)[0] == {"AKE": "unknown", "BTW": "capped", "GRAM": "unknown"}


def test_missing_or_empty_dir_is_silent(tmp_path):
    assert tc.read_runs(tmp_path / "nope") == ({}, None)
    assert tc.read_runs(tmp_path) == ({}, None)


@pytest.mark.parametrize("body", ["{not json", "[]", "null", '{"runs": []}', '{"runs": [1]}', '{"runs": "x"}',
                                  '{"coins": []}', '{"other": 1}', '{"runs": [{"coins": {}}, {"nocoins": 1}]}',
                                  '\xff'])
def test_corrupt_or_unknown_shape_is_ignored_with_a_note(tmp_path, body):
    write(tmp_path, "2026-10-25.json", single({"AKE": coin("ok")}))
    write(tmp_path, "2026-10-26.json", body)
    outcomes, note = tc.read_runs(tmp_path)
    assert outcomes == {} and note and "2026-10-26.json" in note and "stored series" in note
    assert body[:8] not in note or body[:8] == ""       # the note never echoes file content


def test_reader_never_raises_on_odd_values(tmp_path):
    write(tmp_path, "2026-10-26.json", single({"AKE": None, "BTW": {"outcome": 5}, "GRAM": coin("ok")}))
    assert tc.read_runs(tmp_path)[0] == {"GRAM": "ok"}


def test_latest_run_outcomes_still_returns_the_plain_dict(tmp_path):
    write(tmp_path, "2026-10-26.json", single({"AKE": coin("ok")}))
    assert tc.latest_run_outcomes(tmp_path) == {"AKE": "ok"}


# --- campaign depth and notes ---

def run2(argv, client=None, eligible=("AKE", "BTW", "GRAM"), health=None, runs=None):
    client = client if client is not None else AutoTrendReq()
    out, err = io.StringIO(), io.StringIO()
    code = p.main(argv, trendreq_factory=lambda: client, sleep=lambda s: None,
                  clock=iter(x * 0.25 for x in range(10_000)).__next__, today=lambda: NOW.date(),
                  version=lambda: "4.9.2", out=out, err=err, jitter=lambda: 0.5,
                  volume_reader=lambda sym, day: (None, "n/a: no stored volume"),
                  eligible_reader=lambda: (list(eligible), ROWS), names_reader=dict,
                  health_reader=lambda km, syms: {s: (health or {}).get(s, "ok") for s in syms},
                  runs_reader=lambda: runs or ({}, None), now=lambda: NOW)
    return code, out.getvalue() + err.getvalue(), client


def test_usable_coin_gets_two_groups_weak_coin_four(tmp_path):
    code, text, client = run2(["--all-eligible", "--state", str(tmp_path / "c.json"), "--max-requests", "60"],
                              eligible=("AKE", "BTW"), health={"AKE": "ok", "BTW": "weak"})
    assert code == 0, text
    by = {"AKE": [], "BTW": []}
    for key in sent(client):
        by["AKE" if "akedo" in key or "ake" in key.split()[0] else "BTW"].append(key)
    assert len(by["AKE"]) == 2 and len(by["BTW"]) == 4
    assert any("|" in k for k in by["AKE"])             # the second group is the bundle


def test_max_groups_usable_flag(tmp_path):
    st = tmp_path / "c.json"
    _, _, client = run2(["--all-eligible", "--state", str(st), "--max-groups-usable", "1"], eligible=("AKE",))
    assert sent(client) == ["akedo crypto"]
    for bad in ("0", "3", "x"):
        code, text, _ = run2(["--all-eligible", "--state", str(tmp_path / "d.json"), "--max-groups-usable", bad])
        assert code == 2 and "--max-groups-usable" in text


def test_max_groups_per_coin_is_the_weak_ceiling_default_4(tmp_path):
    _, _, client = run2(["--all-eligible", "--state", str(tmp_path / "c.json")], eligible=("AKE",),
                        health={"AKE": "weak"})
    assert len(sent(client)) == 4
    _, _, client = run2(["--all-eligible", "--state", str(tmp_path / "e.json"), "--max-groups-per-coin", "2"],
                        eligible=("AKE",), health={"AKE": "missing"})
    assert len(sent(client)) == 2


def test_the_runs_note_is_printed_and_never_blocks(tmp_path):
    runs = ({}, "trends_runs: 2026-10-26.json ignored (unreadable); using the stored series")
    code, text, _ = run2(["--all-eligible", "--state", str(tmp_path / "c.json"), "--max-requests", "1"], runs=runs)
    assert code == 0 and runs[1] in text
    st = tmp_path / "c.json"
    code, text, _ = run2(["--report", str(st)], runs=runs)
    assert code == 0 and runs[1] in text


def test_default_runs_reader_survives_a_corrupt_cache_file(tmp_path, monkeypatch):
    from api.data import cache
    monkeypatch.setattr(cache, "CACHE_ROOT", tmp_path)
    write(tmp_path / "attention" / "trends_runs", "2026-10-26.json", "{broken")
    outcomes, note = p._runs()
    assert outcomes == {} and note and "ignored" in note


# --- report: waking up ---

def surge_metrics():
    return {**_metrics("quiet-then-surge"), "median": 3}


def test_report_labels_waking_up_and_never_switches():
    st = tc.new_state()
    _coin(st, "AKE", [(["akedo crypto"], "ok", _metrics("too-little-interest"), "loader-valid"),
                      (["ake crypto"], "ok", surge_metrics(), "loader-valid")])
    _coin(st, "BTW", [(["bitway crypto"], "ok", surge_metrics(), "loader-valid"),
                      (["btw crypto"], "ok", _metrics("too-little-interest"), "loader-valid")])
    _coin(st, "OKB", [(["okb crypto"], "ok", _metrics("too-little-interest"), "loader-valid")])
    lines, _ = _report(st, ["AKE", "BTW", "OKB"])
    assert st["coins"]["AKE"]["best_group"] == "ake crypto"          # surge beats too-little-interest
    assert st["coins"]["BTW"]["best_group"] == "bitway crypto"
    for sym in ("AKE", "BTW"):
        assert "recommend: keep watching: waking up" in lines[sym] and "switch" not in lines[sym]
        assert "quiet-then-surge (waking up)" in lines[sym]
    assert "waking up" not in lines["OKB"] and "needs owner" in lines["OKB"]
    assert "current: bitway crypto (quiet-then-surge (waking up))" in lines["BTW"] or "(waking up)" in lines["BTW"]


def test_report_never_counts_waking_up_as_passed():
    st = tc.new_state()
    _coin(st, "AKE", [(["akedo crypto"], "ok", surge_metrics(), "loader-valid")])
    _coin(st, "BTW", [(["bitway crypto"], "ok", _metrics(clean=True), "loader-valid")])
    _, text = _report(st, ["AKE", "BTW"])
    assert "usable 1" in text and "waking up 1 (shown, never counted as passed)" in text


def test_a_usable_group_still_beats_a_surge_in_the_report():
    st = tc.new_state()
    _coin(st, "AKE", [(["akedo crypto"], "ok", surge_metrics(), "loader-valid"),
                      (["ake crypto"], "ok", _metrics(), "loader-valid")])
    lines, _ = _report(st, ["AKE"])
    assert st["coins"]["AKE"]["best_group"] == "ake crypto" and "waking up" not in lines["AKE"].split("recommend")[1]


# --- --report on a missing state ---

def test_report_on_a_missing_state_says_so_and_exits_2(tmp_path):
    st = tmp_path / "missing.json"
    code, text, _ = run2(["--report", str(st)], eligible=("AKE",))
    assert code == 2 and "state file not found" in text and str(st) in text and "campaign report" not in text
    assert "|" not in text and not st.exists()
    code, text, _ = run2(["--report", "-", "--state", str(st)], eligible=("AKE",))
    assert code == 2 and "state file not found" in text and str(st) in text
