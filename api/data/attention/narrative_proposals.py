"""T223: category evidence proposes every matching narrative; never changes placement."""
from __future__ import annotations


def build(ledger: dict, snapshot: dict | None, id_map: dict, placed: set[str]) -> dict:
    snapshot = snapshot or {}
    eligible = {e["symbol"] for e in ledger["coins"].values()
                if e["state"] == "member" and e["class"] == "normal" and e["symbol"] not in placed}
    coins: dict[str, list[dict]] = {}
    for row in snapshot.get("categories", []):
        category = row.get("id")
        narrative = id_map.get(category, {}).get("narrative")
        if not narrative:
            continue
        for symbol in sorted(eligible.intersection(row.get("symbols", []))):
            coins.setdefault(symbol, []).append({"narrative": narrative, "category": category,
                                                 "as_of": snapshot.get("date")})
    return {"as_of": snapshot.get("date"), "coins": coins}


def refresh(ledger: dict) -> None:
    # Imports remain data-only; the mapping is an owner JSON document, not analytics code.
    import json
    from pathlib import Path
    from api.data.attention import categories_store, onboarding_store, web_queries

    path = Path(__file__).resolve().parents[1] / "attention_narrative_id_map.json"
    mapping = json.loads(path.read_text(encoding="utf-8"))["map"]
    result = build(ledger, categories_store.read_latest(), mapping, set(web_queries.placed_symbols()))
    onboarding_store.write_json("narrative_proposals.json", result)
