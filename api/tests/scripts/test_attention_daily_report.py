"""S-Report CLI: `python -m api.scripts.attention_daily_report [--day D] [--print]` (offline, facts only)."""
from __future__ import annotations

import io
import json
from datetime import date, datetime, timezone

from api.analytics.attention import daily_report as dr
from api.data import cache
from api.data.attention import daily_facts
from api.scripts import attention_daily_report as cli

D = date(2026, 11, 5)
AT = datetime(2026, 11, 5, 9, 0, tzinfo=timezone.utc)
NOW = datetime(2026, 11, 6, 1, 0, tzinfo=timezone.utc)


def _none(day, universe):
    return {src: {s: None for s in syms} for src, syms in universe.items()}


def _seed():
    daily_facts.write_universe_snapshot(D, "xsearch", eligible_symbols=["SOL"], ambiguous_symbols=[],
                                        method_order=["xsearch_web"], now=AT, switches={})
    p = cache.CACHE_ROOT / "attention" / "xsearch_web" / "_meta" / "_completeness" / f"{D.isoformat()}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"day": D.isoformat(), "coins": {"SOL": {"reason": "fetched", "capped": False}}}))


def test_cli_defaults_to_yesterday_and_prints(isolated_cache):
    _seed()
    out = io.StringIO()
    assert cli.main(["--print"], out=out, now=NOW, selector=_none) == 0
    assert dr.report_paths(D)[0].exists()
    assert "100% stored" in out.getvalue() and D.isoformat() in out.getvalue()


def test_cli_explicit_day_without_print_reports_paths(isolated_cache):
    _seed()
    out = io.StringIO()
    assert cli.main(["--day", D.isoformat()], out=out, now=NOW, selector=_none) == 0
    assert str(dr.report_paths(D)[0]) in out.getvalue()


def test_cli_refuses_an_open_day(isolated_cache):
    out = io.StringIO()
    assert cli.main(["--day", NOW.date().isoformat()], out=out, now=NOW, selector=_none) == 2
    assert not dr.report_paths(NOW.date())[0].exists()
