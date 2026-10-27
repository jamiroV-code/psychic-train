"""T201: probe_trends campaign mode (--all-eligible, --state, --max-requests, --report). Fake TrendReq only: no
network, no real sleeping; the state file lives in tmp_path (outside the repo)."""
from __future__ import annotations

import io
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from api.data.attention import trends
from api.scripts import probe_trends as p
from api.scripts import trends_campaign as tc
from api.tests.trends_fixtures import (
    SECRET,
    FakeTrendReq,
    block_network,
    daily_frame,
    forbidden,
    too_many,
    tree_snapshot,
)

N = trends.TRENDS_RANGE_DAYS
NOW = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)
REPO = Path(__file__).resolve().parents[3]
ROWS = [{"symbol": s, "id": i} for s, i in
        (("AKE", "akedo"), ("BTW", "bitway"), ("GRAM", "the-open-network"), ("USDT", "tether"))]
AKE = ["akedo crypto", "ake crypto", "akedo crypto|ake crypto|akedo coin"]


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    block_network(monkeypatch)


def rise(base, last):
    return [base] * (N - 7) + [last] * 7


class AutoTrendReq(FakeTrendReq):
    """Answers every request with a daily frame for the requested terms; `script` items (exceptions or a per-term
    value dict) are used first, in order."""

    def __init__(self, script=None, values=None):
        super().__init__()
        self.script = list(script or [])
        self.values = values or {}

    def interest_over_time(self):
        terms = self.payloads[-1][0]
        item = self.script.pop(0) if self.script else None
        if isinstance(item, BaseException):
            raise item
        vals = item or {t: self.values.get(t, rise(10, 14)) for t in terms}
        return daily_frame(terms, days=N, values=vals)


def run(argv, client=None, eligible=("AKE", "BTW", "GRAM"), health=None, sleeps=None, now=NOW, factory=None):
    client = client if client is not None else AutoTrendReq()
    out, err = io.StringIO(), io.StringIO()
    sleeps = [] if sleeps is None else sleeps
    code = p.main(argv, trendreq_factory=factory or (lambda: client), sleep=sleeps.append,
                  clock=iter(x * 0.25 for x in range(10_000)).__next__, today=lambda: now.date(),
                  version=lambda: "4.9.2", out=out, err=err, jitter=lambda: 0.5,
                  volume_reader=lambda sym, day: (None, "n/a: no stored volume"),
                  eligible_reader=lambda: (list(eligible), ROWS), names_reader=dict,
                  health_reader=lambda km, syms: {s: (health or {}).get(s, "weak") for s in syms}, now=lambda: now)
    return code, out.getvalue() + err.getvalue(), client


def sent(client):
    return ["|".join(terms) for terms, _ in client.payloads]


def state_of(path):
    return json.loads(Path(path).read_text())


def no_client():
    raise AssertionError("a Trends client was started")


# --- candidates and selection ---

def test_all_eligible_tests_eligible_coins_only_and_records_state(tmp_path):
    st = tmp_path / "c.json"
    code, text, client = run(["--all-eligible", "--state", str(st), "--max-groups-per-coin", "1"])
    assert code == 0, text
    assert sent(client) == ["akedo crypto", "bitway crypto", "the open network toncoin"]
    assert "tether" not in text.lower() and "USDT" not in text
    doc = state_of(st)
    rec = doc["coins"]["AKE"]["groups"]["akedo crypto"]
    assert rec["terms"] == ["akedo crypto"] and rec["kind"] == "baseline" and rec["outcome"] == "ok"
    assert rec["tested_at"] == NOW.isoformat() and rec["tester_version"] == tc.TESTER_VERSION
    assert rec["metrics"]["verdict"] == "ok" and rec["loader_flags"] == {"akedo crypto": "loader-valid"}
    assert doc["coins"]["AKE"]["best_group"] == "akedo crypto" and doc["coins"]["AKE"]["verdict"] == "ok"
    assert doc["coins"]["AKE"]["last_tested"] == NOW.isoformat()


def test_default_depth_weak_coin_four_groups_usable_coin_two(tmp_path):
    code, _, client = run(["--all-eligible", "--state", str(tmp_path / "c.json")], eligible=("AKE",),
                          health={"AKE": "weak"})
    assert code == 0 and sent(client) == [AKE[0], AKE[1], "akedo", "AKE"]
    code, _, client = run(["--all-eligible", "--state", str(tmp_path / "d.json")], eligible=("AKE",),
                          health={"AKE": "ok"})
    assert code == 0 and sent(client) == [AKE[0], AKE[2]]


def test_priority_weak_missing_empty_first_then_universe_order(tmp_path):
    health = {"AKE": "ok", "BTW": "weak", "GRAM": "missing"}
    _, _, client = run(["--all-eligible", "--state", str(tmp_path / "c.json"), "--max-groups-per-coin", "1"],
                       health=health)
    assert sent(client) == ["bitway crypto", "the open network toncoin", "akedo crypto", AKE[2]]
    assert tc.priority_order(["A", "B", "C", "D"], {"A": "ok", "B": "empty", "C": "ok", "D": "weak"}) == \
        ["B", "D", "A", "C"]


def test_keyword_health_from_runs_then_stored_series():
    from api.data.attention import trends_keywords as tk
    km = tk.load()
    good, low = [10.0] * N, [0.0] * N
    reader = {"AKE": good, "BTW": low, "OKB": []}.get
    h = tc.keyword_health(km, ["AKE", "BTW", "OKB", "NOPE", "GRAM"], {"GRAM": "too-little-interest"},
                          lambda s: reader(s, good))
    assert h == {"AKE": "ok", "BTW": "weak", "OKB": "empty", "NOPE": "missing", "GRAM": "weak"}
    assert tc.keyword_health(km, ["AKE"], {"AKE": "ok"}, lambda s: low) == {"AKE": "ok"}


def test_latest_run_outcomes_read_the_newest_file(tmp_path):
    assert tc.latest_run_outcomes(tmp_path / "missing") == {}
    d = tmp_path / "trends_runs"
    d.mkdir()
    (d / "2026-10-19.json").write_text(json.dumps({"coins": {"AKE": {"outcome": "too-little-interest"}}}))
    (d / "2026-10-20.json").write_text(json.dumps({"coins": {"AKE": {"outcome": "ok"}, "BTW": "rate-limited"}}))
    assert tc.latest_run_outcomes(d) == {"AKE": "ok", "BTW": "unknown"}
    (d / "2026-10-21.json").write_text("{not json")
    assert tc.latest_run_outcomes(d) == {}   # unreadable newest file: fall back to the stored series stats


# --- caps, pacing, breaker ---

def test_max_requests_cap_and_resume(tmp_path):
    st = tmp_path / "c.json"
    code, text, c1 = run(["--all-eligible", "--state", str(st), "--max-requests", "4", "--max-groups-per-coin", "3"])
    assert code == 0 and len(c1.payloads) == 4
    assert "5 candidate group(s) left" in text and "run the same command again" in text
    code, text, c2 = run(["--all-eligible", "--state", str(st), "--max-requests", "40", "--max-groups-per-coin", "3"])
    assert code == 0 and len(c2.payloads) == 5
    assert not set(sent(c1)) & set(sent(c2))
    assert "every candidate group of every eligible coin is tested" in text
    code, text, _ = run(["--all-eligible", "--state", str(st), "--max-groups-per-coin", "3"], factory=no_client)
    assert code == 0 and "nothing to test" in text


@pytest.mark.parametrize("n", ["0", "61", "-1", "x"])
def test_max_requests_hard_max(tmp_path, n):
    code, text, _ = run(["--all-eligible", "--state", str(tmp_path / "c.json"), "--max-requests", n],
                        factory=no_client)
    assert code == 2 and "60" in text
    assert not (tmp_path / "c.json").exists()


def test_default_max_requests_is_40_with_spacing_and_pause(tmp_path):
    many = [f"C{i}" for i in range(20)]
    sleeps: list = []
    code, _, client = run(["--all-eligible", "--state", str(tmp_path / "c.json")], eligible=many, sleeps=sleeps)
    assert code == 0 and len(client.payloads) == p.CAMPAIGN_DEFAULT_REQUESTS == 40
    assert sleeps == [p.INTERVAL_SECONDS + 0.5] * 39
    sleeps.clear()
    _, _, client = run(["--all-eligible", "--state", str(tmp_path / "d.json"), "--max-requests", "60"],
                       eligible=many, sleeps=sleeps)
    assert len(client.payloads) == 60
    assert sleeps.count(p.CAMPAIGN_PAUSE_SECONDS) == 1 and sleeps.index(p.CAMPAIGN_PAUSE_SECONDS) == 39
    assert p.CAMPAIGN_PAUSE_EVERY == 40 and p.CAMPAIGN_PAUSE_SECONDS == 20


def test_429_stops_exit_4_and_rerun_continues_where_it_stopped(tmp_path):
    st = tmp_path / "c.json"
    code, text, c1 = run(["--all-eligible", "--state", str(st), "--max-groups-per-coin", "3"], client=AutoTrendReq([None, None, too_many()]),
                         eligible=("AKE", "BTW"))
    assert code == p.STOPPED_EXIT == 4 and len(c1.payloads) == 3
    assert "stopped after HTTP 429" in text and SECRET not in text
    rec = state_of(st)["coins"]["AKE"]["groups"]["akedo"]
    assert rec["outcome"].startswith("request-failed: TooManyRequestsError (HTTP 429)") and rec["metrics"] is None
    code, _, c2 = run(["--all-eligible", "--state", str(st), "--max-groups-per-coin", "3"], eligible=("AKE", "BTW"))
    assert code == 0 and sent(c2) == ["akedo", "bitway crypto", "btw crypto", "bitway"]


def test_three_failures_in_a_row_stop(tmp_path):
    script = [forbidden(), forbidden(), forbidden()]
    code, text, c = run(["--all-eligible", "--state", str(tmp_path / "c.json")], client=AutoTrendReq(script))
    assert code == 4 and len(c.payloads) == 3 and "3 failed requests in a row" in text


def test_ctrl_c_saves_completed_groups_and_exits_130(tmp_path):
    st = tmp_path / "c.json"
    code, _, _ = run(["--all-eligible", "--state", str(st)], client=AutoTrendReq([None, KeyboardInterrupt()]))
    assert code == 130
    groups = state_of(st)["coins"]["AKE"]["groups"]
    assert list(groups) == ["akedo crypto"] and groups["akedo crypto"]["outcome"] == "ok"


def test_frame_rejected_is_recorded_as_tested(tmp_path):
    st = tmp_path / "c.json"
    short = {"akedo crypto": [5] * 90}
    client = AutoTrendReq()
    client.interest_over_time = lambda: daily_frame(["akedo crypto"], days=90, values=short)
    run(["--all-eligible", "--state", str(st), "--max-requests", "1"], client=client, eligible=("AKE",))
    rec = state_of(st)["coins"]["AKE"]["groups"]["akedo crypto"]
    assert rec["outcome"] == "frame-rejected: rows: 90, need 100" and rec["metrics"] is None
    _, _, c2 = run(["--all-eligible", "--state", str(st), "--max-requests", "1"], eligible=("AKE",))
    assert sent(c2) == ["ake crypto"]


# --- freshness ---

def test_max_age_skips_recent_and_retests_old(tmp_path):
    st = tmp_path / "c.json"
    run(["--all-eligible", "--state", str(st), "--max-groups-per-coin", "1"], eligible=("AKE",))
    _, text, c = run(["--all-eligible", "--state", str(st), "--max-groups-per-coin", "1"], eligible=("AKE",),
                     now=NOW + timedelta(days=13), factory=no_client)
    assert "nothing to test" in text
    _, _, c = run(["--all-eligible", "--state", str(st), "--max-groups-per-coin", "1"], eligible=("AKE",),
                  now=NOW + timedelta(days=14))
    assert sent(c) == ["akedo crypto"]
    _, _, c = run(["--all-eligible", "--state", str(st), "--max-groups-per-coin", "1", "--max-age-days", "0"],
                  eligible=("AKE",), now=NOW + timedelta(days=14))
    assert sent(c) == ["akedo crypto"]


def test_eligible_set_change_between_runs(tmp_path):
    st = tmp_path / "c.json"
    run(["--all-eligible", "--state", str(st), "--max-groups-per-coin", "1"], eligible=("AKE", "BTW"))
    _, _, c = run(["--all-eligible", "--state", str(st), "--max-groups-per-coin", "1"], eligible=("AKE", "GRAM"))
    assert sent(c) == ["the open network toncoin"]
    code, text, _ = run(["--report", str(st)], eligible=("AKE", "GRAM"), factory=no_client)
    assert code == 0
    assert "BTW" in text and "no longer eligible" in text.split("BTW")[-2] + text.split("BTW")[-1]


def test_no_eligible_coins_refuses(tmp_path):
    code, text, _ = run(["--all-eligible", "--state", str(tmp_path / "c.json")], eligible=(), factory=no_client)
    assert code == 2 and "no eligible coins" in text


# --- state file safety ---

@pytest.mark.parametrize("body", ["{not json", "[]", '{"version": 1}', '{"version": 99, "coins": {}}',
                                  '{"version": 1, "coins": {"AKE": {"groups": {"x": {"terms": "x"}}}}}',
                                  ('{"version": 1, "coins": {"AKE": {"groups": {"x": {"terms": "x", "outcome": "ok", '
                                   '"metrics": null, "tested_at": "2026-10-21T12:00:00+00:00"}}}}}')])
def test_corrupt_state_refused_and_never_overwritten(tmp_path, body):
    st = tmp_path / "c.json"
    st.write_text(body)
    for argv in (["--all-eligible", "--state", str(st)], ["--report", str(st)]):
        code, text, _ = run(argv, factory=no_client)
        assert code == 2 and "not a valid campaign state" in text and "left untouched" in text
        assert st.read_text() == body


def test_missing_state_report_refuses_campaign_starts_new(tmp_path):
    st = tmp_path / "c.json"
    code, text, _ = run(["--report", str(st)], factory=no_client)
    assert code == 2 and "state file not found" in text and not st.exists()
    code, text, _ = run(["--all-eligible", "--state", str(st), "--max-requests", "1"])
    assert code == 0 and "new campaign" in text and st.exists()
    missing_dir = tmp_path / "nope" / "c.json"
    code, text, _ = run(["--all-eligible", "--state", str(missing_dir)], factory=no_client)
    assert code == 2 and "folder" in text and not missing_dir.exists()


@pytest.mark.parametrize("rel", ["api/data/cache/attention/trends_campaign.json", "api/data/c.json",
                                 "process/c.json", "c.json"])
def test_state_path_inside_the_repo_is_refused(rel):
    target = REPO / rel
    assert not target.exists()
    for argv in (["--all-eligible", "--state", str(target)], ["--report", str(target)]):
        code, text, _ = run(argv, factory=no_client)
        assert code == 2 and "inside the repository" in text
    assert not target.exists()


def test_default_state_path_is_outside_the_repo():
    path = tc.default_state_path()
    assert path.name == "trends_campaign.json"
    assert REPO not in path.resolve().parents


def test_atomic_write_crash_leaves_the_old_file(tmp_path, monkeypatch):
    st = tmp_path / "c.json"
    old = tc.new_state()
    tc.save_state(st, old)
    before = st.read_bytes()

    def crash(*_a, **_k):
        raise OSError("disk full")

    monkeypatch.setattr(tc.os, "replace", crash)
    new = tc.new_state()
    new["coins"]["AKE"] = {"groups": {}, "last_tested": None, "best_group": None, "verdict": None}
    with pytest.raises(OSError):
        tc.save_state(st, new)
    assert st.read_bytes() == before
    assert sorted(x.name for x in tmp_path.iterdir()) == ["c.json"]


def test_state_holds_terms_metrics_outcomes_only(tmp_path):
    st = tmp_path / "c.json"
    run(["--all-eligible", "--state", str(st)], client=AutoTrendReq([None, forbidden()]), eligible=("AKE",))
    text = st.read_text()
    assert SECRET not in text and "Cookie" not in text and "body" not in text
    doc = json.loads(text)
    assert set(doc) == {"version", "tester_version", "coins"}
    for rec in doc["coins"]["AKE"]["groups"].values():
        assert set(rec) == {"terms", "kind", "note", "loader_flags", "outcome", "metrics", "tested_at",
                            "tester_version"}


def test_campaign_writes_only_the_state_file(tmp_path):
    roots = [REPO / "api" / "data", REPO / "process"]
    before = tree_snapshot(*roots)
    run(["--all-eligible", "--state", str(tmp_path / "c.json")])
    assert tree_snapshot(*roots) == before
    assert [x.name for x in tmp_path.iterdir()] == ["c.json"]


# --- report ---

def _state_with_results(tmp_path):
    st = tmp_path / "c.json"
    vals = {
        # AKE: the current term is clean and rising -> keep
        "akedo crypto": rise(10, 14),
        # BTW: the current term is too little interest, a variant is clean -> switch
        "bitway crypto": [1] * N, "btw crypto": rise(10, 14),
        "bitway crypto|btw crypto|bitway coin": None,
    }
    client = AutoTrendReq(values=vals)
    run(["--all-eligible", "--state", str(st), "--max-groups-per-coin", "2"], client=client, eligible=("AKE", "BTW"))
    # GRAM: nothing usable -> needs owner
    gram = AutoTrendReq(values={"the open network toncoin": [0] * N, "the open network": [1] * N})
    run(["--all-eligible", "--state", str(st), "--max-groups-per-coin", "2"], client=gram,
        eligible=("AKE", "BTW", "GRAM"))
    return st


def test_report_sends_no_request_and_recommends(tmp_path):
    st = _state_with_results(tmp_path)
    code, text, _ = run(["--report", str(st)], eligible=("AKE", "BTW", "GRAM", "OKB"), factory=no_client)
    assert code == 0, text
    lines = {ln.split(" | ")[0].strip(): ln for ln in text.splitlines() if " | " in ln}
    assert "recommend: keep" in lines["AKE"] and "clean rising yes" in lines["AKE"]
    assert "recommend: switch to [btw crypto]" in lines["BTW"]
    assert "current: bitway crypto (too-little-interest)" in lines["BTW"]
    assert "recommend: needs owner" in lines["GRAM"]
    assert "tested 3 of 4 eligible coins" in text
    untested = text.split("untested")[1]
    assert "OKB" in untested
    assert "OKB" not in lines or "passed" not in lines["OKB"] and "keep" not in lines["OKB"]
    assert "own scale only" in text
    assert "stage 2" in text and "keyword tested" in text and "last_tested" in text


def test_report_dash_uses_the_state_flag(tmp_path):
    st = _state_with_results(tmp_path)
    code, text, _ = run(["--report", "-", "--state", str(st)], eligible=("AKE",), factory=no_client)
    assert code == 0 and "tested 1 of 1 eligible coins" in text
    assert "BTW" in text and "no longer eligible" in text


def test_report_with_client_that_raises_never_touches_google(tmp_path, monkeypatch):
    st = _state_with_results(tmp_path)
    monkeypatch.setattr(p, "start_client", lambda *a, **k: (_ for _ in ()).throw(AssertionError("client")))
    code, _, _ = run(["--report", str(st)], factory=no_client)
    assert code == 0


# --- argument rules ---

@pytest.mark.parametrize("argv", [
    ["--all-eligible", "--try", "AKE=akedo"],
    ["--all-eligible", "--alone", "AKE"],
    ["--all-eligible", "--report", "-"],
    ["--report", "-", "--try", "AKE=akedo"],
    ["--state", "x.json"],
    ["--max-requests", "5"],
    ["--all-eligible", "--max-groups-per-coin", "0"],
    ["--all-eligible", "--max-groups-per-coin", "7"],
    ["--all-eligible", "--max-age-days", "-1"],
    ["--all-eligible", "--timeframe", "today 3-m"],
])
def test_bad_campaign_arguments_exit_2(argv):
    code, _, _ = run(argv, factory=no_client)
    assert code == 2


# --- round 2 decisions visible in --try output ---

def test_try_output_labels_json_as_stage_2_and_medians_own_scale():
    client = AutoTrendReq()
    code, text, _ = run(["--try", "AKE=akedo crypto"], client=client)
    assert code == 0
    assert "stage-2 shape, not accepted by the loader yet" in text
    assert "own scale only" in text
    assert "never compared across groups" in text


def test_failures_not_in_a_row_do_not_stop(tmp_path):
    script = [forbidden(), forbidden(), None, forbidden(), forbidden()]
    code, _, c = run(["--all-eligible", "--state", str(tmp_path / "c.json"), "--max-requests", "6"],
                     client=AutoTrendReq(script))
    assert code == 0 and len(c.payloads) == 6


@pytest.mark.parametrize("extra", [["--all-eligible"], ["--state", "OTHER"]])
def test_report_with_an_existing_state_still_refuses_bad_combinations(tmp_path, extra):
    st = tmp_path / "c.json"
    tc.save_state(st, tc.new_state())
    argv = ["--report", str(st)] + [str(st) if x == "OTHER" else x for x in extra]
    code, text, _ = run(argv, factory=no_client)
    assert code == 2 and "campaign report" not in text


def _metrics(verdict="ok", clean=False):
    return {"verdict": verdict, "clean": clean, "zero_pct": 0, "distinct": 5, "identity_corr": None,
            "identity_reason": "n/a: no stored volume", "median": 10}


def _coin(state, sym, groups):
    from api.data.attention import trends_candidates as tcand
    for terms, outcome, metrics, flag in groups:
        cand = tcand.Candidate(tuple(terms), "variant")
        tc.record(state, sym, cand, {t: flag for t in terms}, outcome, metrics, NOW)


def _report(state, eligible):
    from api.data.attention import trends_keywords as tk
    lines = tc.report_lines(state, eligible, tk.load(), {})
    return {ln.split(" | ")[0]: ln for ln in lines if " | " in ln}, "\n".join(lines)


def test_report_switch_rules():
    st = tc.new_state()
    # baseline usable but not clean, a loader-valid variant is clean -> switch
    _coin(st, "AKE", [(["akedo crypto"], "ok", _metrics(), "loader-valid"),
                      (["ake crypto"], "ok", _metrics(clean=True), "loader-valid")])
    # the clean group is not loader-valid and the baseline is usable -> keep
    _coin(st, "BTW", [(["bitway crypto"], "ok", _metrics(), "loader-valid"),
                      (["bitway"], "ok", _metrics(clean=True), "needs qualifier word")])
    # the baseline is unusable and the only usable group is not loader-valid -> needs owner
    _coin(st, "OKB", [(["okb crypto"], "ok", _metrics("too-little-interest"), "loader-valid"),
                      (["okb"], "ok", _metrics(), "needs qualifier word")])
    lines, _ = _report(st, ["AKE", "BTW", "OKB"])
    assert "recommend: switch to [ake crypto]" in lines["AKE"]
    assert "recommend: keep" in lines["BTW"]
    assert "recommend: needs owner (best usable group is not loader-valid)" in lines["OKB"]


def test_failed_requests_only_are_untested_and_set_no_last_tested():
    st = tc.new_state()
    _coin(st, "AKE", [(["akedo crypto"], "request-failed: ResponseError (HTTP 403)", None, "loader-valid")])
    assert st["coins"]["AKE"]["last_tested"] is None
    _coin(st, "BTW", [(["bitway crypto"], "frame-rejected: gap", None, "loader-valid")])
    assert st["coins"]["BTW"]["last_tested"] == NOW.isoformat()
    lines, text = _report(st, ["AKE", "BTW"])
    assert "AKE" not in lines and "AKE" in text.split("untested")[1]
    assert "tested 1 of 2 eligible coins" in text and "needs owner" in lines["BTW"]
