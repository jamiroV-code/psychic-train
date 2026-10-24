"""T103 W2: point-in-time Discovery history. Store only; every path redirected to tmp_path."""
from __future__ import annotations

import time
from datetime import timedelta

import pytest

from api.analytics.attention import discovery as disc, discovery_history as hist
from api.data.attention import store
from api.data.attention.types import SourceSeries
from api.tests.analytics.attention.conftest import TODAY
from api.tests.analytics.attention.test_discovery import END, SOURCES, cat, gain, put_change, world


@pytest.fixture(autouse=True)
def _fresh_cache():
    hist.clear_cache()
    yield
    hist.clear_cache()


def put_pts(source, symbol, pts):
    store.write_series(SourceSeries(source, symbol, pts, "ok"), today=TODAY)


def ramp(n, end=END, slope=0.05):
    """n completed days ending `end`, linearly rising so every day has a distinct change."""
    return [(end - timedelta(days=n - 1 - i), 1.0 + slope * i) for i in range(n)]


def wobbly(n, end=END):
    return [(end - timedelta(days=n - 1 - i), 1.0 + 0.3 * ((i * 7) % 11) + 0.02 * i) for i in range(n)]


def by_date(res):
    return {d.date: d for d in res.days}


def seed_coin(sym, n=130, shape=wobbly):
    for s in SOURCES:
        put_pts(s, sym, shape(n))


def truncate_store(sym, last):
    for s in SOURCES:
        pts = [p for p in store.read_points(s, sym) if p[0] <= last]
        store.store_path(s, sym).unlink()
        put_pts(s, sym, pts)


# ---- AC-W11 / AC-W16: point-in-time ---------------------------------------------------------

def test_day_d_from_truncated_store_equals_full_store(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]})
    seed_coin("A")
    full = hist.coin_history("A", 30, today=TODAY)
    d = END - timedelta(days=10)
    want = by_date(full)[d.isoformat()]
    truncate_store("A", d)
    cut = hist.coin_history("A", 30, today=d + timedelta(days=1))
    got = cut.days[-1]
    assert got.date == d.isoformat() and got == want
    assert len(full.days) == 30 and want.covered_weight > 0


def test_changing_or_deleting_points_after_d_does_not_change_d(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]})
    seed_coin("A")
    before = by_date(hist.coin_history("A", 30, today=TODAY))
    d = END - timedelta(days=12)
    for s in SOURCES:  # rewrite everything after D with wild values
        pts = [(x, v if x <= d else v * 100) for x, v in store.read_points(s, "A")]
        store.store_path(s, "A").unlink()
        put_pts(s, "A", pts)
    after = by_date(hist.coin_history("A", 30, today=TODAY))
    for k, v in before.items():
        if k <= d.isoformat():
            assert after[k] == v
    assert after[END.isoformat()] != before[END.isoformat()]
    for s in SOURCES:  # deleting the tail: the shared days are unchanged
        pts = [p for p in store.read_points(s, "A") if p[0] <= d]
        store.store_path(s, "A").unlink()
        put_pts(s, "A", pts)
    gone = by_date(hist.coin_history("A", 30, today=TODAY))
    assert gone[d.isoformat()] == before[d.isoformat()]


def test_last_day_matches_live_scoring(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]})
    seed_coin("A")
    live = next(c for c in cat(disc.build_discovery(30, today=TODAY), "ai").coins if c.symbol == "A")
    last = hist.coin_history("A", 30, today=TODAY).days[-1]
    assert last.date == END.isoformat()
    assert (last.score, last.covered_weight, last.rising_weight, last.trigger) == (
        live.raw_change, live.covered_weight, live.rising_weight, live.trigger)


def test_t96_lag_anchored_to_day_d_not_today(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]})
    for s in SOURCES:
        put_pts(s, "A", wobbly(130, end=END - timedelta(days=20)))  # store stops 20 days ago
    res = hist.coin_history("A", 90, today=TODAY)
    assert res.status == "ok"
    assert max(d.date for d in res.days) == (END - timedelta(days=20 - 3)).isoformat()  # lag limit 3


# ---- AC-W13: the 90-day gate ---------------------------------------------------------------

def test_source_absent_until_min_history_days_then_present(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]})
    put_pts("wikipedia", "A", ramp(100))
    res = hist.coin_history("A", 90, today=TODAY)
    first = END - timedelta(days=99) + timedelta(days=89)  # the 90th stored point
    assert [d.date for d in res.days] == [(first + timedelta(days=i)).isoformat() for i in range(11)]
    assert all(d.covered_weight == 25 for d in res.days)
    assert (first - timedelta(days=1)).isoformat() not in by_date(res)


def test_min_history_days_comes_from_config(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]}, min_history_days=30)
    put_pts("wikipedia", "A", ramp(40))
    res = hist.coin_history("A", 30, today=TODAY)
    first = END - timedelta(days=39) + timedelta(days=29)
    assert res.days[0].date == first.isoformat() and len(res.days) == 11
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]}, min_history_days=90)
    res = hist.coin_history("A", 7, today=TODAY)
    assert (res.status, res.reason, res.days) == ("no-data", "no-attention-data", [])


def test_gate_does_not_use_total_stored_length(isolated_cache, tmp_path, monkeypatch):
    """130 stored days; on a day with only 89 points up to it the source must be out (lookahead trap)."""
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]})
    put_pts("wikipedia", "A", ramp(130))
    start = END - timedelta(days=129)
    res = by_date(hist.coin_history("A", 90, today=TODAY))
    assert (start + timedelta(days=88)).isoformat() not in res
    assert (start + timedelta(days=89)).isoformat() in res


def test_exchange_activity_rescales_when_an_exchange_appears_later(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]}, min_history_days=30)
    put_pts("exchange_volume", "A", ramp(130))
    put_pts("kraken_volume", "A", [(d, 1.0) for d, _ in ramp(35)])  # flat: change 0, gated from END-5
    res = by_date(hist.coin_history("A", 30, today=TODAY))
    pts = store.read_points("exchange_volume", "A")

    def binance(day):
        return disc._source_change([p for p in pts if p[0] <= day], day, 7, 30, 3)

    solo_day, both_day = END - timedelta(days=6), END
    assert res[solo_day.isoformat()].score == pytest.approx(binance(solo_day))
    assert res[both_day.isoformat()].score == pytest.approx(40 * binance(both_day) / 55)
    assert res[solo_day.isoformat()].covered_weight == res[both_day.isoformat()].covered_weight == 10


def test_coingecko_fallback_per_day(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]}, min_history_days=30)
    put_pts("coingecko", "A", ramp(60))
    res = hist.coin_history("A", 7, today=TODAY)
    assert {d.covered_weight for d in res.days} == {10} and len(res.days) == 7


def test_missing_is_never_zero_and_rescales(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]})
    put_change("wikipedia", "A", 2.0, 1.0)
    put_change("coingecko", "A", 1.0, 1.0)
    d = hist.coin_history("A", 7, today=TODAY).days[-1]
    assert d.covered_weight == 35 and d.rising_weight == 25
    assert d.score == pytest.approx((25 * 100.0 + 10 * 0.0) / 35)


def test_trigger_flag_and_thin(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7, "B": 5e7}, cats={"ai": ["A", "B"]})
    gain("A")  # wikipedia 25 + coingecko 10 + trends 25 all rising
    put_change("wikipedia", "B", 2.0, 1.0)
    a = hist.coin_history("A", 7, today=TODAY).days[-1]
    b = hist.coin_history("B", 7, today=TODAY).days[-1]
    assert a.trigger and not a.thin and not b.trigger and b.thin and b.covered_weight == 25


# ---- payload, categories -------------------------------------------------------------------

def test_history_days_per_source(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]})
    put_pts("wikipedia", "A", ramp(130))
    put_pts("coingecko", "A", ramp(50))
    res = hist.coin_history("A", 30, today=TODAY)
    assert res.history_days["wikipedia"] == 130 and res.history_days["coingecko"] == 50
    assert res.history_days["reddit"] == 0 and res.min_history_days == 90


def test_empty_result_is_no_data_with_reason(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]})
    res = hist.coin_history("A", 30, today=TODAY)
    assert (res.status, res.reason, res.days) == ("no-data", "no-attention-data", [])


def test_unknown_symbol_and_category(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]})
    with pytest.raises(hist.UnknownSubject):
        hist.coin_history("NOPE", 30, today=TODAY)
    with pytest.raises(hist.UnknownSubject):
        hist.category_history("nope", 30, today=TODAY)


def test_category_history_needs_no_categories_snapshot(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats=None)
    res = hist.category_history("ai", 30, today=TODAY)
    assert res.reason != "categories-missing"


def test_coin_history_accepts_exchange_token_now_in_universe(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"LEO": 5e7, "USDT": 5e7}, cats={"ai": ["LEO"]})
    assert hist.coin_history("LEO", 30, today=TODAY).id == "LEO"
    with pytest.raises(hist.UnknownSubject):
        hist.coin_history("USDT", 30, today=TODAY)


def test_category_aggregate_matches_live_on_last_day(isolated_cache, tmp_path, monkeypatch):
    coins = {f"C{i}": 5e7 for i in range(6)}
    world(tmp_path, monkeypatch, coins, cats={"ai": list(coins)})
    for i, s in enumerate(coins):
        gain(s, factor=1.0 + 0.3 * i) if i < 5 else put_change("wikipedia", s, 1.0, 1.0)
    live = cat(disc.build_discovery(30, today=TODAY), "ai")
    last = hist.category_history("ai", 30, today=TODAY).days[-1]
    assert last.score == pytest.approx(live.score)
    assert (last.coins_used, last.triggered_count) == (live.coins_used, live.gaining_count)
    assert last.triggered_share == pytest.approx(live.gaining_count / live.coins_used)


def test_category_uses_only_coins_scorable_that_day_and_winsorises(isolated_cache, tmp_path, monkeypatch):
    coins = {f"C{i:02d}": 5e7 for i in range(20)}
    world(tmp_path, monkeypatch, coins, cats={"ai": list(coins)}, min_history_days=30)
    for i, s in enumerate(coins):
        n = 130 if i < 19 else 45  # C19 only passes the gate in the last 16 days
        put_pts("wikipedia", s, [(d, v * (51.0 if i == 19 else 1.0 + 0.01 * i) if d > END - timedelta(days=7)
                                  else v) for d, v in ramp(n, slope=0.0)])
    res = by_date(hist.category_history("ai", 30, today=TODAY))
    early = res[(END - timedelta(days=20)).isoformat()]
    late = res[END.isoformat()]
    assert (early.coins_used, late.coins_used) == (19, 20)
    raws = [hist.coin_history(s, 30, today=TODAY).days[-1].score for s in coins]
    cap = disc._percentile(raws, 95)
    assert max(raws) > cap > 0
    assert late.score == pytest.approx(sum(min(r, cap) for r in raws) / 20)  # C19's 5000% is capped
    assert late.triggered_count == 0 and late.triggered_share == 0.0


def test_category_unscorable_days_are_omitted(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]})
    put_pts("wikipedia", "A", ramp(100))
    res = hist.category_history("ai", 90, today=TODAY)
    assert len(res.days) == 11 and res.status == "ok"


# ---- performance ---------------------------------------------------------------------------

def test_each_series_is_read_once_not_per_day(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7, "B": 5e7}, cats={"ai": ["A", "B"]})
    seed_coin("A"), seed_coin("B")
    calls = []
    real = store.read_points
    monkeypatch.setattr(store, "read_points", lambda s, y: calls.append((s, y)) or real(s, y))
    hist.category_history("ai", 90, today=TODAY)
    assert len(calls) == len(set(calls))


def test_synthetic_100_coins_x_100_days_is_fast(isolated_cache, tmp_path, monkeypatch, capsys):
    coins = {f"C{i:03d}": 5e7 for i in range(100)}
    world(tmp_path, monkeypatch, coins, cats={"ai": list(coins)}, min_history_days=30)
    for s in coins:
        for src in ("wikipedia", "reddit", "trends", "coingecko"):
            put_pts(src, s, wobbly(130))
    t0 = time.perf_counter()
    res = hist.category_history("ai", 90, today=TODAY)
    cat_s = time.perf_counter() - t0
    t0 = time.perf_counter()
    hist.coin_history("C000", 90, today=TODAY)
    coin_s = time.perf_counter() - t0
    with capsys.disabled():
        print(f"\nTIMING category(100 coins x 90 days) {cat_s:.2f}s, coin(90 days) {coin_s:.3f}s")
    assert len(res.days) == 79 and res.days[-1].coins_used == 100  # 52 points needed per series
    t0 = time.perf_counter()
    hist.category_history("ai", 90, today=TODAY)
    warm_s = time.perf_counter() - t0
    with capsys.disabled():
        print(f"TIMING category warm (cache hit) {warm_s:.3f}s")
    assert coin_s < 0.5 and warm_s < 0.5


def test_cache_hit_skips_store_reads_and_invalidates(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]})
    seed_coin("A")
    calls = []
    real = store.read_points
    monkeypatch.setattr(store, "read_points", lambda s, y: calls.append((s, y)) or real(s, y))
    first = hist.category_history("ai", 30, today=TODAY)
    n = len(calls)
    assert n > 0 and hist.category_history("ai", 30, today=TODAY) == first and len(calls) == n  # hit
    hist.category_history("ai", 7, today=TODAY)  # other window: miss
    assert len(calls) > n
    n = len(calls)
    # a new stored day arrives
    store.write_series(SourceSeries("wikipedia", "A", [(TODAY, 9.0)], "ok"), today=TODAY + timedelta(days=1))
    hist.category_history("ai", 30, today=TODAY)
    assert len(calls) > n  # store changed: recomputed
    n = len(calls)
    pts = [(d, v * 3) for d, v in real("wikipedia", "A")]  # rewrite OLD points, latest date unchanged
    store.store_path("wikipedia", "A").unlink()
    put_pts("wikipedia", "A", pts)
    changed = hist.category_history("ai", 30, today=TODAY)
    assert len(calls) > n and changed != first
    n = len(calls)
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]}, trigger_pct=10)  # config edit
    hist.category_history("ai", 30, today=TODAY)
    assert len(calls) > n
    clone = hist.category_history("ai", 30, today=TODAY)
    clone.days.clear()  # callers cannot corrupt the cache
    assert hist.category_history("ai", 30, today=TODAY).days


# ---- T113 U1: ids resolve to narratives; old category ids through the map -----------------------------------

def test_history_accepts_old_category_id_via_map(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7, "B": 5e7}, cats={"ai": ["A", "B"]})
    seed_coin("A"), seed_coin("B")
    old = hist.category_history("artificial-intelligence", 30, today=TODAY)
    new = hist.category_history("ai", 30, today=TODAY)
    assert old.id == "ai" and old.status == "ok" and old.days == new.days


def test_history_retired_old_id_is_unknown(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]})
    with pytest.raises(hist.UnknownSubject, match="gaming"):
        hist.category_history("gaming", 30, today=TODAY)


def test_history_members_come_from_narratives(isolated_cache, tmp_path, monkeypatch):
    from api.analytics.attention import narratives as narr_mod
    from api.tests.analytics.attention.test_discovery import write_narratives
    world(tmp_path, monkeypatch, {"A": 5e7, "B": 5e7}, cats={"ai": ["A"]})
    monkeypatch.setattr(narr_mod, "NARRATIVES_PATH", write_narratives(tmp_path, {"ai": ["A", "B"]}))
    seed_coin("A"), seed_coin("B")
    assert hist.category_history("ai", 30, today=TODAY).days[-1].coins_used == 2


def test_history_payload_carries_membership_as_of(isolated_cache, tmp_path, monkeypatch):
    from api.analytics.attention import narratives as narr_mod
    from api.tests.analytics.attention.test_discovery import write_narratives
    world(tmp_path, monkeypatch, {"A": 5e7}, cats={"ai": ["A"]})
    seed_coin("A")
    assert hist.category_history("ai", 30, today=TODAY).membership_as_of == "2026-10-14"
    monkeypatch.setattr(narr_mod, "NARRATIVES_PATH", write_narratives(tmp_path, {"ai": ["A"]}, as_of="2026-10-15"))
    assert hist.category_history("ai", 30, today=TODAY).membership_as_of == "2026-10-15"  # cache invalidated
