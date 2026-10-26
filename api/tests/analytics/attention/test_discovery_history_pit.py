"""T175 (T100b-PIT, M1 option A): point-in-time Trends in the Discovery history chart. Store only, no network.

Chart day D reads Trends from the pull archived on UTC date D+1 (`trends_pulls/<D+1>.parquet`, last row D), never
from the replaced live series and never from a later pull. A frozen snapshot's Trends entry for (D, window, coin)
wins over the archive; with neither, Trends is missing on D (never 0).
"""
from __future__ import annotations

import json
import random
from datetime import timedelta

import pytest

from api.analytics.attention import discovery as disc
from api.analytics.attention import discovery_history as hist
from api.analytics.attention import signal_snapshots
from api.data.attention import store
from api.data.attention.types import SourceSeries
from api.tests.analytics.attention.conftest import TODAY
from api.tests.analytics.attention.test_discovery import END, world

W = 30
WINDOW_DAYS = [END - timedelta(days=W - 1 - i) for i in range(W)]


@pytest.fixture(autouse=True)
def _fresh_cache():
    hist.clear_cache()
    yield
    hist.clear_cache()


def series(n, last, f):
    """n consecutive days ending `last`, value f(i) for the i-th day (oldest first)."""
    return [(last - timedelta(days=n - 1 - i), float(f(i))) for i in range(n)]


def pull(pull_date, by_symbol, n=100):
    """Archive one Trends pull as the refresh run does: points < pull_date, last row pull_date - 1."""
    out = []
    for sym, f in by_symbol.items():
        out.append(SourceSeries("trends", sym, series(n, pull_date - timedelta(days=1), f), "ok"))
    store.write_pull_archive("trends", pull_date, out)


def values(v):
    return lambda i: v[i]


def wave(seed):
    return lambda i: 10.0 + (i * 7 + seed * 13) % 37 + 0.5 * seed


def expected(points, day):
    """The Trends change the chart must show on `day` when Trends is the only source (score == that change)."""
    pts = [p for p in points if p[0] <= day]
    return disc._source_change(pts, day, 7, W, 3)


def by_date(res):
    return {d.date: d for d in res.days}


def only_trends(tmp_path, monkeypatch, coins=("A",)):
    world(tmp_path, monkeypatch, {c: 5e7 for c in coins}, cats={"ai": list(coins)})


def snapshot(day, rows, window=W):
    p = signal_snapshots.snapshot_dir() / f"{day.isoformat()}_w{window}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"date": day.isoformat(), "window": window, "membership_definition": "narratives",
                             "rows": rows}))


def snap_row(day, sym, sources, window=W):
    return {"date": day.isoformat(), "window": window, "symbol": sym, "category_ids": ["ai"], "score": 0.0,
            "covered_weight": 0.0, "rising_weight": 0.0, "trigger": False, "sources": sources}


def test_chart_day_d_reads_pull_d_plus_1(isolated_cache, tmp_path, monkeypatch):
    only_trends(tmp_path, monkeypatch)
    pulls = {}
    for d in WINDOW_DAYS:
        pulls[d] = series(100, d, wave(d.toordinal() % 5))
        pull(d + timedelta(days=1), {"A": wave(d.toordinal() % 5)})
    # the live (replaced) series holds other values; the chart must not read it
    store.write_series(SourceSeries("trends", "A", series(100, END, lambda i: 50.0 + i % 3), "ok"),
                       today=TODAY, mode="replace-series")
    got = by_date(hist.coin_history("A", W, today=TODAY))
    assert len(got) == W
    for d in WINDOW_DAYS:
        want = expected(pulls[d], d)
        assert want is not None
        assert got[d.isoformat()].score == pytest.approx(want, abs=1e-12)
        assert got[d.isoformat()].covered_weight == 25


def test_pull_date_for_day_is_next_utc_day():
    d = END - timedelta(days=4)
    assert hist.trends_pull_date(d) == d + timedelta(days=1)


def test_chart_never_reads_later_pull(isolated_cache, tmp_path, monkeypatch):
    only_trends(tmp_path, monkeypatch)
    d = END - timedelta(days=10)
    # only LATER pulls exist for d (d+2 .. today); each has a row for d, with values unlike each other
    for k in range(2, 12):
        pull(d + timedelta(days=k), {"A": wave(k)})
    got = by_date(hist.coin_history("A", W, today=TODAY))
    assert d.isoformat() not in got
    assert all(day > d.isoformat() for day in got)
    # the right pull appears: d now reads it, and only it
    pull(d + timedelta(days=1), {"A": wave(99)})
    got = by_date(hist.coin_history("A", W, today=TODAY))
    assert got[d.isoformat()].score == pytest.approx(expected(series(100, d, wave(99)), d), abs=1e-12)


def test_pull_without_last_row_d_is_missing(isolated_cache, tmp_path, monkeypatch):
    only_trends(tmp_path, monkeypatch)
    d = END - timedelta(days=3)
    lagged = series(100, d - timedelta(days=1), wave(1))   # Google lagged: the pull of d+1 ends on d-1
    store.write_pull_archive("trends", d + timedelta(days=1), [SourceSeries("trends", "A", lagged, "ok")])
    got = by_date(hist.coin_history("A", W, today=TODAY))
    assert d.isoformat() not in got
    reader = hist._TrendsPulls(probed=True, min_days=90)
    s = reader.at("A", d)
    assert (s.state, s.points, s.reason) == ("unavailable", [], hist.PULL_LAST_ROW_NOT_DAY)
    # the lagged pull is not used for d-1 either: that day's pull is d, which does not exist
    assert reader.at("A", d - timedelta(days=1)).reason == hist.NO_PULL


def test_absent_pull_is_missing_not_zero(isolated_cache, tmp_path, monkeypatch):
    only_trends(tmp_path, monkeypatch)
    gap = END - timedelta(days=6)
    for d in WINDOW_DAYS:
        if d != gap:
            pull(d + timedelta(days=1), {"A": wave(2)})
    res = hist.coin_history("A", W, today=TODAY)
    got = by_date(res)
    assert gap.isoformat() not in got and len(got) == W - 1
    assert all(x.score != 0 for x in res.days)
    s = hist._TrendsPulls(probed=True, min_days=90).at("A", gap)
    assert (s.state, s.reason) == ("unavailable", hist.NO_PULL)
    # with another source the day stays, scored without Trends (weight rescaled, never Trends = 0)
    store.write_series(SourceSeries("wikipedia", "A", series(130, END, wave(3)), "ok"), today=TODAY)
    hist.clear_cache()
    got = by_date(hist.coin_history("A", W, today=TODAY))
    assert got[gap.isoformat()].covered_weight == 25    # wikipedia only
    assert got[(gap - timedelta(days=1)).isoformat()].covered_weight == 50


def test_missing_reasons_symbol_short_pull_unreadable_not_probed(isolated_cache, tmp_path, monkeypatch):
    only_trends(tmp_path, monkeypatch)
    d = END - timedelta(days=2)
    pull(d + timedelta(days=1), {"B": wave(1)})
    pull(d, {"A": wave(1)}, n=60)
    bad = store.pull_archive_path("trends", d + timedelta(days=2))
    bad.write_bytes(b"not parquet")
    r = hist._TrendsPulls(probed=True, min_days=90)
    assert r.at("A", d).reason == hist.SYMBOL_NOT_IN_PULL
    short = r.at("A", d - timedelta(days=1))
    assert (short.state, short.points) == ("insufficient-history", [])
    assert r.at("A", d + timedelta(days=1)).reason == hist.UNREADABLE_PULL
    assert hist._TrendsPulls(probed=False, min_days=90).at("B", d).state == "unavailable"
    assert r.at("B", d).state == "ok" and r.count("B", d) == 100
    # the gate: exactly min_history_days rows in the pull is enough, one fewer is not
    pull(d - timedelta(days=2), {"A": wave(1)}, n=90)
    pull(d - timedelta(days=3), {"A": wave(1)}, n=89)
    assert r.at("A", d - timedelta(days=3)).state == "ok"
    assert r.at("A", d - timedelta(days=4)).state == "insufficient-history"
    # an unreadable pull never breaks the chart
    assert [x.date for x in hist.coin_history("A", W, today=TODAY).days] == [(d - timedelta(days=3)).isoformat()]


def test_snapshot_wins_over_archive(isolated_cache, tmp_path, monkeypatch):
    only_trends(tmp_path, monkeypatch)
    d = END - timedelta(days=5)
    for x in WINDOW_DAYS:
        pull(x + timedelta(days=1), {"A": wave(4)})
    snapshot(d, [snap_row(d, "A", [{"source": "trends", "change": 42.5, "as_of": (d - timedelta(days=1)).isoformat()},
                                   {"source": "wikipedia", "change": 1.0, "as_of": d.isoformat()}])])
    # another window's record never feeds this window
    snapshot(d + timedelta(days=1), [snap_row(d + timedelta(days=1), "A", [{"source": "trends", "change": 99.0,
                                                                           "as_of": d.isoformat()}], 7)], window=7)
    got = by_date(hist.coin_history("A", W, today=TODAY))
    assert got[d.isoformat()].score == pytest.approx(42.5)
    nxt = d + timedelta(days=1)
    assert got[nxt.isoformat()].score == pytest.approx(expected(series(100, nxt, wave(4)), nxt), abs=1e-12)
    # only the snapshot's Trends entry is taken: its wikipedia entry is not, the chart reads the store for that
    assert got[d.isoformat()].covered_weight == 25


def test_snapshot_without_trends_entry_falls_back_to_archive(isolated_cache, tmp_path, monkeypatch):
    only_trends(tmp_path, monkeypatch)
    d = END - timedelta(days=5)
    pull(d + timedelta(days=1), {"A": wave(4)})
    snapshot(d, [snap_row(d, "A", [{"source": "wikipedia", "change": 3.0, "as_of": d.isoformat()}]),
                 snap_row(d, "B", [{"source": "trends", "change": 7.0, "as_of": d.isoformat()}])])
    got = by_date(hist.coin_history("A", W, today=TODAY))
    assert got[d.isoformat()].score == pytest.approx(expected(series(100, d, wave(4)), d), abs=1e-12)


def test_snapshot_trends_fills_day_without_archive(isolated_cache, tmp_path, monkeypatch):
    """The snapshot is a frozen record: it fills its day even with no archive at all."""
    only_trends(tmp_path, monkeypatch)
    d = END - timedelta(days=8)
    snapshot(d, [snap_row(d, "A", [{"source": "trends", "change": -12.0, "as_of": d.isoformat()}])])
    res = hist.coin_history("A", W, today=TODAY)
    assert [(x.date, x.score) for x in res.days] == [(d.isoformat(), -12.0)]


def test_other_sources_unchanged(isolated_cache, tmp_path, monkeypatch):
    """Every non-Trends source still reads the live store exactly as before; Trends' live series is never read."""
    only_trends(tmp_path, monkeypatch)
    for s in ("wikipedia", "coingecko", "reddit"):
        store.write_series(SourceSeries(s, "A", series(130, END, wave(len(s))), "ok"), today=TODAY)
    cfg = disc.load_config()
    stored = {(s, "A"): hist._Stored(s, "A", True, 90) for s in ("wikipedia", "coingecko", "reddit")}
    old = []
    for d in WINDOW_DAYS:
        data = {k: v.at(d) for k, v in stored.items()}
        data |= {(s, "A"): SourceSeries(s, "A") for s in disc.series_names(cfg) if (s, "A") not in data}
        old.append(disc._coin("A", cfg, data, d, 7, W, 3))
    base = hist.coin_history("A", W, today=TODAY)
    assert [(x.score, x.covered_weight, x.rising_weight, x.trigger) for x in base.days] == \
           [(c[0], c[1], c[2], c[3]) for c in old]
    # a replaced live Trends series changes nothing in the chart
    store.write_series(SourceSeries("trends", "A", series(100, END, wave(8)), "ok"), today=TODAY,
                       mode="replace-series")
    hist.clear_cache()
    assert hist.coin_history("A", W, today=TODAY).days == base.days


def test_last_day_matches_live_when_todays_pull_is_archived(isolated_cache, tmp_path, monkeypatch):
    """The refresh run writes the live series and today's pull together; the last chart day equals live scoring."""
    only_trends(tmp_path, monkeypatch)
    pts = series(100, END, wave(6))
    s = SourceSeries("trends", "A", pts, "ok")
    store.write_series(s, today=TODAY, mode="replace-series")
    store.write_pull_archive("trends", TODAY, [s])
    store.write_series(SourceSeries("wikipedia", "A", series(130, END, wave(2)), "ok"), today=TODAY)
    live = disc.build_discovery(W, today=TODAY)
    coin = next(c for cat in live.categories for c in cat.coins if c.symbol == "A")
    last = hist.coin_history("A", W, today=TODAY).days[-1]
    assert last.date == END.isoformat()
    assert (last.score, last.covered_weight) == (pytest.approx(coin.raw_change), coin.covered_weight)


def test_history_days_for_trends_come_from_the_pull(isolated_cache, tmp_path, monkeypatch):
    only_trends(tmp_path, monkeypatch)
    store.write_series(SourceSeries("trends", "A", series(100, END, wave(1)), "ok"), today=TODAY,
                       mode="replace-series")
    assert hist.coin_history("A", W, today=TODAY).history_days["trends"] == 0   # no pull for END yet
    pull(TODAY, {"A": wave(1)}, n=95)
    hist.clear_cache()
    assert hist.coin_history("A", W, today=TODAY).history_days["trends"] == 95


def test_new_pull_or_snapshot_invalidates_cache(isolated_cache, tmp_path, monkeypatch):
    only_trends(tmp_path, monkeypatch)
    d = END - timedelta(days=4)
    assert hist.coin_history("A", W, today=TODAY).days == []
    pull(d + timedelta(days=1), {"A": wave(3)})
    assert [x.date for x in hist.coin_history("A", W, today=TODAY).days] == [d.isoformat()]
    snapshot(d, [snap_row(d, "A", [{"source": "trends", "change": 5.0, "as_of": d.isoformat()}])])
    assert hist.coin_history("A", W, today=TODAY).days[0].score == 5.0


def test_category_history_reads_pulls_point_in_time(isolated_cache, tmp_path, monkeypatch):
    only_trends(tmp_path, monkeypatch, coins=("A", "B"))
    d = END - timedelta(days=1)
    pull(d + timedelta(days=1), {"A": wave(1), "B": wave(2)})
    pull(END + timedelta(days=1), {"A": wave(5)})                    # B missing from today's pull
    got = by_date(hist.category_history("ai", W, today=TODAY))
    assert set(got) == {d.isoformat(), END.isoformat()}
    assert got[d.isoformat()].coins_used == 2 and got[END.isoformat()].coins_used == 1
    assert got[END.isoformat()].score == pytest.approx(expected(series(100, END, wave(5)), END), abs=1e-12)


@pytest.mark.parametrize("seed", range(8))
def test_no_look_ahead_over_several_pulls(isolated_cache, tmp_path, monkeypatch, seed):
    """Property: with daily pulls whose later versions rescale and revise the past, chart day D equals the chart
    computed when only pulls dated <= D+1 existed, and never depends on a later pull."""
    only_trends(tmp_path, monkeypatch, coins=("A", "B"))
    rng = random.Random(seed)
    base = {sym: [rng.uniform(5, 60) for _ in range(160)] for sym in ("A", "B")}
    first = END - timedelta(days=W + 5)
    pulls = {}
    for k in range((END - first).days + 2):        # pull dates first .. TODAY
        p = first + timedelta(days=k)
        scale = rng.uniform(0.6, 1.5)
        rows = {}
        for sym, vals in base.items():
            if rng.random() < 0.1:
                continue                             # coin missing from this pull
            off = (p - first).days
            v = [min(100.0, x * scale) for x in vals[off:off + 100]]
            for j in rng.sample(range(100), 5):     # Google re-samples a few past values
                v[j] = min(100.0, v[j] + rng.uniform(1, 20))
            rows[sym] = v
        if rng.random() < 0.1:
            continue                                 # whole pull missing (run failed)
        pulls[p] = rows
    def write(upto):
        for p, rows in pulls.items():
            if p <= upto:
                pull(p, {s: values(v) for s, v in rows.items()})

    write(TODAY)
    full = {s: by_date(hist.coin_history(s, W, today=TODAY)) for s in ("A", "B")}
    for d in WINDOW_DAYS:
        p = d + timedelta(days=1)
        for s in ("A", "B"):
            row = full[s].get(d.isoformat())
            if p not in pulls or s not in pulls[p]:
                assert row is None, (d, s)
                continue
            want = expected(series(100, d, values(pulls[p][s])), d)
            if want is None:
                assert row is None
            else:
                assert row.score == pytest.approx(want, abs=1e-12)
    # recompute with only the pulls known on each day: identical past days
    for d in WINDOW_DAYS[::5]:
        for f in store.pull_archive_path("trends", TODAY).parent.glob("*.parquet"):
            f.unlink()
        write(d + timedelta(days=1))
        hist.clear_cache()
        for s in ("A", "B"):
            cut = by_date(hist.coin_history(s, W, today=TODAY))
            assert cut.get(d.isoformat()) == full[s].get(d.isoformat())
            assert all(k <= d.isoformat() for k in cut)
