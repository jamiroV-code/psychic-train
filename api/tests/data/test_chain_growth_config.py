"""Chain growth RFC-2: chains.json loader (AC-11), skip+warn validation."""
from __future__ import annotations

import json
import logging

from api.data import chain_growth_config as cfg


def _write(tmp_path, data):
    p = tmp_path / "chains.json"
    p.write_text(json.dumps(data) if not isinstance(data, str) else data)
    return p


def _chain(**over):
    base = {
        "id": "base",
        "label": "Base",
        "metrics": {"active_addresses": {"source": "growthepie", "source_key": "base"}},
    }
    base.update(over)
    return base


def test_shipped_config_loads_all_nine(caplog):
    with caplog.at_level(logging.WARNING):
        chains = cfg.load_chains()
    assert not caplog.records
    ids = [c.id for c in chains]
    assert ids == ["ethereum", "base", "arbitrum", "optimism", "polygon", "robinhood", "solana", "bnb", "tron"]
    by = {c.id: c for c in chains}
    assert by["polygon"].metric("active_addresses").source_key == "polygon_pos"
    assert by["optimism"].cross_check.source_key == "op-mainnet"
    assert by["robinhood"].launch_date == "2026-07-01" and by["robinhood"].limited_history is True
    for cid in ("solana", "bnb", "tron"):
        for m in cfg.METRICS:
            ms = by[cid].metric(m)
            assert ms.source == "none" and ms.unavailable_reason == "source-unavailable"
    for c in chains[:6]:
        assert [m for m, _ in c.metrics] == ["active_addresses", "transactions"]


def test_shipped_config_has_no_secrets_or_dune():
    text = cfg.CHAINS_PATH.read_text().lower()
    assert "dune" not in text and "api_key" not in text and "new_addresses" not in text


def test_bad_entries_skipped_with_warning(tmp_path, caplog):
    p = _write(tmp_path, {"chains": [
        _chain(),
        _chain(),  # duplicate
        _chain(id="Bad ID"),
        _chain(id="nolabel", label=""),
        _chain(id="baddate", launch_date="2026-13-01"),
        _chain(id="badsrc", metrics={"active_addresses": {"source": "dune", "source_key": "x"}}),
        _chain(id="nokey", metrics={"transactions": {"source": "growthepie"}}),
        _chain(id="secret", api_key="abc"),
        "not-an-object",
        _chain(id="ok2", enabled=False),
    ]})
    with caplog.at_level(logging.WARNING):
        chains = cfg.load_chains(p)
    assert [c.id for c in chains] == ["base", "ok2"]
    assert chains[1].enabled is False
    msgs = " ".join(r.getMessage() for r in caplog.records)
    for word in ("duplicate", "'Bad ID'", "label", "launch_date", "unknown source", "source_key", "secret"):
        assert word in msgs


def test_new_addresses_ignored_with_warning(tmp_path, caplog):
    p = _write(tmp_path, {"chains": [_chain(metrics={
        "active_addresses": {"source": "growthepie", "source_key": "base"},
        "new_addresses": {"source": "growthepie", "source_key": "base"},
    })]})
    with caplog.at_level(logging.WARNING):
        (c,) = cfg.load_chains(p)
    assert [m for m, _ in c.metrics] == ["active_addresses"]
    assert "new_addresses" in caplog.text


def test_source_none_default_reason(tmp_path):
    p = _write(tmp_path, {"chains": [_chain(metrics={"transactions": {"source": "none"}})]})
    (c,) = cfg.load_chains(p)
    assert c.metric("transactions") == cfg.MetricSource(source="none", unavailable_reason="source-unavailable")


def test_bad_cross_check_dropped_chain_kept(tmp_path, caplog):
    p = _write(tmp_path, {"chains": [_chain(cross_check={"source": "dune", "source_key": "x"})]})
    with caplog.at_level(logging.WARNING):
        (c,) = cfg.load_chains(p)
    assert c.cross_check is None and "cross_check" in caplog.text


def test_missing_or_broken_file_never_crashes(tmp_path, caplog):
    with caplog.at_level(logging.WARNING):
        assert cfg.load_chains(tmp_path / "nope.json") == []
        assert cfg.load_chains(_write(tmp_path, "{not json")) == []
        assert cfg.load_chains(_write(tmp_path, {"chains": "x"})) == []
    assert len(caplog.records) == 3
