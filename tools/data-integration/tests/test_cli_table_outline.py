"""AC-39: the table outline through the CLI and the real pipeline. Fake registry, no network."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from data_integration import cli, paths, parse, status
from data_integration.approvals import ApprovalStore
from data_integration.types import FetchOutcome

from _helpers import fixed_clock, make_record

FIX = Path(__file__).parent / "fixtures"
FIXT = Path(__file__).parent / "fixtures_table_outline"
URL = "https://example.test/data/prices.html"
SRC = "example-src"
OK_BODY = (FIX / "ok.html").read_bytes()
BASIC = (FIXT / "basic.html").read_bytes()
HEADER = "table outline (nothing stored, only header names are shown):"
PAGE_HEADER = "page outline (nothing stored, page text is not shown):"


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    for name, leaf in (("DIT_APPROVALS_DIR", "appr"), ("DIT_SCRAPE_DIR", "scrape"), ("DIT_EVIDENCE_DIR", "evid")):
        monkeypatch.setenv(name, str(tmp_path / "dit" / leaf))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "lad"))
    return tmp_path


class Reg:
    def __init__(self, body=BASIC):
        self.body, self.calls = body, []

    def fn(self, url, pass_, **kw):
        self.calls.append(url)
        return FetchOutcome(status.OK, url, 200, self.body, "", hashlib.sha256(self.body).hexdigest())

    @property
    def registry(self):
        return {1: self.fn, 2: self.fn, 3: self.fn}


def recipe(tmp_path, tier=1, **over):
    data = {"schema_version": 1, "source": SRC, "tier": tier, "url": URL, "selector": "table.prices",
            "dataset": {"symbol": "BTC-HIST", "timeframe": "1d"}, "min_rows": 2}
    data.update(over)
    p = tmp_path / "t.recipe.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return str(p)


def approve(tier=1):
    ApprovalStore(paths.approvals_dir()).write(
        make_record(source=SRC, tier=tier, hosts=("example.test",), pages=("/data/",)))


def go(argv, reg):
    return cli.main(argv, clock=fixed_clock(), registry=reg.registry)


def written(root):
    return [p for p in Path(root).rglob("*") if p.is_file()] if Path(root).exists() else []


@pytest.mark.parametrize("tier", [1, 2, 3])
@pytest.mark.parametrize("flags", [["--preview"], []])
def test_missing_columns_prints_table_outline_exit_5_one_fetch(tmp_path, capsys, tier, flags):
    approve(tier)
    reg = Reg()
    assert go(["run", recipe(tmp_path, tier), *flags], reg) == 5
    out = capsys.readouterr().out
    assert "missing columns:" in out and HEADER in out
    assert "tables matched: 2" in out and "columns: 3" in out and "rows: 3" in out
    assert "headers: Date, Price (USD), Change %" in out
    assert "111.11" not in out and "Secret narrative" not in out and PAGE_HEADER not in out
    assert len(reg.calls) == 1
    assert written(tmp_path / "dit" / "scrape") == [] and written(tmp_path / "dit" / "evid") == []


@pytest.mark.parametrize("flags", [["--preview"], []])
def test_other_invalid_reasons_print_no_table_outline(tmp_path, capsys, flags):
    approve()
    assert go(["run", recipe(tmp_path, min_rows=50), *flags], Reg(OK_BODY)) == 5
    assert HEADER not in capsys.readouterr().out
    ragged = b"<table class='prices'><tr><td>a</td><td>b</td></tr><tr><td>c</td></tr></table>"
    assert go(["run", recipe(tmp_path), *flags], Reg(ragged)) == 5
    assert HEADER not in capsys.readouterr().out


def test_changed_page_with_baseline_prints_no_table_outline(tmp_path, capsys):
    approve()
    assert go(["run", recipe(tmp_path), "--accept-baseline"], Reg(OK_BODY)) == 0
    capsys.readouterr()
    assert go(["run", recipe(tmp_path)], Reg((Path(__file__).parent / "fixtures_outline" / "rich.html").read_bytes())) == 6
    assert HEADER not in capsys.readouterr().out


@pytest.mark.parametrize("name", ["table_outline", "render_table_outline"])
def test_forced_outline_error_still_exit_5(tmp_path, monkeypatch, capsys, name):
    approve()
    monkeypatch.setattr(parse, name, lambda *a, **k: 1 / 0)
    assert go(["run", recipe(tmp_path), "--preview"], Reg()) == 5
    assert go(["run", recipe(tmp_path)], Reg()) == 5
    out = capsys.readouterr().out
    assert "missing columns:" in out and HEADER not in out and "Traceback" not in out
