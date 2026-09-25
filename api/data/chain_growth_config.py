"""Loader for the user-editable chain list (`api/data/chains.json`).

Chain growth RFC-2 (ADR-6, fallback form: growthepie + L2BEAT only, no Dune).
Same posture as `analytics/narrative/mapping.load_category_map`: hand-edited
JSON, validated on load, bad entries skipped with a warning naming them —
never a crash. A missing or unparseable file loads an empty list.

Metrics: `active_addresses`, `transactions`. Any other metric key (for
example `new_addresses`, which has no free source) is ignored with a warning.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

CHAINS_PATH = Path(__file__).resolve().parent / "chains.json"

METRICS: tuple[str, ...] = ("active_addresses", "transactions")
METRIC_SOURCES = frozenset({"growthepie", "none"})
CROSS_CHECK_SOURCES = frozenset({"l2beat"})
DEFAULT_UNAVAILABLE_REASON = "source-unavailable"

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_FORBIDDEN_FIELD_RE = re.compile(r"(api_?key|secret|token|password)", re.IGNORECASE)


@dataclass(frozen=True)
class MetricSource:
    source: str  # "growthepie" | "none"
    source_key: str | None = None
    unavailable_reason: str | None = None


@dataclass(frozen=True)
class CrossCheck:
    source: str  # "l2beat"
    source_key: str


@dataclass(frozen=True)
class ChainConfig:
    id: str
    label: str
    enabled: bool
    launch_date: str | None
    limited_history: bool
    metrics: tuple[tuple[str, MetricSource], ...]
    cross_check: CrossCheck | None = None

    def metric(self, name: str) -> MetricSource | None:
        return dict(self.metrics).get(name)


def _has_forbidden_field(obj: object) -> str | None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and _FORBIDDEN_FIELD_RE.search(k):
                return k
            hit = _has_forbidden_field(v)
            if hit:
                return hit
    return None


def _valid_date(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _parse_metric(chain_id: str, name: str, raw: object) -> MetricSource | None:
    where = f"chain {chain_id!r} metric {name!r}"
    if not isinstance(raw, dict):
        logger.warning("chains config: skipping %s (not an object)", where)
        return None
    source = raw.get("source")
    if source not in METRIC_SOURCES:
        logger.warning("chains config: skipping %s (unknown source %r; allowed: %s)", where, source, sorted(METRIC_SOURCES))
        return None
    if source == "growthepie":
        key = raw.get("source_key")
        if not isinstance(key, str) or not key.strip():
            logger.warning("chains config: skipping %s (growthepie needs a non-empty source_key)", where)
            return None
        return MetricSource(source="growthepie", source_key=key.strip())
    reason = raw.get("unavailable_reason", DEFAULT_UNAVAILABLE_REASON)
    if not isinstance(reason, str) or not reason.strip():
        reason = DEFAULT_UNAVAILABLE_REASON
    return MetricSource(source="none", unavailable_reason=reason.strip())


def _parse_cross_check(chain_id: str, raw: object) -> CrossCheck | None:
    if raw is None:
        return None
    if (
        not isinstance(raw, dict)
        or raw.get("source") not in CROSS_CHECK_SOURCES
        or not isinstance(raw.get("source_key"), str)
        or not raw["source_key"].strip()
    ):
        logger.warning("chains config: dropping cross_check for chain %r (need source 'l2beat' and a source_key)", chain_id)
        return None
    return CrossCheck(source=raw["source"], source_key=raw["source_key"].strip())


def _parse_chain(raw: object, seen: set[str]) -> ChainConfig | None:
    if not isinstance(raw, dict):
        logger.warning("chains config: skipping entry %r (not an object)", raw)
        return None
    chain_id = raw.get("id")
    if not isinstance(chain_id, str) or not _ID_RE.match(chain_id):
        logger.warning("chains config: skipping entry with id %r (need a lowercase id)", chain_id)
        return None
    if chain_id in seen:
        logger.warning("chains config: skipping duplicate chain id %r", chain_id)
        return None
    forbidden = _has_forbidden_field(raw)
    if forbidden:
        logger.warning("chains config: skipping chain %r (field %r looks like a secret; secrets never go in chains.json)", chain_id, forbidden)
        return None
    label = raw.get("label")
    if not isinstance(label, str) or not label.strip():
        logger.warning("chains config: skipping chain %r (missing label)", chain_id)
        return None
    enabled = raw.get("enabled", True)
    if not isinstance(enabled, bool):
        logger.warning("chains config: skipping chain %r (enabled must be true/false)", chain_id)
        return None
    launch = raw.get("launch_date")
    if launch is not None and not _valid_date(launch):
        logger.warning("chains config: skipping chain %r (launch_date must be YYYY-MM-DD or null)", chain_id)
        return None
    limited = raw.get("limited_history", False)
    if not isinstance(limited, bool):
        logger.warning("chains config: skipping chain %r (limited_history must be true/false)", chain_id)
        return None
    raw_metrics = raw.get("metrics")
    if not isinstance(raw_metrics, dict):
        logger.warning("chains config: skipping chain %r (metrics must be an object)", chain_id)
        return None
    metrics: list[tuple[str, MetricSource]] = []
    for name, spec in raw_metrics.items():
        if name not in METRICS:
            logger.warning("chains config: ignoring unknown metric %r on chain %r (allowed: %s)", name, chain_id, list(METRICS))
            continue
        parsed = _parse_metric(chain_id, name, spec)
        if parsed is not None:
            metrics.append((name, parsed))
    if not metrics:
        logger.warning("chains config: skipping chain %r (no valid metrics)", chain_id)
        return None
    metrics.sort(key=lambda m: METRICS.index(m[0]))
    seen.add(chain_id)
    return ChainConfig(
        id=chain_id,
        label=label.strip(),
        enabled=enabled,
        launch_date=launch,
        limited_history=limited,
        metrics=tuple(metrics),
        cross_check=_parse_cross_check(chain_id, raw.get("cross_check")),
    )


def load_chains(path: Path | None = None) -> list[ChainConfig]:
    """All valid chains in file order (disabled ones included; callers filter
    on `enabled`). Never raises."""
    path = CHAINS_PATH if path is None else path
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        logger.warning("chains config: %s not found; loading no chains", path)
        return []
    except (OSError, ValueError) as exc:
        logger.warning("chains config: could not parse %s (%s); loading no chains", path, exc)
        return []
    if not isinstance(data, dict) or not isinstance(data.get("chains"), list):
        logger.warning("chains config: %s must be an object with a \"chains\" list; loading no chains", path)
        return []
    seen: set[str] = set()
    out = []
    for raw in data["chains"]:
        chain = _parse_chain(raw, seen)
        if chain is not None:
            out.append(chain)
    return out
