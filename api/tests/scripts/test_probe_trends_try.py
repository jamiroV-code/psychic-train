"""T196: probe_trends --try term groups. Fake TrendReq only: no network, no real sleeping, writes nothing."""
from __future__ import annotations

import io
import json
import math
from datetime import timedelta

import pytest

from api.data.attention import trends
from api.data.attention import trends_keywords as k
from api.scripts import probe_trends as p
from api.tests.trends_fixtures import (
    FORBIDDEN_IN_OUTPUT,
    SECRET,
    TODAY,
    FakeTrendReq,
    block_network,
    daily_frame,
    factory,
    forbidden,
    too_many,
    tree_snapshot,
)

TF = "2026-07-13 2026-10-20"  # the daily run's explicit 100-day range ending yesterday
N = trends.TRENDS_RANGE_DAYS


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    block_network(monkeypatch)


def _clock():
    ticks = iter(x * 0.25 for x in range(1000))
    return lambda: next(ticks)


def _run(frames, argv, sleeps=None, volume=None):
    client = FakeTrendReq(frames=frames)
    out, err = io.StringIO(), io.StringIO()
    sleeps = [] if sleeps is None else sleeps
    code = p.main(argv, trendreq_factory=factory(client), sleep=sleeps.append, clock=_clock(),
                  today=lambda: TODAY, version=lambda: "4.9.2", out=out, err=err, jitter=lambda: 0.5,
                  volume_reader=volume or (lambda sym, day: (None, "n/a: no stored volume")))
    return code, out.getvalue() + err.getvalue(), client


def frame(terms, values=None, **kw):
    kw.setdefault("days", N)
    return daily_frame(terms, values=values, **kw)


def rise(base, last):
    return [base] * (N - 7) + [last] * 7


# --- parsing ---

def test_try_is_repeatable_and_one_request_per_group():
    sleeps = []
    code, text, client = _run([frame(["toncoin crypto", "ton coin"]), frame(["akedo"])],
                              ["--try", "GRAM=toncoin crypto|ton coin", "--try", "AKE=akedo"], sleeps=sleeps)
    assert code == 0
    assert client.payloads == [(["toncoin crypto", "ton coin"], TF), (["akedo"], TF)]
    assert sleeps == [p.INTERVAL_SECONDS + 0.5]
    assert "group 1/2: GRAM [toncoin crypto | ton coin]" in text and "group 2/2: AKE [akedo]" in text


def test_terms_are_stripped_and_topic_ids_allowed():
    code, _, client = _run([frame(["/m/0abc12", "ether.fi"])], ["--try", "ETHFI= /m/0abc12 | ether.fi "])
    assert code == 0 and client.payloads == [(["/m/0abc12", "ether.fi"], TF)]


@pytest.mark.parametrize("argv", [
    ["--try", "GRAM=a1|a2|a3|a4|a5|a6"],                # > 5 terms
    ["--try", "GRAM="], ["--try", "GRAM=ton||coin"],     # empty term
    ["--try", "GRAM=ton;rm"], ["--try", 'GRAM=ton"x'], ["--try", "GRAM=ton\x07x"], ["--try", "GRAM=<b>"],
    ["--try", "GRAM=" + "x" * 61],                       # too long
    ["--try", "GRAM=ton|TON"],                           # duplicate term (case-insensitive)
    ["--try", "gram=ton"], ["--try", "GRAM"], ["--try", "GR/AM=ton"],
    ["--try", "GRAM=ton", "--alone", "SOL"],
    ["--try", "GRAM=ton", "--timeframe", "today 3-m"],
])
def test_bad_try_values_exit_2_before_any_request(argv):
    code, text, client = _run([frame(["x"])], argv)
    assert code == 2 and client.payloads == [] and "--" in text


def test_more_than_12_groups_exit_2():
    argv = [a for i in range(13) for a in ("--try", f"S{i}=term{i}")]
    code, text, client = _run([], argv)
    assert code == 2 and client.payloads == [] and "12" in text
    argv = argv[:24]
    code, _, client = _run([frame([f"term{i}"]) for i in range(12)], argv)
    assert code == 0 and len(client.payloads) == 12


def test_five_terms_allowed_and_bare_words_accepted():
    terms = ["pax gold", "paxos gold", "paxg", "pax+gold", "pax"]
    code, text, client = _run([frame(terms)], ["--try", "PAXG=" + "|".join(terms)])
    assert code == 0 and client.payloads[0][0] == terms
    assert "term pax+gold: not loader-safe (length or characters)" in text
    assert "term paxg: loader-valid" in text


def test_loader_valid_flag_uses_the_real_loader_check():
    _, text, _ = _run([frame(["morpho", "morpho protocol", "morpho crypto"])],
                      ["--try", "MORPHO=morpho|morpho protocol|morpho crypto"])
    # stage 2: MORPHO is on `_ambiguous`; only its approved term ("morpho crypto") is loader-valid
    assert "term morpho: needs approval (ambiguous)" in text
    assert "term morpho protocol: needs approval (ambiguous)" in text
    assert "term morpho crypto: loader-valid" in text


# --- per-group output ---

def test_group_report_lines():
    vals = {"toncoin crypto": rise(10, 14), "ton coin": rise(10, 14)}
    code, text, _ = _run([frame(list(vals), values=vals)], ["--try", "GRAM=toncoin crypto|ton coin"])
    assert code == 0
    assert "outcome: ok" in text and "latency: 0.25 s" in text
    assert "  toncoin crypto | 10 | 0% | 50%" in text
    assert ("  group | days 100 | min 20 | median 20 (own scale only) | max 28 | zero 0% | distinct 2 | verdict: ok"
            in text)
    assert ("  rising | ratio (mean, as the daily run) 1.4 | ratio (median, used for clean-rising) 1.4 | "
            "days above baseline 7/7 | one-term spike: no (largest share of the rise 50%, its baseline share 50%)"
            ) in text
    assert "correlation (7-day smoothed) vs best term" in text
    assert "  identity | n/a: no stored volume" in text and "a hint, not proof" in text
    assert "  clean rising: yes" in text


def test_clean_rising_no_lists_reasons():
    code, text, _ = _run([frame(["a b"], values={"a b": 10})], ["--try", "AKE=a b"])
    assert code == 0 and "  clean rising: no (" in text and "last7 median / prior28 median 1 < 1.1" in text


def test_identity_line_uses_the_coins_stored_volume():
    vals = [20 + 5 * math.sin(2 * math.pi * i / 20) for i in range(N)]
    end = TODAY - timedelta(days=1)
    dates = [end - timedelta(days=N - 1 - i) for i in range(N)]
    seen = []

    def volume(sym, day):
        seen.append((sym, day))
        return [(d, math.expm1(v)) for d, v in zip(dates, vals)], ""

    _, text, _ = _run([frame(["okb token"], values={"okb token": vals})], ["--try", "OKB=okb token"], volume=volume)
    assert seen == [("OKB", TODAY)]
    assert "  identity | vs log(1+stored daily volume) over 94 days: 0." in text


def test_zero_heavy_group_is_too_little_and_never_zero_filled():
    vals = {"btw": [0] * 45 + [20] * 55}
    _, text, _ = _run([frame(["btw"], values=vals)], ["--try", "BTW=btw"])
    assert "verdict: too-little-interest" in text and "zero 45%" in text and "clean rising: no" in text


def test_quiet_then_surge_reported():
    vals = {"pearl ai": [0] * 50 + [1] * 43 + [10] * 7}
    _, text, _ = _run([frame(["pearl ai"], values=vals)], ["--try", "PEARL=pearl ai"])
    assert f"verdict: {trends.QUIET_THEN_SURGE}" in text


def test_bad_frame_prints_reason_only_and_run_continues():
    code, text, client = _run([frame(["a b"], days=90), frame(["c d"])], ["--try", "AKE=a b", "--try", "BTW=c d"])
    assert code == 0 and len(client.payloads) == 2
    assert "  missing: frame rejected (rows: 90, need 100)" in text


def test_partial_row_inside_is_a_gap_and_partial_today_is_dropped():
    f = frame(["a b"])
    f.loc[f.index[50], "isPartial"] = True
    _, text, _ = _run([f], ["--try", "AKE=a b"])
    assert "missing: frame rejected (gap)" in text
    ok = frame(["a b"], days=N + 1, end=TODAY, partial_last=True)
    _, text, _ = _run([ok], ["--try", "AKE=a b"])
    assert "group | days 100" in text


def test_malformed_frame_never_raises():
    _, text, _ = _run([frame(["a b"], values={"a b": ["x"] * N})], ["--try", "AKE=a b"])
    assert "missing: frame rejected (parse-failed: TypeError)" in text


# --- breaker, exit codes ---

def test_429_stops_and_exits_4_without_retry():
    code, text, client = _run([frame(["a b"]), too_many(), frame(["e f"])],
                              ["--try", "AKE=a b", "--try", "BTW=c d", "--try", "OKB=e f"])
    assert code == p.STOPPED_EXIT == 4 and len(client.payloads) == 2
    assert "outcome: TooManyRequestsError (HTTP 429)" in text
    assert "OKB [e f]: not run (stopped after HTTP 429)" in text


def test_three_failures_in_a_row_stop():
    frames = [forbidden(), RuntimeError("x"), forbidden(), frame(["g h"])]
    argv = [a for s, t in (("A", "a b"), ("B", "c d"), ("C", "e f"), ("D", "g h")) for a in ("--try", f"{s}={t}")]
    code, text, client = _run(frames, argv)
    assert code == 4 and len(client.payloads) == 3
    assert "D [g h]: not run (stopped after 3 failed requests in a row)" in text


def test_failures_not_in_a_row_do_not_stop():
    frames = [forbidden(), forbidden(), frame(["e f"]), forbidden()]
    argv = [a for s, t in (("A", "a b"), ("B", "c d"), ("C", "e f"), ("D", "g h")) for a in ("--try", f"{s}={t}")]
    code, _, client = _run(frames, argv)
    assert code == 0 and len(client.payloads) == 4


def test_ctrl_c_prints_partial_summary_and_exits_130():
    code, text, client = _run([frame(["a b"]), KeyboardInterrupt()], ["--try", "AKE=a b", "--try", "BTW=c d",
                                                                       "--try", "OKB=e f"])
    assert code == 130 and len(client.payloads) == 2
    assert "interrupted (Ctrl-C)" in text and "ranked summary" in text


def test_client_start_failure_and_pytrends_missing_codes():
    out, err = io.StringIO(), io.StringIO()

    def _boom():
        raise ConnectionError("x " + SECRET)

    assert p.main(["--try", "AKE=akedo"], trendreq_factory=_boom, sleep=lambda s: None, out=out, err=err) == 1
    assert SECRET not in out.getvalue() + err.getvalue()


# --- output safety ---

def test_output_has_no_response_bodies_or_secrets():
    _, text, _ = _run([forbidden(), too_many()], ["--try", "AKE=a b", "--try", "BTW=c d"])
    assert "ResponseError (HTTP 403)" in text
    for bad in FORBIDDEN_IN_OUTPUT + ("body", "Traceback"):
        assert bad not in text
    _, text, _ = _run([RuntimeError("x " + SECRET)], ["--try", "AKE=a b"])
    assert SECRET not in text and "outcome: RuntimeError" in text


def test_try_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data_dir = k.KEYWORDS_PATH.parent
    before = tree_snapshot(data_dir)
    _run([frame(["a b"]), frame(["c d"])], ["--try", "AKE=a b", "--try", "AKE=c d"])
    assert tree_snapshot(data_dir) == before and list(tmp_path.iterdir()) == []


# --- summary and paste-ready JSON ---

def _summary_runs():
    clean = {"ton coin": rise(10, 14)}
    flat_high = {"toncoin": [50] * N}
    low = {"toncoin crypto": [1] * N}
    frames = [frame(list(low), values=low), frame(list(flat_high), values=flat_high), frame(list(clean), values=clean),
              forbidden()]
    # XTON: an unlisted symbol (GRAM is on `_ambiguous` since stage 2, so its unapproved terms are not loader-valid)
    argv = ["--try", "XTON=toncoin crypto", "--try", "XTON=toncoin", "--try", "XTON=ton coin",
            "--try", "MORPHO=morpho"]
    return _run(frames, argv)


def test_ranked_summary_per_symbol():
    code, text, _ = _summary_runs()
    assert code == 0
    summary = text.split("ranked summary")[1].split("paste-ready JSON")[0]
    gram = summary.split("XTON")[1].split("MORPHO")[0]
    lines = [ln.strip() for ln in gram.strip().splitlines()]
    assert lines[0].startswith("1. [ton coin] | verdict ok | clean rising yes")
    assert lines[1].startswith("2. [toncoin] | verdict ok | clean rising no | median 50")
    assert lines[2].startswith("3. [toncoin crypto] | verdict too-little-interest")
    assert "[morpho] | missing: request failed" in summary


def test_paste_ready_json_is_best_loader_valid_usable_group():
    _, text, _ = _summary_runs()
    block = text.split("paste-ready JSON")[1]
    doc = json.loads(block[block.index("{"):block.rindex("}") + 1])
    assert doc == {"XTON": {"term": "ton coin"}}   # stage 2: keyword file shape, one term
    assert "MORPHO: no loader-valid usable group" in block
    assert "informational" in text and "written nowhere" in text


def test_json_skips_groups_that_are_not_loader_valid():
    vals = {"morpho": rise(10, 14)}
    _, text, _ = _run([frame(["morpho"], values=vals)], ["--try", "MORPHO=morpho"])
    block = text.split("paste-ready JSON")[1]
    assert json.loads(block[block.index("{"):block.rindex("}") + 1]) == {}
    assert "MORPHO: no loader-valid usable group" in block


def test_json_skips_unusable_groups():
    _, text, _ = _run([frame(["akedo"], values={"akedo": 1})], ["--try", "AKE=akedo"])
    block = text.split("paste-ready JSON")[1]
    assert json.loads(block[block.index("{"):block.rindex("}") + 1]) == {}
    assert "AKE: no loader-valid usable group" in block


def test_header_and_report_say_which_ratio_is_which():
    code, text, _ = _run([frame(["a b"], values={"a b": 10})], ["--try", "AKE=a b"])
    assert code == 0 and "daily run uses the mean; clean-rising uses the median" in text
    assert "last7_vs_prior28_ratio" not in text


def test_spiky_group_shows_two_different_ratios():
    vals = [10.0] * 99 + [100.0]
    code, text, _ = _run([frame(["a b"], values={"a b": vals})], ["--try", "AKE=a b"])
    assert code == 0
    assert "ratio (mean, as the daily run) 2.29 | ratio (median, used for clean-rising) 1 |" in text
