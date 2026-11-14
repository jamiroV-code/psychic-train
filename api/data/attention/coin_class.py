"""Automatic coin class for onboarding (T223 O3, D-31). Pure rules, no I/O.

Evidence per coin: CoinGecko coin-detail `categories`, `name`, `asset_platform_id` (shapes UNVERIFIED live until
probe P-O0) and derived price numbers (`price_min`, `price_max`, `n_days`, `last_price`; the series is never kept).

Rules, first match wins:
- stablecoin: a stablecoin category OR a USD/EUR-style symbol or name, AND a tight price window (max over min under
  `stable_band_pct`); one signal alone is not enough;
- wrapped_staked: a wrapped, liquid-staking or bridged category, or a wrapped/staked/bridged name;
- commodity_backed: a tokenized gold or commodity category;
- tokenized_fund: a tokenized treasury or fund category;
- a tight price window with none of the above stays `unknown` (price alone never classes a coin);
- normal: only when the category list is non-empty and nothing matched;
- anything else (empty or failed response) is `unknown`, never `normal`.
The owner's class lists in discovery.json win (`owner`), then `confirmed_classes` in coin_onboarding.json
(`confirmed`), then this rule (`auto`).
"""
from __future__ import annotations

import math
import re

from api.data.attention.onboarding_store import sanitize

MAX_CATEGORIES = 10
STABLE_CATS = ("stablecoin",)
WRAPPED_CATS = ("wrapped", "liquid staking", "liquid restaking", "bridged", "staked")
COMMODITY_CATS = ("tokenized gold", "gold-backed", "commodity-backed", "tokenized commodit")
FUND_CATS = ("tokenized treasury", "tokenized treasuries", "tokenized fund", "tokenized money market", "t-bills")
STABLE_SYMBOL = re.compile(r"(USD|EUR)")
STABLE_NAME = re.compile(r"\b(usd|dollar|euro)\b", re.I)
WRAPPED_NAME = re.compile(r"\b(wrapped|staked|bridged)\b", re.I)


def _has(cats: list[str], needles: tuple[str, ...]) -> bool:
    return any(n in c for c in cats for n in needles)


def price_stats(points) -> dict | None:
    """Derived numbers from a market_chart `prices` list ([ms, price], ...); None when no usable price."""
    vals = [float(p[1]) for p in points or [] if isinstance(p, (list, tuple)) and len(p) == 2
            and isinstance(p[1], (int, float)) and not isinstance(p[1], bool) and math.isfinite(p[1]) and p[1] > 0]
    if not vals:
        return None
    return {"price_min": min(vals), "price_max": max(vals), "n_days": len(vals), "last_price": vals[-1]}


def _tight(prices, band_pct: float, min_days: int) -> bool:
    if not isinstance(prices, dict):
        return False
    lo, hi, n = prices.get("price_min"), prices.get("price_max"), prices.get("n_days")
    if not all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in (lo, hi, n)) or lo <= 0:
        return False
    return n >= min_days and hi / lo < 1 + band_pct / 100.0


def classify(symbol: str, evidence: dict | None, settings) -> tuple[str, dict]:
    """(class, evidence summary for the ledger). `evidence` None or without a category list = a failed fetch."""
    if not isinstance(evidence, dict) or not isinstance(evidence.get("categories"), list):
        why = evidence.get("error") if isinstance(evidence, dict) else None
        return "unknown", sanitize({"reason": why or "no coin detail"})
    raw = [str(c) for c in evidence["categories"] if isinstance(c, str) and c.strip()]
    cats = [c.casefold() for c in raw]
    name = str(evidence.get("name") or "")
    prices = evidence.get("prices")
    tight = _tight(prices, settings.stable_band_pct, settings.price_min_days)
    summary = {"categories": raw[:MAX_CATEGORIES], "asset_platform_id": evidence.get("asset_platform_id"),
               **(prices if isinstance(prices, dict) else {})}
    stable_signal = _has(cats, STABLE_CATS) or bool(STABLE_SYMBOL.search(symbol.upper()) or STABLE_NAME.search(name))
    if stable_signal and tight:
        cls = "stablecoin"
    elif _has(cats, WRAPPED_CATS) or WRAPPED_NAME.search(name):
        cls = "wrapped_staked"
    elif _has(cats, COMMODITY_CATS):
        cls = "commodity_backed"
    elif _has(cats, FUND_CATS):
        cls = "tokenized_fund"
    elif tight or stable_signal or not cats:
        cls = "unknown"
    else:
        cls = "normal"
    return cls, sanitize(summary)


def resolve(symbol: str, auto_class: str, owner_rules: dict, settings) -> tuple[str, str]:
    """(class, class_source): owner lists, then confirmed, then the automatic class."""
    for name, syms in (owner_rules.get("classes") or {}).items():
        if symbol in syms:
            return name, "owner"
    if symbol in settings.confirmed_classes:
        return settings.confirmed_classes[symbol], "confirmed"
    return auto_class, "auto"
