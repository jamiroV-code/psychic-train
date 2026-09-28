"""narrative-v2 RFC-7 (ADR-7 items 3-4): real-cache-boundary proofs.

- `NARRATIVES_PATH` override: unset resolves to the real tracked file
  (production unaffected); set redirects every loader call.
- Round trips through the real cache writer/reader for the `pytrends-blended`
  namespace and through the real `narratives.json` loader.
- AC-8: the seeder's 6- and 15-narrative fixtures, served by the real
  `/history`, `/momentum` and `/mindshare` routes — every narrative present in
  every cross-narrative view, none silently truncated.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.analytics.narrative import history, narrative_config
from api.data import cache
from api.scripts import seed_e2e_cache as seeder

REAL = Path(narrative_config.__file__).resolve().parents[2] / "data" / "narratives.json"


def test_narratives_path_unset_resolves_to_real_file(monkeypatch):
    monkeypatch.delenv(narrative_config.NARRATIVES_PATH_ENV, raising=False)
    assert narrative_config.default_narratives_path().resolve() == REAL
    assert narrative_config.NARRATIVES_PATH.resolve() == REAL


def test_narratives_path_env_redirects_loader(tmp_path, monkeypatch):
    path = tmp_path / "n.json"
    path.write_text(json.dumps({"version": 2, "narratives": [
        {"id": "solo", "label": "Solo", "keywords": ["solo crypto"], "coins": ["SOL"]}]}), encoding="utf-8")
    monkeypatch.setenv(narrative_config.NARRATIVES_PATH_ENV, str(path))
    assert [n["id"] for n in narrative_config.load_narratives()] == ["solo"]


def test_pytrends_blended_namespace_round_trip(isolated_cache):
    for d, v in (("2026-09-01", 10.0), ("2026-09-02", 20.0), ("2026-09-02", 30.0)):
        cache.write_narrative_point(history.PYTRENDS_BLENDED_SOURCE, "x01", d, v)
    assert cache.narrative_series_path("pytrends-blended", "x01").is_relative_to(isolated_cache)
    back = cache.read_narrative_series("pytrends-blended", "x01")
    assert list(back.columns) == cache.NARRATIVE_COLUMNS
    assert list(back["date"]) == ["2026-09-01", "2026-09-02"]
    assert list(back["raw_value"]) == [10.0, 30.0]  # same-day rewrite replaces


def test_seeder_refuses_real_narratives_path(monkeypatch):
    monkeypatch.setenv(narrative_config.NARRATIVES_PATH_ENV, str(REAL))
    with pytest.raises(SystemExit):
        seeder._narratives_path()
    monkeypatch.delenv(narrative_config.NARRATIVES_PATH_ENV)
    with pytest.raises(SystemExit):
        seeder._narratives_path()


@pytest.mark.parametrize("n", [5, 16])
def test_config_builder_rejects_out_of_range(n):
    with pytest.raises(ValueError):
        seeder.build_narrative_v2_configs({"narratives": []}, n)


@pytest.mark.parametrize("n", [seeder.NARRATIVE_V2_MIN, seeder.NARRATIVE_V2_MAX])
def test_ac8_every_view_covers_every_narrative(n, isolated_cache, tmp_path, monkeypatch):
    from api.main import app

    real_before = REAL.read_bytes()
    monkeypatch.setenv(narrative_config.NARRATIVES_PATH_ENV, str(tmp_path / "cfg" / "narratives.json"))
    facts = seeder.seed_narrative(pd.Timestamp.now(tz="UTC").tz_localize(None).normalize(), n_narratives=n)
    v2 = facts["v2"]
    # Swap the n-variant in; the loader picks it up on the next call (AC-4 path).
    Path(v2["narratives_path"]).write_text(Path(v2["variants"][str(n)]["path"]).read_text(), encoding="utf-8")
    ids = v2["variants"][str(n)]["ids"]
    assert len(ids) == n

    client = TestClient(app)
    hist = client.get("/api/narrative/history").json()
    assert [c["category_id"] for c in hist["categories"]] == ids
    assert sorted(e["category_id"] for e in hist["comparison"]["entries"]) == sorted(ids)
    assert sorted(e["category_id"] for e in hist["change_in_attention"]["entries"]) == sorted(ids)

    mom = client.get("/api/narrative/momentum").json()
    by_id = {e["category_id"]: e for e in mom["entries"]}
    assert sorted(by_id) == sorted(ids)
    for nid in v2["mature"]:
        assert by_id[nid]["status"] == "ok" and by_id[nid]["momentum_basis"] == "pytrends-blended"
        assert by_id[nid]["rank"] is not None
    for nid in v2["thin"] + v2["no_data"]:
        assert by_id[nid]["status"] == "insufficient" and by_id[nid]["rank"] is None and by_id[nid]["reason"]
    ranks = sorted(e["rank"] for e in mom["entries"] if e["rank"] is not None)
    assert ranks[0] == 1 and len(ranks) >= len(v2["mature"])

    ms = client.get("/api/narrative/mindshare").json()
    ms_ids = {e["category_id"]: e for e in ms["entries"]}
    assert sorted(ms_ids) == sorted(ids)
    assert sum(e["mindshare"] for e in ms["entries"] if e["mindshare"] is not None) == pytest.approx(1.0)
    for nid in v2["no_data"]:
        assert ms_ids[nid]["status"] == "excluded" and ms_ids[nid]["mindshare"] is None
    for nid in v2["mature"]:
        assert ms_ids[nid]["mindshare"] > 0

    assert REAL.read_bytes() == real_before  # the tracked config was never written
