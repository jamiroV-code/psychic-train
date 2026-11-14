"""Read-only onboarding view. All evidence comes from local files; no writes or provider calls."""
from __future__ import annotations

import json
from pathlib import Path

from api.data.attention import onboarding_resolver, onboarding_settings, onboarding_store as store
from api.data.attention import trends_keywords, web_queries
from api.models.discovery import OnboardingCoin, OnboardingResponse, OnboardingSource

WIKI_PATH = Path(__file__).resolve().parents[2] / "data" / "wiki_articles.json"


def build() -> OnboardingResponse:
    settings, _ = onboarding_settings.safe_load()
    settings = settings or onboarding_settings.Settings()
    ledger, state = store.read_ledger()
    result = OnboardingResponse(mode=settings.mode, status="corrupt" if state == "corrupt" else "no-ledger",
                                probation_days=settings.probation_days, exit_band_rank=settings.exit_band_rank,
                                exit_days=settings.exit_days)
    if ledger is None:
        return result
    result.status, result.as_of = "ok", ledger.get("last_advanced_date")
    pending_doc = store.read_json("pending.json") or {}
    proposal_doc = store.read_json("narrative_proposals.json") or {}
    pending_coins = pending_doc.get("coins", {})
    proposals = proposal_doc.get("coins", {})
    pending_coins = pending_coins if isinstance(pending_coins, dict) else {}
    proposals = proposals if isinstance(proposals, dict) else {}
    try:
        wiki_owner = json.loads(WIKI_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        wiki_owner = {}
    wiki, wiki_drops = onboarding_resolver.merge_wiki(wiki_owner, store.read_json("wiki_articles_auto.json"))
    keywords, _ = trends_keywords.safe_load_merged()
    symbols = [e["symbol"] for e in ledger["coins"].values()]
    try:
        # View only: expose valid proposed query names without adding them to the stream's placed set.
        queries = web_queries.merge_overlay(web_queries.load(), store.read_json(web_queries.OVERLAY_NAME), symbols)[0]
    except (OSError, ValueError):
        queries = None
    for entry in sorted(ledger["coins"].values(), key=lambda e: (e["state"] != "watching", e["symbol"])):
        symbol = entry["symbol"]
        pending = pending_coins.get(symbol, {})
        pending = pending if isinstance(pending, dict) else {}
        values = {"wikipedia": wiki.get(symbol), "trends": keywords.keyword_for(symbol) if keywords else None,
                  "reddit_x": queries.coins.get(symbol, {}).get("name") if queries else None}
        sources, items = {}, []
        for source, value in values.items():
            p = pending.get(source)
            p = p if isinstance(p, dict) else None
            outcome = entry.get("resolver", {}).get(source, {})
            if value:
                sources[source] = OnboardingSource(state="name", value=value)
            elif p:
                sources[source] = OnboardingSource(state="pending", reason=str(p.get("reason", "waiting for review")))
                items.append({"source": source, **p})
            else:
                sources[source] = OnboardingSource(state="none" if outcome.get("state") == "none" else "missing",
                                                   reason=outcome.get("reason") or "no name resolved")
        proposal = proposals.get(symbol, [])
        result.coins.append(OnboardingCoin(**store.sanitize({
            "symbol": symbol, "state": entry["state"], "days_in_top100": entry["consecutive_top100"],
            "class": entry["class"], "class_source": entry["class_source"],
            "class_evidence": entry["class_evidence"], "pending": items,
            "proposal": proposal if isinstance(proposal, list) else []}), sources=sources))
    return result
