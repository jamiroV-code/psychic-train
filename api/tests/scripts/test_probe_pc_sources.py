"""W8b: owner probe tool skeleton (parser and reporting helpers only; no network, no source modes yet)."""
from __future__ import annotations

import ast
from pathlib import Path

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
    assert probe.main(["--source", "reddit", "--symbol", "SOL", "--feed-depth"]) == 2
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
