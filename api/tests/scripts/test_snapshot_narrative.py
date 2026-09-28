"""RFC-4: nightly narrative snapshot script. All tests use `isolated_cache`
and stub every provider — no network."""
from __future__ import annotations

import pandas as pd
import pytest

from api.data import cache, coingecko_adapter, pytrends_adapter, reddit_adapter
from api.data import hyperliquid_narrative_adapter as hl
from api.data.coingecko_adapter import TrendingResult
from api.data.reddit_adapter import MentionResult
from api.scripts import snapshot_narrative as sn

TODAY = sn.utc_today()
CATS = ["ai", "rwa", "l2s", "memecoins"]
KWS = ["AI crypto", "RWA crypto", "layer 2 crypto", "memecoin"]
ALL_KWS = ["AI crypto", "artificial intelligence crypto", "RWA crypto", "tokenized real world assets",
           "layer 2 crypto", "L2 rollup", "memecoin", "meme coin crypto"]


def _trend_frame(values: dict, day: str) -> pd.DataFrame:
    return pd.DataFrame({k: [v] for k, v in values.items()}, index=pd.DatetimeIndex([day], name="date"))


@pytest.fixture
def providers(monkeypatch):
    """Healthy stubs; individual tests override pieces."""
    calls = {"pytrends": 0, "reddit": 0, "trending": 0, "exchange": 0}

    def fake_live(terms, timeframe="now 7-d"):
        calls["pytrends"] += 1  # one call per batched request
        return _trend_frame({t: 10.0 + ALL_KWS.index(t) for t in terms}, TODAY)

    def fake_mentions(kw, *a, **k):
        calls["reddit"] += 1
        cache.write_narrative_point("reddit", kw, TODAY, float(calls["reddit"]))
        return MentionResult(query=kw, mention_count=1.0, as_of=TODAY, status="ok")

    def fake_trending(*a, **k):
        calls["trending"] += 1
        # FET, TAO -> ai (curated); ETH -> l2s; BTC -> store-of-value (not a seed)
        return TrendingResult(symbols=["FET", "TAO", "ETH", "BTC"], as_of=TODAY, status="ok")

    def fake_hl(exchange=None, now=None):
        calls["exchange"] += 1
        perps = [hl.PerpMarket(base="FET", base_name="FET", quote_volume=100.0 * calls["exchange"]),
                 hl.PerpMarket(base="ETH", base_name="ETH", quote_volume=300.0)]
        return hl.ExchangeSnapshotResult(status="ok", as_of=TODAY, perps=perps)

    def fake_single(keyword):
        """Unbatched primary top-up: derives from whatever _fetch_batch_live
        stub is installed (so per-test overrides of date/failure carry over),
        offset by +1000 so it is distinguishable from the batched value."""
        try:
            df = pytrends_adapter._fetch_batch_live([keyword])
        except Exception:
            return None, None
        if df is None or df.empty or keyword not in df.columns:
            return None, None
        return float(df[keyword].iloc[-1]) + 1000.0, df.index[-1].strftime("%Y-%m-%d")

    monkeypatch.setattr(pytrends_adapter, "_fetch_batch_live", fake_live)
    monkeypatch.setattr(pytrends_adapter, "_fetch_live", fake_single)
    monkeypatch.setattr(reddit_adapter, "fetch_mentions", fake_mentions)
    monkeypatch.setattr(coingecko_adapter, "fetch_trending", fake_trending)
    monkeypatch.setattr(hl, "fetch_daily_market_snapshot", fake_hl)
    monkeypatch.setenv("REDDIT_CLIENT_ID", "x")
    monkeypatch.setenv("REDDIT_CLIENT_SECRET", "y")
    return calls


def _by_source(summaries):
    return {s.source: s for s in summaries}


def _all_files(root):
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())


def test_full_run_writes_every_source(isolated_cache, providers):
    summaries = sn.run_snapshot()
    by = _by_source(summaries)
    assert all(by[s].written == 4 for s in ("pytrends", "reddit", "coingecko-narrative", "exchange"))
    assert sn.exit_code(summaries) == 0
    for kw in KWS:
        assert len(cache.read_narrative_series("pytrends", kw)) == 1


def test_coingecko_narrative_uses_curated_map_and_never_writes_legacy(isolated_cache, providers):
    sn.run_snapshot()
    values = {c: float(cache.read_narrative_series("coingecko-narrative", c)["raw_value"].iloc[0]) for c in CATS}
    assert values == {"ai": 2.0, "rwa": 0.0, "l2s": 1.0, "memecoins": 0.0}
    assert not (isolated_cache / "narrative" / "coingecko").exists()
    assert not (isolated_cache / "narrative" / "coingecko-narrative" / "store-of-value.parquet").exists()


def test_same_day_rerun_no_duplicates_first_observation_wins(isolated_cache, providers):
    sn.run_snapshot()
    first = {kw: cache.read_narrative_series("pytrends", kw)["raw_value"].tolist() for kw in KWS}
    first_ex = cache.read_exchange_series("ai")["volume_share"].tolist()
    summaries = sn.run_snapshot()
    by = _by_source(summaries)
    for src in ("pytrends", "reddit", "coingecko-narrative", "exchange"):
        assert by[src].written == 0 and by[src].skipped_existing == 4, src
    for kw in KWS:
        assert cache.read_narrative_series("pytrends", kw)["raw_value"].tolist() == first[kw]
        assert len(cache.read_narrative_series("reddit", kw)) == 1
    assert cache.read_exchange_series("ai")["volume_share"].tolist() == first_ex
    # read-before-write: second run never even called pytrends/reddit
    # 8 keywords -> 2 anchor-chained batched requests on the first run only
    # (+4 unbatched primary top-ups, counted via the derived stub)
    assert providers["pytrends"] == 2 + 4 and providers["reddit"] == 4
    assert sn.exit_code(summaries) == 0


def test_backfilled_pytrends_date_is_never_overwritten(isolated_cache, providers, monkeypatch):
    yesterday = "2000-01-01"
    cache.write_narrative_point("pytrends", "AI crypto", yesterday, 55.0, source_status="backfilled")
    monkeypatch.setattr(pytrends_adapter, "_fetch_batch_live",
                        lambda terms, timeframe="now 7-d": _trend_frame({t: 99.0 for t in terms}, yesterday))
    by = _by_source(sn.run_snapshot())
    df = cache.read_narrative_series("pytrends", "AI crypto")
    assert df["raw_value"].tolist() == [55.0]
    assert df["source_status"].tolist() == ["backfilled"]
    assert by["pytrends"].skipped_existing == 1 and by["pytrends"].written == 3


def test_reddit_credentials_unset_writes_no_row_and_reports_reason(isolated_cache, providers, monkeypatch):
    monkeypatch.delenv("REDDIT_CLIENT_ID", raising=False)
    monkeypatch.delenv("REDDIT_CLIENT_SECRET", raising=False)
    summaries = sn.run_snapshot()
    by = _by_source(summaries)
    assert providers["reddit"] == 0
    assert not (isolated_cache / "narrative" / "reddit").exists()
    assert by["reddit"].line().startswith("reddit: unavailable (credentials-not-configured)")
    assert sn.exit_code(summaries) == 0


def test_partial_provider_failure_isolated(isolated_cache, providers, monkeypatch):
    def boom(terms, timeframe="now 7-d"):
        raise RuntimeError("google 429")
    monkeypatch.setattr(pytrends_adapter, "_fetch_batch_live", boom)
    monkeypatch.setattr(hl, "fetch_daily_market_snapshot",
                        lambda exchange=None, now=None: hl.ExchangeSnapshotResult(status="unavailable", as_of=TODAY,
                                                                                  reason="fetch-failed"))
    summaries = sn.run_snapshot()
    by = _by_source(summaries)
    assert by["pytrends"].failed == 4 and not by["pytrends"].available
    assert by["exchange"].line().startswith("exchange: unavailable")
    assert by["reddit"].written == 4 and by["coingecko-narrative"].written == 4
    assert sn.exit_code(summaries) == 0


def test_stale_trending_snapshot_is_not_archived_as_today(isolated_cache, providers, monkeypatch):
    monkeypatch.setattr(coingecko_adapter, "fetch_trending",
                        lambda *a, **k: TrendingResult(symbols=["FET"], as_of="2000-01-01", status="stale"))
    by = _by_source(sn.run_snapshot())
    assert by["coingecko-narrative"].written == 0
    assert not (isolated_cache / "narrative" / "coingecko-narrative").exists()


def test_all_sources_down_exit_2(isolated_cache, providers, monkeypatch):
    monkeypatch.setattr(pytrends_adapter, "_fetch_batch_live", lambda terms, timeframe="now 7-d": None)
    monkeypatch.delenv("REDDIT_CLIENT_ID", raising=False)
    monkeypatch.setattr(coingecko_adapter, "fetch_trending",
                        lambda *a, **k: TrendingResult(symbols=[], as_of=None, status="unavailable"))
    monkeypatch.setattr(hl, "fetch_daily_market_snapshot",
                        lambda exchange=None, now=None: hl.ExchangeSnapshotResult(status="unavailable", as_of=TODAY))
    assert sn.exit_code(sn.run_snapshot()) == 2


def test_dry_run_writes_nothing(isolated_cache, providers, capsys):
    before = _all_files(isolated_cache)
    rc = sn.main(["--dry-run"])
    out = capsys.readouterr().out
    assert rc == 0
    assert _all_files(isolated_cache) == before
    assert cache.CACHE_ROOT == isolated_cache
    assert "[dry-run] pytrends: ok written=4" in out


def test_verify_only_reports_counts_without_fetching(isolated_cache, providers, capsys):
    sn.run_snapshot()
    counts = dict(providers)
    assert sn.main(["--verify-only"]) == 0
    out = capsys.readouterr().out
    assert "pytrends/AI crypto: rows=1" in out and "coingecko-narrative/ai: rows=1" in out
    assert "exchange/ai: rows=1" in out
    assert providers == counts


# --- narrative-v2 RFC-3: batched multi-keyword blend ------------------------

def test_l2s_multi_keyword_blend_not_keywords0_only(isolated_cache, providers):
    """Regresses the SPEC bug: only keywords[0] was ever fetched."""
    by = _by_source(sn.run_snapshot())
    assert by["pytrends-blended"].written == 4
    l2s = cache.read_narrative_series("pytrends-blended", "l2s")
    # layer 2 crypto = 14, L2 rollup = 15 (anchor 10 in both batches -> scale 1)
    assert l2s["raw_value"].tolist() == [14.5]
    # primary keyword series still archived under its keyword key (ADR-2),
    # from the unbatched top-up (14 + 1000 stub offset)
    assert cache.read_narrative_series("pytrends", "layer 2 crypto")["raw_value"].tolist() == [1014.0]
    # blended rows never land under a keyword key
    assert not (isolated_cache / "narrative" / "pytrends" / "l2s.parquet").exists()


def test_snapshot_zero_anchor_batch_writes_nothing_for_that_batch(isolated_cache, providers, monkeypatch):
    def fake(terms, timeframe="now 7-d"):
        vals = {t: 50.0 for t in terms}
        if "memecoin" in terms:  # second batch: anchor collapses to 0
            vals["AI crypto"] = 0.0
        return _trend_frame(vals, TODAY)
    monkeypatch.setattr(pytrends_adapter, "_fetch_batch_live", fake)
    by = _by_source(sn.run_snapshot())
    assert cache.read_narrative_series("pytrends-blended", "memecoins").empty
    assert cache.read_narrative_series("pytrends-blended", "ai")["raw_value"].tolist() == [50.0]
    # primary rows come from the unbatched top-up, unaffected by the anchor collapse
    assert cache.read_narrative_series("pytrends", "memecoin")["raw_value"].tolist() == [1050.0]
    assert by["pytrends"].written == 4 and by["pytrends"].failed == 0


def test_primary_keyword_uses_unbatched_value_blend_uses_batched(isolated_cache, providers, monkeypatch):
    """Regresses RFC-3 scale drift: pytrends/{keywords[0]} (read by /categories)
    must come from the unbatched single-keyword fetch, not the batch."""
    monkeypatch.setattr(pytrends_adapter, "_fetch_live", lambda keyword: (77.0, TODAY))
    sn.run_snapshot()
    for kw in KWS:
        assert cache.read_narrative_series("pytrends", kw)["raw_value"].tolist() == [77.0], kw
    # blended still from the anchor-chained batch: layer 2 crypto 14 + L2 rollup 15
    assert cache.read_narrative_series("pytrends-blended", "l2s")["raw_value"].tolist() == [14.5]


def test_primary_topup_failure_skips_row_no_batched_fallback(isolated_cache, providers, monkeypatch):
    monkeypatch.setattr(pytrends_adapter, "_fetch_live", lambda keyword: (None, None))
    by = _by_source(sn.run_snapshot())
    for kw in KWS:
        assert cache.read_narrative_series("pytrends", kw).empty
    assert by["pytrends"].failed == 4 and by["pytrends"].written == 0
    assert by["pytrends-blended"].written == 4
