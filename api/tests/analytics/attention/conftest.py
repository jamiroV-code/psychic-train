"""Shared builders for S-C tests: stored series with a known 7/90 ratio, tmp configs."""
from __future__ import annotations

import json
from datetime import date, timedelta

from api.data.attention import store
from api.data.attention.types import SourceSeries
from api.models.layout import Layout, LayoutGroup

TODAY = date(2026, 10, 16)
SOURCES = ("wikipedia", "coingecko", "trends")
REFS = ("R1", "R2", "R3", "R4")


def put(source: str, symbol: str, last7: float, days: int = 130) -> None:
    """`days` completed days ending yesterday: flat 1.0, the last 7 equal `last7`."""
    end = TODAY - timedelta(days=1)
    pts = []
    for i in range(days):
        d = end - timedelta(days=days - 1 - i)
        pts.append((d, last7 if i >= days - 7 else 1.0))
    store.write_series(SourceSeries(source, symbol, pts, "ok"), today=TODAY)


def put_refs(sources=SOURCES) -> None:
    for s in sources:
        for i, r in enumerate(REFS):
            put(s, r, float(i + 1))


def write_configs(tmp_path, sources=SOURCES, weights=None, reference=REFS):
    probe = tmp_path / "probe_records.json"
    probe.write_text(json.dumps({s: {"probed": True} for s in sources}))
    w = tmp_path / "weights.json"
    w.write_text(json.dumps(weights or {s: 1.0 for s in SOURCES}))
    u = tmp_path / "universe.json"
    u.write_text(json.dumps({"reference": list(reference), "stablecoins": ["USDT"], "wrapped": ["WBTC"]}))
    return probe, w, u


def make_layout(groups: dict[str, list[str]], names=None) -> Layout:
    names = names or {}
    return Layout(version=1, section="crypto", revision=1, saved_at="2026-10-15T10:00:00Z",
                  source="file", hidden_lines=[],
                  groups=[LayoutGroup(id=k, name=names.get(k, k.title()), coins=v) for k, v in groups.items()])
