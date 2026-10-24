"""Coin score: weighted mean of the available source ranks, weights renormalised."""
from __future__ import annotations

import json
from pathlib import Path

WEIGHTS_PATH = Path(__file__).resolve().parents[2] / "data" / "attention_weights.json"


def load_weights(path: Path | None = None) -> dict[str, float]:
    data = json.loads((path or WEIGHTS_PATH).read_text())
    return {str(k): float(v) for k, v in data.items() if float(v) > 0}


def coin_score(ranks: dict[str, float | None], weights: dict[str, float]) -> tuple[float | None, int, int]:
    """(score, sources_used, sources_total). A missing rank feeds nothing and is never 0."""
    used = {s: r for s, r in ranks.items() if r is not None}
    total_w = sum(weights.get(s, 1.0) for s in used)
    if not used or total_w <= 0:
        return None, 0, len(ranks)
    score = sum(r * weights.get(s, 1.0) for s, r in used.items()) / total_w
    return score, len(used), len(ranks)
