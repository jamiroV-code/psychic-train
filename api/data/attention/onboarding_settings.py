"""Owner settings for automatic coin onboarding (T223, D-31): `api/data/coin_onboarding.json`.

`load` returns validated `Settings` or raises `ValueError` with a plain message; `safe_load` never raises and
returns (settings or None, reason). A bad file means the onboarding steps skip; nothing here can flip `mode`.
Owner edits (`confirmed_classes`, `blocked_sources`) live only in this file, never in bot-written files.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

SETTINGS_PATH = Path(__file__).resolve().parents[1] / "coin_onboarding.json"
MODES = ("shadow", "enforce")
DEFAULT_MODE = "shadow"
CLASSES = ("normal", "stablecoin", "wrapped_staked", "commodity_backed", "tokenized_fund")
SOURCES = ("wikipedia", "trends", "reddit_x")
SYMBOL_RE = re.compile(r"^[A-Z0-9_]{1,24}$")
INT_KEYS = {"probation_days": (1, 365), "exit_band_rank": (101, 250), "exit_days": (1, 365),
            "resolver_max_coins_per_run": (0, 100), "classify_max_coins_per_run": (0, 100),
            "identity_min_days": (1, 365), "wiki_min_days": (1, 365)}
FLOAT_KEYS = {"stable_band_pct": (0.0, 50.0), "identity_min_corr": (-1.0, 1.0)}
MAP_KEYS = ("confirmed_classes", "blocked_sources")
KEYS = {"mode", *INT_KEYS, *FLOAT_KEYS, *MAP_KEYS}


@dataclass(frozen=True)
class Settings:
    mode: str = DEFAULT_MODE
    probation_days: int = 14
    exit_band_rank: int = 120
    exit_days: int = 7
    resolver_max_coins_per_run: int = 5
    classify_max_coins_per_run: int = 15
    stable_band_pct: float = 2.0
    identity_min_days: int = 60
    identity_min_corr: float = 0.2
    wiki_min_days: int = 30
    confirmed_classes: dict = field(default_factory=dict)
    blocked_sources: dict = field(default_factory=dict)

    def blocked(self, symbol: str, source: str) -> bool:
        return source in self.blocked_sources.get(symbol, ())


def validate(doc) -> Settings:
    if not isinstance(doc, dict):
        raise ValueError("coin onboarding settings: the file must hold one JSON object")
    unknown = sorted(set(doc) - KEYS)
    if unknown:
        raise ValueError(f"coin onboarding settings: unknown keys {', '.join(unknown)}")
    missing = sorted(KEYS - set(doc))
    if missing:
        raise ValueError(f"coin onboarding settings: missing keys {', '.join(missing)}")
    if doc["mode"] not in MODES:
        raise ValueError(f"coin onboarding settings: mode must be one of {', '.join(MODES)}")
    for k, (lo, hi) in INT_KEYS.items():
        v = doc[k]
        if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
            raise ValueError(f"coin onboarding settings: {k} must be a whole number from {lo} to {hi}")
    for k, (lo, hi) in FLOAT_KEYS.items():
        v = doc[k]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not lo <= v <= hi:
            raise ValueError(f"coin onboarding settings: {k} must be a number from {lo:g} to {hi:g}")
    cc = doc["confirmed_classes"]
    if not isinstance(cc, dict) or not all(isinstance(s, str) and SYMBOL_RE.match(s) and c in CLASSES
                                           for s, c in cc.items()):
        raise ValueError(f"coin onboarding settings: confirmed_classes must map a symbol to one of "
                         f"{', '.join(CLASSES)}")
    bs = doc["blocked_sources"]
    if not isinstance(bs, dict) or not all(
            isinstance(s, str) and SYMBOL_RE.match(s) and isinstance(v, list) and v and all(x in SOURCES for x in v)
            for s, v in bs.items()):
        raise ValueError(f"coin onboarding settings: blocked_sources must map a symbol to a list of "
                         f"{', '.join(SOURCES)}")
    return Settings(mode=doc["mode"], **{k: doc[k] for k in INT_KEYS},
                    **{k: float(doc[k]) for k in FLOAT_KEYS},
                    confirmed_classes=dict(cc), blocked_sources={s: tuple(v) for s, v in bs.items()})


def load(path: Path | None = None) -> Settings:
    try:
        doc = json.loads((path or SETTINGS_PATH).read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"coin onboarding settings: cannot read the file ({type(exc).__name__})") from None
    except ValueError:
        raise ValueError("coin onboarding settings: the file is not valid JSON") from None
    return validate(doc)


def safe_load(path: Path | None = None) -> tuple[Settings | None, str]:
    try:
        return load(path), ""
    except ValueError as exc:
        return None, str(exc)
