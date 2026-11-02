"""T223 O3: the pure coin classifier (AC6, AC7). Two signals for a stablecoin; price alone never classes a coin."""
from __future__ import annotations

import pytest

from api.data.attention import coin_class as cc
from api.data.attention.onboarding_settings import Settings

S = Settings()
PEG = {"price_min": 0.998, "price_max": 1.003, "n_days": 30, "last_price": 1.0}
WIDE = {"price_min": 0.5, "price_max": 1.4, "n_days": 30, "last_price": 1.1}


def ev(categories=("Layer 1 (L1)",), name="Coin", prices=WIDE, platform=None):
    return {"categories": list(categories) if categories is not None else None, "name": name,
            "asset_platform_id": platform, "prices": prices}


@pytest.mark.parametrize("evidence, symbol, want", [
    (ev(("Stablecoins", "USD Stablecoin"), "Pay Dollar", PEG), "PDX", "stablecoin"),     # category and band
    (ev(("Ethereum Ecosystem",), "Ripple USD", PEG), "RLUSD", "stablecoin"),             # pattern and band
    (ev(("Stablecoins",), "Depegged", WIDE), "DPG", "unknown"),                          # category only
    (ev(("Stablecoins",), "No prices", None), "NPX", "unknown"),                         # category, no price
    (ev(("Meme",), "Calm Coin", PEG), "CALM", "unknown"),                                # band only: one signal
    (ev((), "Near One", PEG), "NONE", "unknown"),                                        # near 1.00, no category
    (ev(("Wrapped-Tokens",), "Something", WIDE), "WSX", "wrapped_staked"),
    (ev(("Liquid Staking Tokens",), "Staked Foo", WIDE), "SFOO", "wrapped_staked"),
    (ev(("Bridged Tokens",), "Foo", WIDE), "FOO", "wrapped_staked"),
    (ev(("DeFi",), "Wrapped Bar", WIDE), "WBAR", "wrapped_staked"),                      # name pattern
    (ev(("Tokenized Gold",), "Gold Token", WIDE), "GLD", "commodity_backed"),
    (ev(("Tokenized Treasury Bills (T-Bills)",), "Fund", PEG), "TBF", "tokenized_fund"),
    (ev(("Smart Contract Platform", "Layer 1 (L1)"), "Chain", WIDE), "CHN", "normal"),
    (ev((), "Empty", WIDE), "EMP", "unknown"),
    (ev(None, "Failed", None), "FLD", "unknown"),
])
def test_rules(evidence, symbol, want):
    cls, summary = cc.classify(symbol, evidence, S)
    assert cls == want
    assert isinstance(summary, dict) and "prices" not in summary


def test_failed_fetch_is_unknown_never_normal():
    assert cc.classify("X", None, S)[0] == "unknown"
    assert cc.classify("X", {"categories": None, "error": "HTTP 503"}, S)[0] == "unknown"


def test_band_comes_from_settings():
    soft = {"price_min": 1.0, "price_max": 1.03, "n_days": 30, "last_price": 1.0}
    assert cc.classify("DPG", ev(("Stablecoins",), "x", soft), S)[0] == "unknown"
    assert cc.classify("DPG", ev(("Stablecoins",), "x", soft), Settings(stable_band_pct=5.0))[0] == "stablecoin"


def test_short_price_history_is_no_band():
    few = {**PEG, "n_days": 3}
    assert cc.classify("PDX", ev(("Stablecoins",), "x", few), S)[0] == "unknown"


def test_owner_list_wins_then_confirmed_then_auto():
    rules = {"classes": {"stablecoin": ["OWN"]}}
    s = Settings(confirmed_classes={"CNF": "normal", "OWN": "normal"})
    assert cc.resolve("OWN", "unknown", rules, s) == ("stablecoin", "owner")
    assert cc.resolve("CNF", "stablecoin", rules, s) == ("normal", "confirmed")
    assert cc.resolve("AUT", "wrapped_staked", rules, s) == ("wrapped_staked", "auto")
    assert cc.resolve("AUT", "unknown", rules, s) == ("unknown", "auto")


def test_price_stats_are_derived_numbers_only():
    pts = [[1_700_000_000_000 + i * 86_400_000, 1.0 + (i % 3) * 0.001] for i in range(30)]
    st = cc.price_stats(pts)
    assert st == {"price_min": 1.0, "price_max": 1.002, "n_days": 30, "last_price": pts[-1][1]}
    assert cc.price_stats([]) is None and cc.price_stats([[1, "x"], [2, -1]]) is None


def test_evidence_summary_is_capped_and_sanitized():
    cats = [f"Cat\u202e{i}" for i in range(40)]
    _, summary = cc.classify("X", ev(cats, "N", WIDE), S)
    assert len(summary["categories"]) == cc.MAX_CATEGORIES and "\u202e" not in "".join(summary["categories"])
