"""chain-growth RFC-1 probe: parsing/verdict logic against recorded-shape
fixtures. No network — every HTTP call goes through httpx.MockTransport."""
from __future__ import annotations

import argparse
import json

import httpx
import pytest

from api.scripts import probe_chain_sources as pcs

SECRET = "dune_test_SECRET_value_123"

MASTER = {
    "chains": {
        "ethereum": {"name": "Ethereum", "launch_date": "2015-07-30"},
        "base": {"name": "Base"},
        "arbitrum": {"name": "Arbitrum One"},
        "optimism": {"name": "OP Mainnet"},
        "robinhood_chain": {"name": "Robinhood Chain", "launch_date": "2026-07-01"},
    },
    "metrics": {"daa": {}, "txcount": {}, "fees": {}},
}
HISTORY = [
    {"origin_key": c, "metric_key": m, "date": d, "value": 1.0}
    for c in ("ethereum", "base", "arbitrum", "optimism", "robinhood_chain")
    for m in ("daa", "txcount")
    for d in (("2026-07-01", "2026-09-24") if c == "robinhood_chain" else ("2021-01-01", "2026-09-24"))
] + [{"origin_key": "base", "metric_key": "fees", "date": "2020-01-01", "value": 2.0}]
L2BEAT = {"success": True, "data": {"chart": {
    "types": ["timestamp", "count", "uopsCount"],
    "data": [[1719792000, 10, 12], [1727136000, 20, 25]],
}}}


def _args(**kw):
    return argparse.Namespace(max_credits=kw.get("max_credits", 50.0),
                              skip_solana_scale=kw.get("skip_solana_scale", False))


def make_client(dune_state="QUERY_STATE_COMPLETED", credits=2.0, gp_ok=True, l2_ok=True,
                execute_status=200, seen=None):
    def handler(req: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(req)
        url = str(req.url)
        if "growthepie" in url:
            if not gp_ok:
                return httpx.Response(503)
            return httpx.Response(200, json=MASTER if url.endswith("master.json") else HISTORY)
        if "l2beat" in url:
            if not l2_ok or url.endswith("/robinhood"):
                return httpx.Response(404, json={"success": False})
            return httpx.Response(200, json=L2BEAT)
        if "dune" in url:
            if url.endswith("/usage"):
                return httpx.Response(404)
            if url.endswith("/sql/execute"):
                return httpx.Response(execute_status, json={"execution_id": "E1", "state": "QUERY_STATE_PENDING"})
            if url.endswith("/status"):
                return httpx.Response(200, json={"state": dune_state, "execution_cost_credits": credits})
            if url.endswith("/results"):
                return httpx.Response(200, json={"result": {"rows": [{"ok": 1}]}})
        return httpx.Response(418)
    return httpx.Client(transport=httpx.MockTransport(handler))


# ---- pure parsing / verdicts -------------------------------------------------

def test_master_parse_finds_targets_robinhood_and_metrics():
    parsed = pcs.parse_growthepie_master(MASTER)
    assert all(parsed["targets_present"].values())
    assert parsed["robinhood_keys"] == ["robinhood_chain"]
    assert parsed["metrics_present"] == {"daa": True, "txcount": True}
    assert parsed["launch_dates"]["robinhood_chain"] == "2026-07-01"
    assert pcs.growthepie_master_verdict(parsed)[0] == pcs.PASS


def test_master_missing_chain_fails_and_absent_robinhood_is_reported():
    m = {"chains": {"ethereum": {}, "base": {}, "arbitrum": {}}, "metrics": {"daa": {}, "txcount": {}}}
    parsed = pcs.parse_growthepie_master(m)
    status, detail = pcs.growthepie_master_verdict(parsed)
    assert status == pcs.FAIL and "optimism" in detail
    ok = {"chains": {k: {} for k in pcs.GROWTHEPIE_TARGETS}, "metrics": {"daa": {}, "txcount": {}}}
    assert "NO robinhood" in pcs.growthepie_master_verdict(pcs.parse_growthepie_master(ok))[1]


@pytest.mark.parametrize("bad", [[], {"chains": []}, "x"])
def test_master_bad_shape_raises(bad):
    with pytest.raises(ValueError):
        pcs.parse_growthepie_master(bad)


def test_history_depth_first_last_and_ignores_other_metrics():
    targets = ["ethereum", "base", "arbitrum", "optimism", "robinhood_chain"]
    h = pcs.parse_growthepie_history(HISTORY, targets)
    assert h["base"]["daa"] == {"first": "2021-01-01", "last": "2026-09-24", "days": 2}
    assert h["robinhood_chain"]["txcount"]["first"] == "2026-07-01"
    assert "fees" not in h["base"]
    assert pcs.history_verdict(h, targets)[0] == pcs.PASS
    assert pcs.history_verdict({}, targets)[0] == pcs.FAIL
    assert pcs.history_verdict({"base": {"daa": {}}}, ["base"])[0] == pcs.UNKNOWN


def test_l2beat_parse_shape():
    info = pcs.parse_l2beat_activity(L2BEAT)
    assert info["points"] == 2 and info["has_uops"] and info["has_tx"]
    assert info["first"] == "2024-07-01"
    with pytest.raises(ValueError):
        pcs.parse_l2beat_activity({"data": {"chart": {}}})


def test_dune_credit_extraction_and_state_verdict():
    assert pcs.extract_dune_credits({"a": {"execution_cost_credits": 3}}) == 3.0
    assert pcs.extract_dune_credits({"credits": True}, {}) is None
    assert pcs.dune_state_verdict("QUERY_STATE_COMPLETED") == pcs.PASS
    assert pcs.dune_state_verdict("QUERY_STATE_FAILED") == pcs.FAIL
    assert pcs.dune_state_verdict(None) == pcs.UNKNOWN


def test_budget_math_uses_17_queries():
    ok = pcs.budget_math(4.0)
    assert ok["projected_monthly"] == 4.0 * 17 * 30 and ok["status"] == pcs.PASS
    assert pcs.budget_math(5.0)["status"] == pcs.FAIL  # 2550 > 2500
    assert pcs.budget_math(None)["status"] == pcs.UNKNOWN


def test_overall_precedence():
    mk = lambda s: pcs.ProbeItem("x", s, "")
    assert pcs.overall([mk(pcs.PASS)]) == pcs.PASS
    assert pcs.overall([mk(pcs.PASS), mk(pcs.UNKNOWN)]) == pcs.UNKNOWN
    assert pcs.overall([mk(pcs.UNKNOWN), mk(pcs.FAIL)]) == pcs.FAIL


def test_safe_serialize_refuses_secret():
    with pytest.raises(RuntimeError):
        pcs.safe_serialize({"x": f"leak {SECRET}"}, SECRET)
    assert SECRET not in pcs.redact(f"a {SECRET} b", SECRET)


# ---- end-to-end with mocked transport ---------------------------------------

def _by_id(result):
    return {i["id"]: i for i in result["items"]}


def test_full_run_happy_path_no_secret_in_output_and_header_used(monkeypatch):
    monkeypatch.setenv("DUNE_API_KEY", SECRET)
    seen: list[httpx.Request] = []
    res = pcs.run(_args(), client=make_client(seen=seen))
    items = _by_id(res)
    assert items["growthepie_master"]["status"] == pcs.PASS
    assert items["growthepie_history_depth"]["status"] == pcs.PASS
    assert items["l2beat_endpoint"]["status"] == pcs.PASS
    assert items["l2beat_activity_robinhood"]["status"] == pcs.UNKNOWN
    assert items["dune_execute"]["status"] == pcs.PASS
    assert items["dune_coverage_tron"]["status"] == pcs.PASS
    assert items["dune_budget_math"]["status"] == pcs.PASS
    assert items["dune_credits_spent"]["data"]["executions"] == 7
    assert SECRET not in pcs.safe_serialize(res, SECRET)
    dune_reqs = [r for r in seen if "dune" in str(r.url)]
    assert dune_reqs and all(r.headers["X-Dune-API-Key"] == SECRET for r in dune_reqs)
    assert all(SECRET not in str(r.url) for r in seen)


def test_credit_cap_skips_remaining_dune_executions(monkeypatch):
    monkeypatch.setenv("DUNE_API_KEY", SECRET)
    res = pcs.run(_args(max_credits=2.0), client=make_client(credits=2.0))
    items = _by_id(res)
    assert items["dune_execute"]["status"] == pcs.PASS
    assert items["dune_solana_scale_35d"]["status"] == pcs.UNKNOWN
    assert items["dune_credits_spent"]["data"]["executions"] == 1


def test_probes_are_independent_when_sources_fail(monkeypatch):
    monkeypatch.delenv("DUNE_API_KEY", raising=False)
    res = pcs.run(_args(), client=make_client(gp_ok=False))
    items = _by_id(res)
    assert items["growthepie_master"]["status"] == pcs.FAIL
    assert items["l2beat_endpoint"]["status"] == pcs.PASS
    assert items["dune_execute"]["status"] == pcs.UNKNOWN
    assert res["dune_key_present"] is False and res["overall"] == pcs.FAIL


def test_dune_auth_failure_is_fail_and_redacted(monkeypatch):
    monkeypatch.setenv("DUNE_API_KEY", SECRET)
    res = pcs.run(_args(), client=make_client(execute_status=401))
    items = _by_id(res)
    assert items["dune_execute"]["status"] == pcs.FAIL
    assert SECRET not in json.dumps(res)


def test_dune_timeout_is_fail(monkeypatch):
    t = iter(range(0, 1000, 60))
    client = make_client(dune_state="QUERY_STATE_EXECUTING")
    runner = pcs.DuneRunner(client, SECRET, 50.0, sleep=lambda s: None, clock=lambda: next(t))
    item = runner.run_sql("x", "SELECT 1")
    assert item.status == pcs.FAIL and "ceiling" in item.detail


def test_main_writes_json(tmp_path, monkeypatch):
    monkeypatch.setenv("DUNE_API_KEY", SECRET)
    monkeypatch.setattr(pcs, "run", lambda args: {"overall": "PASS", "items": []})
    out = tmp_path / "r.json"
    assert pcs.main(["--out", str(out)]) == 0
    assert json.loads(out.read_text())["overall"] == "PASS"
