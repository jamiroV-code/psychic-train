"""Trends probe (T100a): fake TrendReq only, no network, no real sleeping, writes nothing."""
from __future__ import annotations

import io
import sys
from importlib import metadata

import pytest

from api.data.attention import trends_keywords as k
from api.scripts import probe_trends as p
from api.scripts import trends_cli_common as common
from api.tests.trends_fixtures import (
    FORBIDDEN_IN_OUTPUT,
    SECRET,
    TODAY,
    FakeTrendReq,
    block_network,
    daily_frame,
    factory,
    forbidden,
    frame_with_today,
    too_many,
    tree_snapshot,
    weekly_frame,
)

# Default keywords come from the keyword file (topic ids since T134 seeded the owner's checker PASS entries).
_KW = k.load()
BTC, ETH, SOL, LINK, AAVE, INJ = (_KW.keyword_for(s) for s in ("BTC", "ETH", "SOL", "LINK", "AAVE", "INJ"))
R1 = [_KW.anchor_keyword(), SOL, LINK, AAVE, INJ]
R2 = [BTC, ETH, SOL, LINK, AAVE]
R3 = [BTC, ETH, INJ, _KW.keyword_for("MORPHO")]


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    block_network(monkeypatch)


def _clock():
    ticks = iter(x * 0.25 for x in range(1000))
    return lambda: next(ticks)


def _run(frames, argv=None, sleeps=None, version=lambda: "4.9.2"):
    client = FakeTrendReq(frames=frames)
    out, err = io.StringIO(), io.StringIO()
    sleeps = [] if sleeps is None else sleeps
    code = p.main(argv or [], trendreq_factory=factory(client), sleep=sleeps.append, clock=_clock(),
                  today=lambda: TODAY, version=version, out=out, err=err)
    return code, out.getvalue() + err.getvalue(), client


def test_report_has_version_outcome_latency_rows_step_complete_days():
    code, text, client = _run([daily_frame(R1)], ["--no-evidence"])
    assert code == 0
    assert client.payloads == [(R1, "today 3-m")]
    assert "pytrends version: 4.9.2" in text
    assert "outcome: ok" in text
    assert "latency: 0.25 s" in text
    assert "rows: 90" in text
    assert "index step: daily" in text
    assert "complete days: 90" in text
    assert "evidence requests: skipped (--no-evidence)" in text


def test_first_and_last_five_rows_printed():
    values = {t: list(range(i * 100, i * 100 + 90)) for i, t in enumerate(R1)}
    frame = daily_frame(R1, values={t: [v % 101 for v in vs] for t, vs in values.items()})
    _, text, _ = _run([frame], ["--no-evidence"])
    first = text.split("first 5 rows:")[1].split("last 5 rows:")[0]
    last = text.split("last 5 rows:")[1]
    dates = [d.date().isoformat() for d in frame.index]
    for d in dates[:5]:
        assert d in first
    for d in dates[-5:]:
        assert d in last
    assert dates[5] not in first and dates[-6] not in last
    assert "Bitcoin=0" in first and "partial=False" in first


def test_non_daily_frame_reported_as_non_daily_with_step():
    _, text, _ = _run([weekly_frame(R1)], ["--no-evidence"])
    assert "index step: non-daily (7..7 days)" in text


def test_partial_and_today_rows_are_not_complete_days():
    _, text, _ = _run([frame_with_today(R1)], ["--no-evidence"])
    assert "rows: 90" in text and "complete days: 89" in text
    f = daily_frame(R1)
    f.loc[f.index[-1], "isPartial"] = True
    _, text, _ = _run([f], ["--no-evidence"])
    assert "complete days: 89" in text


def test_exception_prints_class_and_status_only():
    code, text, _ = _run([forbidden()])
    assert code == 0
    assert "outcome: ResponseError (HTTP 403)" in text
    for bad in FORBIDDEN_IN_OUTPUT + ("code 403", "body"):
        assert bad not in text
    code, text, _ = _run([ConnectionError("dns " + "x")], ["--no-evidence"])
    assert "outcome: ConnectionError" in text and "dns" not in text


def test_http_429_is_reported_and_evidence_requests_are_skipped():
    code, text, client = _run([too_many(), daily_frame(R2), daily_frame(R3)])
    assert code == 0
    assert "outcome: TooManyRequestsError (HTTP 429)" in text
    assert "evidence requests: skipped after HTTP 429" in text
    assert len(client.payloads) == 1
    for bad in FORBIDDEN_IN_OUTPUT:
        assert bad not in text


def test_version_unknown_when_metadata_missing(monkeypatch):
    def _missing(name):
        raise metadata.PackageNotFoundError(name)

    monkeypatch.setattr(common.metadata, "version", _missing)
    assert common.pytrends_version() == "unknown"
    _, text, _ = _run([daily_frame(R1)], ["--no-evidence"], version=common.pytrends_version)
    assert "pytrends version: unknown" in text


def test_evidence_uses_two_requests_with_both_anchors_and_five_coins():
    code, _, client = _run([daily_frame(R1), daily_frame(R2), daily_frame(R3)])
    assert code == 0
    assert [t for t, _ in client.payloads] == [R1, R2, R3]
    _, _, client = _run([daily_frame(["Bitcoin", "Aptos"]), daily_frame(["Bitcoin", "Ethereum", "Aptos"])],
                        ["--coins", "APT", "--anchor-a", "Bitcoin", "--anchor-b", "Ethereum"])
    assert client.payloads[0][0][:2] == ["Bitcoin", "Aptos"]
    assert client.payloads[1][0][:3] == ["Bitcoin", "Ethereum", "Aptos"]


def test_evidence_prints_raw_stats_and_percent_of_each_anchor():
    vals2 = {BTC: [100] * 90, ETH: [40] * 90, SOL: [20] * 90, LINK: [1] * 89 + [50], AAVE: 0}
    _, text, _ = _run([daily_frame(R1), daily_frame(R2, values=vals2), daily_frame(R3)])
    ev = text.split("evidence request 2")[1].split("evidence request 3")[0]
    assert f"{BTC} | days 90 | min 100 | median 100 | max 100 | last 100 | at 100: 90 | at 0 or 1: 0" in ev
    assert f"{LINK} | days 90 | min 1 | median 1 | max 50 | last 50 | at 100: 0 | at 0 or 1: 89" in ev
    assert f"{SOL}: median 20% of A ({BTC}), 50% of B ({ETH})" in ev
    assert f"{AAVE}: median 0% of A ({BTC}), 0% of B ({ETH})" in ev
    assert f"A ({BTC}): a coin is above it on 0 days; every coin is at 0 or 1 on 0 days" in ev
    assert f"B ({ETH}): a coin is above it on 1 days" in ev
    assert "recommend" not in text.lower()


def test_failure_of_one_evidence_request_still_prints_the_other():
    code, text, client = _run([daily_frame(R1), forbidden(), daily_frame(R3)])
    assert code == 0 and len(client.payloads) == 3
    r2 = text.split("evidence request 2")[1].split("evidence request 3")[0]
    r3 = text.split("evidence request 3")[1]
    assert "ResponseError (HTTP 403)" in r2
    assert f"{INJ} | days 90" in r3


def test_probe_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data_dir = k.KEYWORDS_PATH.parent
    before = tree_snapshot(data_dir)
    _run([daily_frame(R1), daily_frame(R2), daily_frame(R3)])
    assert tree_snapshot(data_dir) == before
    assert list(tmp_path.iterdir()) == []


def test_sleeps_three_seconds_between_requests_and_sends_at_most_three():
    sleeps: list[float] = []
    _, _, client = _run([daily_frame(R1), daily_frame(R2), daily_frame(R3), daily_frame(R3)], sleeps=sleeps)
    assert sleeps == [3.0, 3.0] and len(client.payloads) == 3
    sleeps.clear()
    _, _, client = _run([daily_frame(R1)], ["--no-evidence"], sleeps=sleeps)
    assert sleeps == [] and len(client.payloads) == 1


@pytest.mark.parametrize("argv", [
    ["--coins", "SOL,link"], ["--coins", "SOL,LI/NK"], ["--anchor-a", "Bit,coin"], ["--anchor-b", 'Ether"um'],
    ["--anchor-a", "a/b"], ["--timeframe", "today 3-m,x"], ["--bogus"],
])
def test_unsafe_cli_values_exit_2_before_any_request(argv):
    code, _, client = _run([daily_frame(R1)], argv)
    assert code == 2 and client.payloads == []


def test_defaults_come_from_keyword_file_and_pytrends_missing_exits_3(monkeypatch):
    m = k.load()
    _, text, client = _run([daily_frame(R1), daily_frame(R2), daily_frame(R3)])
    assert client.payloads[0][0][0] == m.anchor_keyword()
    assert client.payloads[1][0][:2] == [m.keyword_for("BTC"), m.keyword_for("ETH")]
    _, text, client = _run([daily_frame(R1)], ["--coins", "ATOM,SOL", "--no-evidence"])
    assert "skip ATOM" in text and client.payloads[0][0][1] == SOL
    monkeypatch.setitem(sys.modules, "pytrends", None)
    monkeypatch.setitem(sys.modules, "pytrends.request", None)
    out, err = io.StringIO(), io.StringIO()
    assert p.main([], sleep=lambda s: None, out=out, err=err) == 3
    assert "uv run --project api --with pytrends python -m api.scripts.probe_trends" in err.getvalue()


def test_cli_modules_import_without_pytrends(monkeypatch):
    import importlib

    monkeypatch.setitem(sys.modules, "pytrends", None)
    monkeypatch.setitem(sys.modules, "pytrends.request", None)
    for name in ("api.scripts.trends_cli_common", "api.scripts.check_trends_keywords", "api.scripts.probe_trends"):
        monkeypatch.delitem(sys.modules, name, raising=False)
        importlib.import_module(name)
    fresh = sys.modules["api.scripts.trends_cli_common"]
    with pytest.raises(fresh.PytrendsMissing):
        fresh.make_trendreq()


def test_429_on_evidence_request_2_skips_request_3():
    code, text, client = _run([daily_frame(R1), too_many(), daily_frame(R3)])
    assert code == 0 and len(client.payloads) == 2
    assert "evidence request 3: skipped after HTTP 429" in text


def test_client_start_failure_exits_1_and_prints_class_only(capsys, caplog):
    planted = "HTTPSConnectionPool(host='trends.google.com', url=/?geo=US) " + SECRET

    def _boom():
        raise ConnectionError(planted)

    out, err = io.StringIO(), io.StringIO()
    assert p.main([], trendreq_factory=_boom, sleep=lambda s: None, out=out, err=err) == 1
    cap = capsys.readouterr()
    text = out.getvalue() + err.getvalue() + cap.out + cap.err + caplog.text
    assert "ConnectionError" in text
    for bad in (planted, SECRET, "trends.google.com", "Traceback", "HTTPSConnectionPool"):
        assert bad not in text
