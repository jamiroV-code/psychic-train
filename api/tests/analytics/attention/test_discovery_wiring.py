"""W8f: Discovery wiring (SPEC AC5, AC6, AC14, AC23, AC32 rescale; Locked pacing rule 9, Q10, Q13).

`fetch_side` and `source_impl` in discovery.json, one method per window (never spliced), PC-off gaps rescale,
T96 lag, point in time with the backfilled flag, reason codes on the Sources row, and the X rotation mode.
Store and config only; every path redirected to tmp_path.
"""
from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta, timezone

import pytest

from api.analytics.attention import discovery as disc, sources as src_mod
from api.data import attention_pc_refresh as pc
from api.data.attention import registry, store, web_evidence
from api.data.attention.types import SourceSeries
from api.tests.analytics.attention.conftest import TODAY
from api.tests.analytics.attention.test_discovery import END, cat, put_change, world

COINS = {"A": 5e7}
CATS = {"ai": ["A"]}


def put_points(source, symbol, pts):
    """Exactly these (day, value) points, replacing whatever the store held."""
    p = store.store_path(source, symbol)
    if p.exists():
        p.unlink()
    store.write_series(SourceSeries(source, symbol, sorted(pts), "ok"), today=TODAY)


def coin(res, symbol="A"):
    return next(r for r in cat(res, "ai").coins if r.symbol == symbol)


def by_source(res, symbol="A"):
    return {s.source: s for s in coin(res, symbol).sources}


def run(today=TODAY, **kw):
    return disc.build_discovery(30, today=today, **kw)


def shipped() -> dict:
    return json.loads(disc.CONFIG_PATH.read_text())


# ---- config: fetch_side and source_impl ---------------------------------------------------------

def test_fetch_side_rejects_unknown_value():
    cfg = disc.validate_config(shipped())
    assert disc.fetch_sides(cfg) == {"xsearch": "pc_side", "reddit": "pc_side", "trends": "github",
                                     "wikipedia": "github", "exchange_activity": "github",
                                     "defillama": "github", "github_dev": "github"}
    # the W8e worker's default map and its reading of the shipped file agree with the validated config
    assert pc.FETCH_SIDE == disc.fetch_sides(cfg) == disc.DEFAULT_FETCH_SIDE
    assert pc.pc_sources(disc.CONFIG_PATH) == ["xsearch_web", "reddit_web"]
    bad = [
        {"fetch_side": {**cfg["fetch_side"], "reddit": "laptop"}},
        {"fetch_side": {**cfg["fetch_side"], "mastodon": "github"}},
        {"fetch_side": {k: v for k, v in cfg["fetch_side"].items() if k != "trends"}},
        {"fetch_side": ["xsearch"]},
        {"source_impl": {"reddit": "reddit_scraped"}},
        {"source_impl": {"trends": "trends_web"}},
        {"source_impl": {"reddit": []}},
        {"source_impl": {"reddit": ["reddit_web", "reddit_web"]}},
        {"source_impl": {"reddit": "reddit"}},  # the official store is GitHub-side, reddit is pc_side here
        {"x_discovery_mode": "daily"},
        {"x_rotation_points": 1},
        {"x_rotation_points": True},
        {"x_rotation_max_lag_days": -1},
    ]
    for over in bad:
        with pytest.raises(ValueError, match="discovery config"):
            disc.validate_config({**copy.deepcopy(cfg), **over})


def test_shipped_config_selects_web_methods_and_rotation():
    cfg = disc.load_config()
    assert disc.source_impls(cfg)["xsearch"] == ("xsearch_web",)
    assert disc.source_impls(cfg)["reddit"] == ("reddit_web", "reddit_stream")
    assert (cfg["x_discovery_mode"], cfg["x_rotation_points"], cfg["x_rotation_max_lag_days"]) == ("rotation", 3, 7)


# ---- source_impl: one method per window ---------------------------------------------------------

def test_source_impl_reads_web_store(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, COINS, cats=CATS, source_impl={"reddit": "reddit_web"})
    put_change("reddit", "A", 5.0, 1.0)        # official store: +400 %, not selected
    put_change("reddit_web", "A", 1.2, 1.0)    # web store (no probe record: written by the PC worker): +20 %
    assert by_source(run())["reddit"].change == pytest.approx(20.0)
    assert "reddit_web" in disc.series_names(disc.load_config()) and "reddit" not in disc.series_names(
        disc.load_config())


def test_two_methods_never_spliced(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, COINS, cats=CATS, source_impl={"reddit": ["reddit_web", "reddit_stream"]})
    # reddit_web holds only the recent days (+200 %), reddit_stream a full window (+10 %): a splice of the web
    # recent days onto the stream base would give +200 %; one method per window gives the stream's +10 %
    put_points("reddit_web", "A", [(END - timedelta(days=i), 3.0) for i in range(7)])
    put_change("reddit_stream", "A", 1.1, 1.0)
    assert by_source(run())["reddit"].change == pytest.approx(10.0)
    # once the first method has a full window it is used for the whole window, the second is ignored
    put_points("reddit_web", "A", [(END - timedelta(days=129 - i), 1.5 if i >= 123 else 1.0) for i in range(130)])
    assert by_source(run())["reddit"].change == pytest.approx(50.0)


# ---- AC6: PC-off gaps rescale, T96 lag drops ----------------------------------------------------

def test_pc_off_gap_rescales_not_zero(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, COINS, cats=CATS, source_impl={"reddit": "reddit_web"})
    put_change("wikipedia", "A", 1.2, 1.0)                     # +20 %, weight 25
    put_change("reddit_web", "A", 2.0, 1.0, lag=10)            # PC off for the last 10 days
    r = coin(run())
    assert "reddit" not in {s.source for s in r.sources}
    assert r.covered_weight == pytest.approx(25.0) and r.raw_change == pytest.approx(20.0)   # never a 0 for reddit
    # PC-off days inside the base window are missing, never 0: the mean is over the stored days only
    pts = [(END - timedelta(days=129 - i), 1.5 if i >= 123 else 1.0) for i in range(130)
           if not 100 <= i < 110]
    put_points("reddit_web", "A", pts)
    r = coin(run())
    assert by_source(run())["reddit"].change == pytest.approx(50.0)
    assert r.covered_weight == pytest.approx(25.0 + 15.0)


def test_t96_lag_drops_source(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, COINS, cats=CATS, source_impl={"reddit": "reddit_web"})
    put_change("wikipedia", "A", 1.2, 1.0)
    put_change("reddit_web", "A", 2.0, 1.0, lag=3)             # exactly max_source_lag_days: still counted
    assert "reddit" in by_source(run())
    put_points("reddit_web", "A", [(d - timedelta(days=1), v) for d, v in store.read_points("reddit_web", "A")])
    assert "reddit" not in by_source(run())                    # lag 4 > 3: drops out, weights rescale
    assert coin(run()).covered_weight == pytest.approx(25.0)


# ---- AC5: point in time and the backfilled flag -------------------------------------------------

def _truncate_after(day, *sources):
    for s in sources:
        put_points(s, "A", [(d, v) for d, v in store.read_points(s, "A") if d <= day])


def test_point_in_time_truncate_recompute_identical(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, COINS, cats=CATS, source_impl={"reddit": "reddit_web"})
    put_change("wikipedia", "A", 1.2, 1.0)
    put_points("reddit_web", "A", [(END - timedelta(days=129 - i), 1.0 + 0.01 * i) for i in range(130)])
    day = END - timedelta(days=5)
    full = run(today=day + timedelta(days=1)).model_dump()
    _truncate_after(day, "wikipedia", "reddit_web")
    assert run(today=day + timedelta(days=1)).model_dump() == full


def _evidence(source, symbol, rows):
    p = web_evidence.evidence_path(source, symbol)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"rows": [r.to_json() for r in rows]}), encoding="utf-8")


def _row(day, value, *, backfilled=False, late_days=1):
    at = datetime(day.year, day.month, day.day, 1, tzinfo=timezone.utc) + timedelta(days=late_days)
    return web_evidence.EvidenceRow(day, value, 10, 24.0, False, False, False, "m", at, backfilled)


def test_backfilled_flag_excludable(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, COINS, cats=CATS, source_impl={"reddit": "reddit_web"})
    put_change("wikipedia", "A", 1.2, 1.0)
    put_change("reddit_web", "A", 2.0, 1.0)
    pts = store.read_points("reddit_web", "A")
    recent = {d for d, _ in pts[-7:]}
    _evidence("reddit_web", "A", [_row(d, v, backfilled=d == max(recent)) for d, v in pts])
    assert by_source(run())["reddit"].change == pytest.approx(100.0)      # default: backfilled values count
    assert "reddit" not in by_source(run(known_at_time=True))             # excluded: the recent window is short
    # registry level: the flag and a late collection (not known at D+1) both drop the point, nothing else does
    _evidence("reddit_web", "A", [_row(d, v, backfilled=d == pts[0][0], late_days=5 if d == pts[1][0] else 1)
                                  for d, v in pts])
    kept = registry.read_series("reddit_web", "A", TODAY, known_at_time=True).points
    assert kept == pts[2:]
    assert registry.read_series("reddit_web", "A", TODAY).points == pts


# ---- Sources row: reason codes and state mapping ------------------------------------------------

@pytest.fixture
def live(isolated_cache, tmp_path, monkeypatch):
    monkeypatch.delenv("X_LIVE", raising=False)
    world(tmp_path, monkeypatch, {"A": 5e7, "B": 5e7}, cats={"ai": ["A", "B"]},
          source_weights={**disc.weights_for_day(disc.validate_config(shipped()), END)["source_weights"]},
          source_impl={"reddit": "reddit_web", "xsearch": "xsearch_web"}, x_discovery_mode="rotation",
          x_rotation_points=3, x_rotation_max_lag_days=7)
    src_mod.clear_cache()
    return tmp_path


def srow(sid):
    return next(r for r in src_mod.build_sources(TODAY).sources if r.id == sid)


def test_sources_row_shows_reason_code(live, monkeypatch):
    put_change("wikipedia", "A", 1.2, 1.0)
    r = srow("wikipedia")
    assert (r.state, r.reason, r.impl) == ("ok", "", "wikipedia")
    assert (srow("github_dev").state, srow("github_dev").reason) == ("off", "parked")
    assert (srow("trends").state, srow("trends").reason) == ("unavailable", "no_stored_data")
    put_change("reddit_web", "A", 2.0, 1.0, days=40)
    r = srow("reddit")
    assert (r.state, r.reason, r.impl) == ("insufficient-history", "insufficient_history", "reddit_web")
    assert "40/90" in r.note
    put_change("reddit_web", "B", 2.0, 1.0, days=130, lag=10)
    src_mod.clear_cache()
    r = srow("reddit")
    assert (r.state, r.reason) == ("unavailable", "stale") and "stale" in r.note
    # X rotation: the history gate is the 3 stored points, the lag is x_rotation_max_lag_days
    put_points("xsearch_web", "A", [(END - timedelta(days=6), 1.0), (END - timedelta(days=5), 1.0)])
    r = srow("xsearch")
    assert (r.state, r.reason, r.impl) == ("insufficient-history", "insufficient_history", "xsearch_web")
    assert "2/3" in r.note
    put_points("xsearch_web", "A", [(END - timedelta(days=7), 1.0), (END - timedelta(days=6), 1.0),
                                    (END - timedelta(days=5), 1.0)])
    src_mod.clear_cache()
    r = srow("xsearch")
    assert (r.state, r.reason, r.coins_with_data) == ("ok", "", 1)   # not "off": X_LIVE is the official store's
    # not probed (official store, no probe record): reason code beside the existing state
    p = live / "probe_records.json"
    p.write_text('{"wikipedia": {}}')
    monkeypatch.setattr(registry, "PROBE_RECORDS_PATH", p)
    r = next(x for x in src_mod.build_sources(TODAY).sources if x.id == "trends")
    assert (r.state, r.reason) == ("not-probed", "not_probed")


# ---- X rotation mode (AC23) ---------------------------------------------------------------------

def rot_world(tmp_path, monkeypatch, **over):
    over.setdefault("source_impl", {"xsearch": "xsearch_web"})
    world(tmp_path, monkeypatch, COINS, cats=CATS, x_discovery_mode="rotation", **over)
    put_change("wikipedia", "A", 1.2, 1.0)


def test_rotation_three_points_scores(isolated_cache, tmp_path, monkeypatch):
    rot_world(tmp_path, monkeypatch)
    put_points("xsearch_web", "A", [(END - timedelta(days=12), 100.0), (END - timedelta(days=8), 1.0),
                                    (END - timedelta(days=4), 3.0), (END, 3.0)])
    x = by_source(run())["xsearch"]
    assert x.change == pytest.approx(50.0) and x.as_of == END.isoformat()   # 3 vs mean(1, 3); the 4th is unused
    assert coin(run()).covered_weight == pytest.approx(25.0 + 10.0)


def test_rotation_fewer_than_three_points_is_missing(isolated_cache, tmp_path, monkeypatch):
    rot_world(tmp_path, monkeypatch)
    put_points("xsearch_web", "A", [(END - timedelta(days=4), 1.0), (END, 3.0)])
    r = coin(run())
    assert "xsearch" not in {s.source for s in r.sources}
    assert r.covered_weight == pytest.approx(25.0) and r.raw_change == pytest.approx(20.0)   # rescaled, never 0
    put_points("xsearch_web", "A", [(END - timedelta(days=8), 0.0), (END - timedelta(days=4), 0.0), (END, 3.0)])
    assert "xsearch" not in by_source(run())                       # base mean 0: no change, like other sources


def test_rotation_lag_uses_x_rotation_max_lag_days(isolated_cache, tmp_path, monkeypatch):
    rot_world(tmp_path, monkeypatch)
    pts = [(END - timedelta(days=d), v) for d, v in ((13, 1.0), (9, 1.0), (5, 2.0))]   # newest 5 days old
    put_points("xsearch_web", "A", pts)
    assert by_source(run())["xsearch"].change == pytest.approx(100.0)   # 5 > max_source_lag_days 3, <= 7
    put_points("xsearch_web", "A", [(d - timedelta(days=3), v) for d, v in pts])        # newest 8 days old
    assert "xsearch" not in by_source(run())
    rot_world(tmp_path, monkeypatch, x_rotation_max_lag_days=4)
    put_points("xsearch_web", "A", pts)
    assert "xsearch" not in by_source(run())


def test_other_sources_keep_seven_day_window(isolated_cache, tmp_path, monkeypatch):
    rot_world(tmp_path, monkeypatch, source_impl={"xsearch": "xsearch_web", "reddit": "reddit_web"})
    window_only = by_source(run())["wikipedia"].model_dump()
    put_points("reddit_web", "A", [(END - timedelta(days=8), 1.0), (END - timedelta(days=4), 1.0), (END, 3.0)])
    assert "reddit" not in by_source(run())                      # 3 points are no 7-day window for Reddit
    put_change("reddit_web", "A", 2.0, 1.0, lag=5)
    put_points("reddit_web", "A", [(END - timedelta(days=5 + 129 - i), 2.0 if i >= 123 else 1.0)
                                   for i in range(130)])
    assert "reddit" not in by_source(run())                      # lag 5 > max_source_lag_days 3 for Reddit
    world(tmp_path, monkeypatch, COINS, cats=CATS, x_discovery_mode="window")
    assert by_source(run())["wikipedia"].model_dump() == window_only


def test_window_mode_reproduces_current_x_behaviour(isolated_cache, tmp_path, monkeypatch):
    world(tmp_path, monkeypatch, COINS, cats=CATS)                   # no x_discovery_mode: today's rule
    put_change("wikipedia", "A", 1.2, 1.0)
    put_change("xsearch", "A", 1.3, 1.0)
    before = run().model_dump()
    assert by_source(run())["xsearch"].change == pytest.approx(30.0)
    world(tmp_path, monkeypatch, COINS, cats=CATS, x_discovery_mode="window")
    assert run().model_dump() == before
    put_points("xsearch", "A", [(END - timedelta(days=8), 1.0), (END - timedelta(days=4), 1.0), (END, 3.0)])
    assert "xsearch" not in by_source(run())                     # window mode: 3 points are not enough


def test_rotation_point_in_time_truncate_identical(isolated_cache, tmp_path, monkeypatch):
    rot_world(tmp_path, monkeypatch)
    put_points("xsearch_web", "A", [(END - timedelta(days=d), float(v))
                                    for d, v in ((15, 1), (11, 2), (7, 2), (3, 4), (0, 9))])
    day = END - timedelta(days=3)
    full = run(today=day + timedelta(days=1))
    assert by_source(full)["xsearch"].change == pytest.approx(100.0)   # 4 vs mean(2, 2): points <= day only
    _truncate_after(day, "xsearch_web", "wikipedia")
    assert run(today=day + timedelta(days=1)).model_dump() == full.model_dump()
