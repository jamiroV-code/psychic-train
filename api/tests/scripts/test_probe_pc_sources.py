"""W8b/W8c: owner probe tool (parser, reporting helpers, Reddit modes on fake clients; no network)."""
from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from api.data.attention import pc_adapter as pa
from api.scripts import probe_pc_sources as probe

SCRIPT = Path(probe.__file__)
SECRET = "cookie=sessid-PLANTED-c00k1e&q=PLANTED"


def test_parser_accepts_documented_modes():
    a = probe.build_parser().parse_args(["--source", "reddit", "--symbol", "sol", "--feed-depth"])
    assert a.source == "reddit" and a.symbol == "SOL" and a.feed_depth
    b = probe.build_parser().parse_args(["--source", "reddit", "--symbol", "SOL", "--compare-scope"])
    assert b.compare_scope
    c = probe.build_parser().parse_args(["--source", "reddit", "--stream-status"])
    assert c.stream_status and c.symbol is None
    d = probe.build_parser().parse_args(["--source", "x", "--symbol", "BTC"])
    assert d.source == "x"


def test_parser_rejects_unknown_source_and_bad_symbol():
    with pytest.raises(SystemExit):
        probe.build_parser().parse_args(["--source", "telegram"])
    with pytest.raises(SystemExit):
        probe.build_parser().parse_args(["--source", "x", "--symbol", "../etc"])


def test_modes_not_built_in_w8b_exit_2_without_network(capsys):
    assert probe.main(["--source", "reddit"]) == 2
    assert probe.main(["--source", "x", "--symbol", "SOL"]) == 2
    out = capsys.readouterr().out
    assert "not built yet" in out


def test_report_line_prints_numbers_and_statuses_only():
    line = probe.report_line("feed", entries=25, status=200, newest_age_h=1.5, ok=True)
    assert line == "feed entries=25 status=200 newest_age_h=1.5 ok=true"
    with pytest.raises(TypeError):
        probe.report_line("feed", url="https://example.invalid/?q=x")
    with pytest.raises(ValueError):
        probe.report_line("bad label!", entries=1)


def test_report_error_prints_class_and_status_only(capsys):
    probe.report_error("feed", ValueError(SECRET), status=403)
    probe.report_error("feed", pa.RedditBlocked(403))
    out = capsys.readouterr().out
    assert "PLANTED" not in out and "cookie" not in out
    assert "feed error=ValueError status=403" in out and "feed error=RedditBlocked status=403" in out


def test_probe_script_imports_no_network_module():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module)
    banned = ("requests", "httpx", "socket", "urllib", "playwright", "http.client")
    assert not [m for m in mods if any(m == b or m.startswith(b + ".") for b in banned)]


# --- W8c Reddit modes (P-R2 feed depth, P-R5 compare scope); fake clients only ---

NOW = datetime(2026, 10, 27, 10, 0, tzinfo=timezone.utc)


def _feed(hours_back: list[float]) -> bytes:
    entries = "".join(
        f'<entry><author><name>/u/PlantedUser</name></author><category term="CryptoCurrency"/>'
        f'<id>t3_{i + 1:x}</id><title>Solana</title><updated>{(NOW - timedelta(hours=h)).isoformat()}</updated></entry>'
        for i, h in enumerate(hours_back))
    return f'<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">{entries}</feed>'.encode()


def _client(respond, seen):
    def handler(req):
        seen.append(req)
        return respond(req)
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_reddit_feed_depth_prints_counts_and_statuses_only(capsys):
    seen = []
    body = _feed([1, 5, 12, 20, 30, 40])  # yesterday (26 Oct) holds the entries 12, 20 and 30 h back
    client = _client(lambda req: httpx.Response(200, content=body, headers={"content-type": "application/atom+xml"}),
                     seen)
    code = probe.main(["--source", "reddit", "--symbol", "SOL", "--feed-depth"], client=client, clock=lambda: NOW,
                      sleep=lambda s: None)
    out = capsys.readouterr().out
    assert code == 0 and len(seen) == 1
    assert "feed status=200 entries=6 newest_age_h=1 oldest_age_h=40 span_h=39 reaches_window_start=true" in out
    assert "yesterday_entries=3" in out
    for leak in ("reddit.com", "Solana", "PlantedUser", "search.rss", "attention-probe"):
        assert leak not in out


def test_reddit_compare_scope_two_requests_a_minute_apart(capsys):
    seen, waits = [], []
    client = _client(lambda req: httpx.Response(200, content=_feed([1, 2, 30])), seen)
    code = probe.main(["--source", "reddit", "--symbol", "SOL", "--compare-scope"], client=client, clock=lambda: NOW,
                      sleep=waits.append)
    out = capsys.readouterr().out
    assert code == 0 and len(seen) == 2 and waits and min(waits) >= 60
    assert "/r/CryptoCurrency/search.rss" == seen[1].url.path and "+" in seen[0].url.path
    assert "scope_set status=200 entries=3" in out and "scope_one status=200 entries=3" in out
    assert "reddit.com" not in out


def test_reddit_probe_block_prints_class_and_status(capsys):
    seen = []
    client = _client(lambda req: httpx.Response(403, content=SECRET.encode()), seen)
    code = probe.main(["--source", "reddit", "--symbol", "SOL", "--feed-depth"], client=client, clock=lambda: NOW,
                      sleep=lambda s: None)
    out = capsys.readouterr().out
    assert code == 0 and "feed error=RedditBlocked status=403" in out and "PLANTED" not in out


def test_reddit_probe_needs_a_collectable_symbol(capsys):
    seen = []
    client = _client(lambda req: httpx.Response(200, content=_feed([1])), seen)
    assert probe.main(["--source", "reddit", "--feed-depth"], client=client) == 2
    assert probe.main(["--source", "reddit", "--symbol", "SKY", "--feed-depth"], client=client) == 2
    assert seen == []
    assert "ambiguous" in capsys.readouterr().out


# --- W8c2 `--stream-status` (local state only, numbers only) ---

def test_reddit_stream_status_reads_local_state_only(capsys, isolated_cache):
    from datetime import date

    from api.data.attention import reddit_stream as rs

    d = date(2026, 10, 26)
    rs.append_poll(rs.Poll("comments", NOW - timedelta(hours=1), NOW - timedelta(hours=1, minutes=1),
                           NOW - timedelta(hours=16), 100, 1, False))
    seen = []
    client = _client(lambda req: httpx.Response(200, content=_feed([1])), seen)
    code = probe.main(["--source", "reddit", "--stream-status"], client=client, clock=lambda: NOW,
                      sleep=lambda s: None)
    out = capsys.readouterr().out
    assert code == 0 and seen == []
    assert "stream_today polls_comments=1 polls_new=0" in out
    assert f"stream_day day={d.strftime('%Y%m%d')}" in out and "coverage_comments=" in out
    assert "PLANTED" not in out


def test_reddit_stream_status_coverage_none_for_days_without_polls(capsys, isolated_cache):
    """A day no poll reached has unknown coverage: printed `none`, never 0; coverage is per feed kind only."""
    from api.data.attention import reddit_stream as rs

    rs.append_poll(rs.Poll("comments", NOW - timedelta(hours=1), NOW - timedelta(hours=1, minutes=1),
                           NOW - timedelta(hours=16), 100, 1, False))
    assert probe.main(["--source", "reddit", "--stream-status"], clock=lambda: NOW, sleep=lambda s: None) == 0
    lines = [ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("stream_day ")]
    assert len(lines) == 3
    by_day = {ln.split()[1]: ln for ln in lines}
    assert "coverage_comments=none" not in by_day["day=20261026"] and "coverage_new=none" in by_day["day=20261026"]
    for day in ("day=20261025", "day=20261024"):
        assert "coverage_comments=none coverage_new=none" in by_day[day]
    assert all("coverage_comments=0 " not in ln and "subreddit" not in ln for ln in lines)
