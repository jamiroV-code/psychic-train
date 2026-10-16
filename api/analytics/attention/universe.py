"""The D-3 reference universe: top-100 symbols minus stablecoins and wrapped coins."""
from __future__ import annotations

import json
from pathlib import Path

UNIVERSE_PATH = Path(__file__).resolve().parents[2] / "data" / "attention_universe.json"


def load_reference(path: Path | None = None) -> list[str]:
    try:
        data = json.loads((path or UNIVERSE_PATH).read_text())
    except (OSError, ValueError):
        return []
    excluded = {str(s).upper() for k in ("stablecoins", "wrapped") for s in data.get(k, [])}
    seen: list[str] = []
    for s in data.get("reference", []):
        sym = str(s).upper()
        if sym not in excluded and sym not in seen:
            seen.append(sym)
    return seen
