"""S-B3R (collector-identity-pool finish plan, B3 (c)): offline benefit/removal analyzer over durable facts."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from api.data.attention import daily_facts as df
from api.data.attention import x_behaviour_report as rep

START = date(2026, 10, 1)
OFF = {m: False for m in rep.MEASURES} | {"x_queryid_mode": "pinned", "facts_retention_days": 180}


def _sw(*on: str) -> dict:
    return OFF | {m: True for m in on}


def _at(day: date, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, 12, minute, tzinfo=timezone.utc)


def _unit(account: str, coin: str, *, raw: int = 40, reads: int = 3) -> dict:
    return {"kind": "unit_completed", "source": "xsearch_web", "account": account, "coin": coin,
            "coin_day": "2026-09-30", "reads": reads, "pages": 2, "raw_results": raw}


def _seed_day(day: date, switches: dict, *, coins=("BTC", "ETH"), challenges: int = 0, locks: int = 0,
              mixed_reads: int = 0, universe=("BTC", "ETH", "SOL")) -> None:
    df.write_universe_snapshot(day, "xsearch_web", eligible_symbols=universe, ambiguous_symbols=[],
                               method_order=["xsearch_web"], now=_at(day), switches=switches)
    minute = 1
    for coin in coins:
        df.append(_unit("acct_a", coin), now=_at(day, minute), switches=switches)
        minute += 1
    for _ in range(challenges):
        df.append({"kind": "challenge", "source": "xsearch_web", "account": "acct_a", "class": "challenge"},
                  now=_at(day, minute), switches=switches)
        minute += 1
    for _ in range(locks):
        df.append({"kind": "account_state", "source": "xsearch_web", "account": "acct_a", "state": "pause",
                   "reason": "rate_limit"}, now=_at(day, minute), switches=switches)
        minute += 1
    if mixed_reads:
        df.append({"kind": "mixed_call", "source": "xsearch_web", "account": "acct_a", "target": "user_by_login",
                   "reads": mixed_reads}, now=_at(day, minute), switches=switches)


def _row(report: dict, measure: str) -> dict:
    return next(r for r in report["rows"] if r["measure"] == measure)


def test_measures_are_the_five_b3_switches():
    assert rep.MEASURES == ("x_quiet_hours_enabled", "x_mixed_traffic_enabled", "x_variation_enabled",
                            "x_adaptive_cooldown_enabled", "x_warmup_enabled")
    assert rep.MIN_DAYS == 7


def test_day_metrics_from_facts(isolated_cache):
    day = START
    _seed_day(day, _sw(), coins=("BTC",), challenges=2, locks=1, mixed_reads=20)
    m = rep.day_metrics(df.read_events(day))
    assert m["arm"] == "baseline"
    assert m["units"] == 1 and m["accounts"] == 1 and m["units_per_account"] == 1.0
    assert m["reads"] == 3 + 20 and m["challenges"] == 2 and m["locked_paused"] == 1
    assert m["missing_coin_days"] == 2  # ETH and SOL eligible but not completed


def test_arm_classification():
    def arm(*provs):
        return rep.classify([{"kind": "switch_provenance", "switches": p} for p in provs])
    assert arm(_sw()) == "baseline"
    assert arm(_sw("x_warmup_enabled")) == "x_warmup_enabled"
    assert arm(_sw("x_warmup_enabled", "x_variation_enabled")) == "combined"
    assert arm(_sw(), _sw("x_warmup_enabled")) == "changed"
    assert arm() == "no_provenance"
    # a non-measure switch change during the day does not break comparability
    assert arm(_sw(), _sw() | {"x_queryid_mode": "registry"}) == "baseline"


def test_missing_universe_is_unknown_not_zero(isolated_cache):
    df.append(_unit("acct_a", "BTC"), now=_at(START), switches=_sw())
    assert rep.day_metrics(df.read_events(START))["missing_coin_days"] is None


def test_seeded_c9_keep_and_inconclusive(isolated_cache):
    day = START
    for _ in range(7):  # baseline: harm every day
        _seed_day(day, _sw(), challenges=1, locks=1)
        day += timedelta(days=1)
    for _ in range(7):  # cooldown alone, 7 comparable days, less harm, no more missing coin-days
        _seed_day(day, _sw("x_adaptive_cooldown_enabled"))
        day += timedelta(days=1)
    for _ in range(3):  # warm-up alone: only 3 days
        _seed_day(day, _sw("x_warmup_enabled"))
        day += timedelta(days=1)
    for _ in range(2):  # combined days are excluded from every single-measure arm
        _seed_day(day, _sw("x_warmup_enabled", "x_variation_enabled"))
        day += timedelta(days=1)
    report = rep.analyze(START, day - timedelta(days=1))
    assert report["arms"]["baseline"] == 7 and report["arms"]["combined"] == 2
    cd = _row(report, "x_adaptive_cooldown_enabled")
    assert (cd["decision"], cd["baseline_days"], cd["measure_days"]) == ("keep", 7, 7)
    wu = _row(report, "x_warmup_enabled")
    assert (wu["decision"], wu["measure_days"]) == ("inconclusive", 3)
    assert _row(report, "x_quiet_hours_enabled")["decision"] == "inconclusive"
    assert rep.analyze(START, day - timedelta(days=1)) == report  # deterministic


def test_measure_without_benefit_is_removed(isolated_cache):
    day = START
    for _ in range(7):
        _seed_day(day, _sw())
        day += timedelta(days=1)
    for _ in range(7):  # mixed traffic spends reads, no harm reduction, one more missing coin-day
        _seed_day(day, _sw("x_mixed_traffic_enabled"), coins=("BTC",), mixed_reads=20)
        day += timedelta(days=1)
    row = _row(rep.analyze(START, day - timedelta(days=1)), "x_mixed_traffic_enabled")
    assert row["decision"] == "remove"
    assert row["metrics"]["reads"] == {"baseline": 6.0, "measure": 23.0}


def test_shrink_events_replayed_from_unit_results(isolated_cache):
    day = START
    for _ in range(7):
        df.append(_unit("acct_a", "BTC", raw=100), now=_at(day), switches=_sw())
        day += timedelta(days=1)
    df.append(_unit("acct_a", "BTC", raw=1), now=_at(day), switches=_sw())
    report = rep.analyze(START, day)
    assert [d["shrink_events"] for d in report["days"]] == [0] * 7 + [1]


def test_reads_only_facts_not_pool_state(isolated_cache):
    (isolated_cache / "attention").mkdir(parents=True, exist_ok=True)
    (isolated_cache / "attention" / "x_pool.json").write_text("{not json")
    report = rep.analyze(START, START + timedelta(days=2))
    assert all(d["arm"] == "no_provenance" for d in report["days"]) and len(report["days"]) == 3


def test_range_validation():
    with pytest.raises(ValueError):
        rep.analyze(START, START - timedelta(days=1))
    with pytest.raises(ValueError):
        rep.analyze(START, START + timedelta(days=rep.MAX_RANGE_DAYS))


def test_cli_prints_rows_with_sample_sizes(isolated_cache, capsys):
    _seed_day(START, _sw())
    assert rep.main(["--from", START.isoformat(), "--to", START.isoformat()]) == 0
    out = capsys.readouterr().out
    for m in rep.MEASURES:
        assert m in out
    assert "inconclusive" in out and "baseline_days=1" in out
    assert rep.main(["--from", "2026-10-02", "--to", "2026-10-01"]) == 2
