"""RFC-1 feasibility probe for the chain-growth (`/onchain-activity`) plan.

User-run only: this repo's dev container cannot reach Dune, growthepie or
L2BEAT. Run it on your own machine from the repo root:

    uv run --project api python -m api.scripts.probe_chain_sources

Secret handling (plan RFC-1 P1 / E3): `DUNE_API_KEY` is read from the
environment only. It is never printed, logged or written. Before the result
JSON is written, the serialized text is checked for the key's literal value
and the write is refused if it appears anywhere.

Every probe runs on its own and reports PASS / FAIL / UNKNOWN. One probe
failing never stops the others.

Dune credit spend: at most 1 + 1 + 5 = 7 executions (1 trivial `SELECT 1`,
1 bounded Solana 35-day unique-signer query, 5 one-hour max(block_time)
coverage queries). Spend is guarded by `--max-credits` (default 50): once the
credits Dune reports as consumed reach the cap, remaining Dune executions are
skipped (UNKNOWN). Use `--skip-solana-scale` to drop the heaviest query.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

import httpx

PASS, FAIL, UNKNOWN = "PASS", "FAIL", "UNKNOWN"

DUNE_BASE = "https://api.dune.com/api/v1"
GROWTHEPIE_HOSTS = ("https://api.growthepie.xyz", "https://api.growthepie.com")
L2BEAT_CANDIDATES = (
    "https://l2beat.com/api/scaling/activity",
    "https://api.l2beat.com/api/scaling/activity",
)

# growthepie chain keys we need (ADR-1). robinhood is unverified: we search.
GROWTHEPIE_TARGETS = ("ethereum", "base", "arbitrum", "optimism")
ROBINHOOD_HINT = "robinhood"
GROWTHEPIE_METRICS = ("daa", "txcount")
L2BEAT_PROJECTS = ("base", "arbitrum", "optimism", "robinhood")

# Dune chain-coverage probes: tiny one-hour window queries.
DUNE_COVERAGE_TABLES = {
    "solana": "solana.transactions",
    "bnb": "bnb.transactions",
    "tron": "tron.transactions",
    "polygon": "polygon.transactions",
    "robinhood": "robinhood.transactions",
}
TRIVIAL_SQL = "SELECT 1 AS ok"
SOLANA_SCALE_SQL = (
    "SELECT date_trunc('day', block_time) AS day, "
    "count(DISTINCT signer) AS daa "
    "FROM solana.transactions "
    "WHERE block_time >= now() - interval '35' day "
    "GROUP BY 1 ORDER BY 1"
)
DUNE_POLL_CEILING_S = 115.0  # hard ceiling under Dune's 2-min small-engine limit
FREE_TIER_MONTHLY_CREDITS = 2500
NIGHTLY_QUERY_COUNT = 17  # plan RFC-1: 4 chains x 3 metrics + 5 chains x new_addresses

DEFAULT_OUT = (
    Path(__file__).resolve().parents[2]
    / "process/features/onchain-activity/active/chain-growth_25-09-26"
    / "chain-growth-probe-result_25-09-26.json"
)


@dataclass
class ProbeItem:
    id: str
    status: str
    detail: str
    data: dict[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------
# Pure parsing / verdict logic (unit-tested with fixtures, no network)
# --------------------------------------------------------------------------

def parse_growthepie_master(master: Any) -> dict[str, Any]:
    """Return {chain_keys, targets_present, robinhood_keys, metric_keys}."""
    if not isinstance(master, dict):
        raise ValueError("master.json is not a JSON object")
    chains = master.get("chains")
    if not isinstance(chains, dict):
        raise ValueError("master.json has no 'chains' object")
    keys = sorted(chains.keys())
    metrics = master.get("metrics")
    metric_keys = sorted(metrics.keys()) if isinstance(metrics, dict) else []
    robinhood = [
        k for k in keys
        if ROBINHOOD_HINT in k.lower()
        or ROBINHOOD_HINT in str((chains[k] or {}).get("name", "")).lower()
    ]
    launch = {
        k: (chains[k] or {}).get("launch_date")
        for k in [*GROWTHEPIE_TARGETS, *robinhood] if k in chains
    }
    return {
        "chain_keys": keys,
        "targets_present": {t: t in chains for t in GROWTHEPIE_TARGETS},
        "robinhood_keys": robinhood,
        "metric_keys": metric_keys,
        "metrics_present": {m: m in metric_keys for m in GROWTHEPIE_METRICS},
        "launch_dates": launch,
    }


def growthepie_master_verdict(parsed: dict[str, Any]) -> tuple[str, str]:
    missing = [t for t, ok in parsed["targets_present"].items() if not ok]
    missing_m = [m for m, ok in parsed["metrics_present"].items() if not ok]
    if missing or missing_m:
        return FAIL, f"missing chains {missing} / metrics {missing_m}"
    rh = parsed["robinhood_keys"]
    rh_note = f"robinhood key(s): {rh}" if rh else "NO robinhood key found"
    return PASS, f"all 4 target chains + daa/txcount present; {rh_note}"


def parse_growthepie_history(rows: Any, chain_keys: list[str]) -> dict[str, dict[str, Any]]:
    """fundamentals_full.json rows -> {chain: {metric: {first, last, days}}}."""
    if not isinstance(rows, list):
        raise ValueError("history export is not a JSON list")
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        chain, metric, date = r.get("origin_key"), r.get("metric_key"), r.get("date")
        if chain not in chain_keys or metric not in GROWTHEPIE_METRICS or not date:
            continue
        cell = out.setdefault(chain, {}).setdefault(metric, {"first": date, "last": date, "days": 0})
        cell["first"] = min(cell["first"], date)
        cell["last"] = max(cell["last"], date)
        cell["days"] += 1
    return out


def history_verdict(history: dict[str, dict[str, Any]], chain_keys: list[str]) -> tuple[str, str]:
    gaps = [
        f"{c}/{m}" for c in chain_keys for m in GROWTHEPIE_METRICS
        if m not in history.get(c, {})
    ]
    if not history:
        return FAIL, "no daa/txcount rows for any target chain"
    if gaps:
        return UNKNOWN, f"history missing for {gaps}"
    return PASS, "daa/txcount history found for every target chain"


def parse_l2beat_activity(payload: Any) -> dict[str, Any]:
    """Extract chart column types + date range from an L2BEAT activity response."""
    if not isinstance(payload, dict):
        raise ValueError("L2BEAT response is not a JSON object")
    data = payload.get("data", payload)
    chart = data.get("chart", data) if isinstance(data, dict) else {}
    types = chart.get("types") if isinstance(chart, dict) else None
    points = chart.get("data") if isinstance(chart, dict) else None
    if not isinstance(types, list) or not isinstance(points, list) or not points:
        raise ValueError("no chart.types / chart.data in L2BEAT response")
    ts = [p[0] for p in points if isinstance(p, list) and p]
    def iso(t: Any) -> Any:
        return dt.datetime.fromtimestamp(t, tz=dt.timezone.utc).date().isoformat() if isinstance(t, (int, float)) else t
    return {
        "types": types,
        "points": len(points),
        "first": iso(min(ts)) if ts else None,
        "last": iso(max(ts)) if ts else None,
        "has_uops": any("uops" in str(t).lower() for t in types),
        "has_tx": any(str(t).lower() in ("count", "txcount", "transactions") or "tx" in str(t).lower() for t in types),
    }


def extract_dune_credits(*payloads: Any) -> float | None:
    """Find a credit figure in Dune status/results payloads (key names vary)."""
    keys = ("execution_cost_credits", "cost_credits", "credits_used", "credits")
    for p in payloads:
        stack = [p]
        while stack:
            cur = stack.pop()
            if isinstance(cur, dict):
                for k in keys:
                    v = cur.get(k)
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        return float(v)
                stack.extend(cur.values())
    return None


def dune_state_verdict(state: str | None) -> str:
    if state == "QUERY_STATE_COMPLETED":
        return PASS
    if state in ("QUERY_STATE_FAILED", "QUERY_STATE_CANCELLED", "QUERY_STATE_EXPIRED"):
        return FAIL
    return UNKNOWN


def budget_math(credits_per_query: float | None, backfill_credits: float = 0.0) -> dict[str, Any]:
    if credits_per_query is None:
        return {"status": UNKNOWN, "detail": "credit cost per query not reported"}
    monthly = credits_per_query * NIGHTLY_QUERY_COUNT * 30 + backfill_credits
    return {
        "status": PASS if monthly <= FREE_TIER_MONTHLY_CREDITS else FAIL,
        "credits_per_query": credits_per_query,
        "queries_per_night": NIGHTLY_QUERY_COUNT,
        "projected_monthly": monthly,
        "ceiling": FREE_TIER_MONTHLY_CREDITS,
        "detail": f"{credits_per_query} x {NIGHTLY_QUERY_COUNT} x 30 = {monthly} vs {FREE_TIER_MONTHLY_CREDITS}",
        "note": "Solana-scale query cost may exceed the trivial query's; see solana_scale item",
    }


def overall(items: list[ProbeItem]) -> str:
    statuses = {i.status for i in items}
    if FAIL in statuses:
        return FAIL
    if UNKNOWN in statuses:
        return UNKNOWN
    return PASS


def redact(text: str, secret: str | None) -> str:
    return text.replace(secret, "[REDACTED]") if secret else text


def safe_serialize(result: dict[str, Any], secret: str | None) -> str:
    text = json.dumps(result, indent=2, sort_keys=True, default=str)
    if secret and secret in text:
        raise RuntimeError("refusing to write result: secret value found in output")
    return text


# --------------------------------------------------------------------------
# Network probes
# --------------------------------------------------------------------------

def _get_json(client: httpx.Client, url: str, **kw: Any) -> Any:
    r = client.get(url, **kw)
    r.raise_for_status()
    return r.json()


def probe_growthepie(client: httpx.Client) -> list[ProbeItem]:
    items: list[ProbeItem] = []
    master, host = None, None
    errors = []
    for h in GROWTHEPIE_HOSTS:
        try:
            master, host = _get_json(client, f"{h}/v1/master.json"), h
            break
        except Exception as exc:  # noqa: BLE001 - record and try next host
            errors.append(f"{h}: {type(exc).__name__}: {exc}")
    if master is None:
        return [ProbeItem("growthepie_master", FAIL, "; ".join(errors))]
    try:
        parsed = parse_growthepie_master(master)
    except ValueError as exc:
        return [ProbeItem("growthepie_master", FAIL, str(exc), {"host": host})]
    st, detail = growthepie_master_verdict(parsed)
    items.append(ProbeItem("growthepie_master", st, detail, {"host": host, **parsed}))

    targets = [t for t in (*GROWTHEPIE_TARGETS, *parsed["robinhood_keys"]) if t in parsed["chain_keys"]]
    try:
        rows = _get_json(client, f"{host}/v1/fundamentals_full.json", timeout=120.0)
        hist = parse_growthepie_history(rows, targets)
        st, detail = history_verdict(hist, targets)
        items.append(ProbeItem("growthepie_history_depth", st, detail, {"history": hist}))
    except Exception as exc:  # noqa: BLE001
        items.append(ProbeItem("growthepie_history_depth", UNKNOWN, f"{type(exc).__name__}: {exc}"))
    return items


def probe_l2beat(client: httpx.Client) -> list[ProbeItem]:
    items: list[ProbeItem] = []
    base_found = None
    tried = []
    for base in L2BEAT_CANDIDATES:
        try:
            parse_l2beat_activity(_get_json(client, base))
            base_found = base
            break
        except Exception as exc:  # noqa: BLE001
            tried.append(f"{base}: {type(exc).__name__}: {exc}")
    if base_found is None:
        return [ProbeItem("l2beat_endpoint", FAIL,
                          "no candidate endpoint returned activity data; locate the documented one "
                          "at https://docs.l2beat.com (plan E5: cross-check degrades to growthepie-only)",
                          {"tried": tried})]
    items.append(ProbeItem("l2beat_endpoint", PASS, f"keyless activity endpoint: {base_found}", {"url": base_found}))
    for proj in L2BEAT_PROJECTS:
        url = f"{base_found}/{proj}"
        try:
            info = parse_l2beat_activity(_get_json(client, url))
            items.append(ProbeItem(f"l2beat_activity_{proj}", PASS, f"{info['points']} points {info['first']}..{info['last']}", {"url": url, **info}))
        except Exception as exc:  # noqa: BLE001
            items.append(ProbeItem(f"l2beat_activity_{proj}", FAIL if proj != "robinhood" else UNKNOWN,
                                   f"{type(exc).__name__}: {exc}", {"url": url}))
    return items


class DuneRunner:
    def __init__(self, client: httpx.Client, key: str, max_credits: float,
                 sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic):
        self.client, self._key, self.max_credits = client, key, max_credits
        self.sleep, self.clock = sleep, clock
        self.spent = 0.0
        self.executions = 0

    @property
    def _headers(self) -> dict[str, str]:
        return {"X-Dune-API-Key": self._key}

    def run_sql(self, item_id: str, sql: str) -> ProbeItem:
        if self.spent >= self.max_credits:
            return ProbeItem(item_id, UNKNOWN, f"skipped: credit cap {self.max_credits} reached ({self.spent} spent)")
        t0 = self.clock()
        try:
            r = self.client.post(f"{DUNE_BASE}/sql/execute", headers=self._headers, json={"sql": sql})
            if r.status_code >= 400:
                return ProbeItem(item_id, FAIL, f"execute HTTP {r.status_code}: {redact(r.text[:300], self._key)}")
            self.executions += 1
            exec_id = r.json().get("execution_id")
            status: dict[str, Any] = {}
            state = None
            while self.clock() - t0 < DUNE_POLL_CEILING_S:
                status = _get_json(self.client, f"{DUNE_BASE}/execution/{exec_id}/status", headers=self._headers)
                state = status.get("state")
                if state not in ("QUERY_STATE_PENDING", "QUERY_STATE_EXECUTING"):
                    break
                self.sleep(3.0)
            elapsed = round(self.clock() - t0, 1)
            results: dict[str, Any] = {}
            if state == "QUERY_STATE_COMPLETED":
                results = _get_json(self.client, f"{DUNE_BASE}/execution/{exec_id}/results", headers=self._headers)
            credits = extract_dune_credits(status, results)
            if credits is not None:
                self.spent += credits
            rows = (results.get("result") or {}).get("rows") or []
            st = dune_state_verdict(state)
            if st == UNKNOWN and state in ("QUERY_STATE_PENDING", "QUERY_STATE_EXECUTING"):
                st, why = FAIL, f"did not finish within {DUNE_POLL_CEILING_S}s ceiling"
            else:
                why = f"state={state}"
            err = status.get("error")
            return ProbeItem(item_id, st, f"{why}, {elapsed}s, credits={credits}", {
                "state": state, "elapsed_s": elapsed, "credits": credits,
                "row_count": len(rows), "sample_rows": rows[:3],
                "error": redact(json.dumps(err), self._key) if err else None,
            })
        except Exception as exc:  # noqa: BLE001
            return ProbeItem(item_id, FAIL, redact(f"{type(exc).__name__}: {exc}", self._key))

    def usage(self) -> ProbeItem:
        try:
            r = self.client.get(f"{DUNE_BASE}/usage", headers=self._headers)
            if r.status_code >= 400:
                return ProbeItem("dune_usage", UNKNOWN, f"usage endpoint HTTP {r.status_code}; check credits in the Dune UI")
            return ProbeItem("dune_usage", PASS, "usage endpoint readable", {"usage": r.json()})
        except Exception as exc:  # noqa: BLE001
            return ProbeItem("dune_usage", UNKNOWN, redact(f"{type(exc).__name__}: {exc}", self._key))


def probe_dune(client: httpx.Client, key: str | None, max_credits: float, solana_scale: bool,
               runner_factory: Callable[..., DuneRunner] = DuneRunner) -> list[ProbeItem]:
    if not key:
        return [ProbeItem("dune_execute", UNKNOWN, "DUNE_API_KEY not set in this shell; Dune probes skipped")]
    runner = runner_factory(client, key, max_credits)
    items = [runner.usage(), runner.run_sql("dune_execute", TRIVIAL_SQL)]
    items.append(ProbeItem("dune_budget_math", **_budget_item(items[1].data.get("credits"))))
    if solana_scale:
        items.append(runner.run_sql("dune_solana_scale_35d", SOLANA_SCALE_SQL))
    for chain, table in DUNE_COVERAGE_TABLES.items():
        sql = f"SELECT max(block_time) AS latest FROM {table} WHERE block_time >= now() - interval '1' hour"
        items.append(runner.run_sql(f"dune_coverage_{chain}", sql))
    items.append(ProbeItem("dune_credits_spent", PASS if runner.spent <= max_credits else FAIL,
                           f"{runner.spent} credits reported over {runner.executions} executions",
                           {"spent": runner.spent, "executions": runner.executions}))
    return items


def _budget_item(credits: float | None) -> dict[str, Any]:
    b = budget_math(credits)
    return {"status": b["status"], "detail": b["detail"], "data": b}


def run(args: argparse.Namespace, client: httpx.Client | None = None) -> dict[str, Any]:
    key = os.environ.get("DUNE_API_KEY") or None
    own = client is None
    client = client or httpx.Client(timeout=30.0, follow_redirects=True)
    items: list[ProbeItem] = []
    try:
        for name, fn in (("growthepie", lambda: probe_growthepie(client)),
                         ("l2beat", lambda: probe_l2beat(client)),
                         ("dune", lambda: probe_dune(client, key, args.max_credits, not args.skip_solana_scale))):
            try:
                items.extend(fn())
            except Exception as exc:  # noqa: BLE001 - probes are independent
                items.append(ProbeItem(f"{name}_crashed", FAIL, redact(f"{type(exc).__name__}: {exc}", key)))
    finally:
        if own:
            client.close()
    return {
        "probe": "chain-growth RFC-1",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "dune_key_present": key is not None,
        "overall": overall(items),
        "items": [asdict(i) for i in items],
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--max-credits", type=float, default=50.0)
    p.add_argument("--skip-solana-scale", action="store_true")
    args = p.parse_args(argv)
    result = run(args)
    key = os.environ.get("DUNE_API_KEY") or None
    text = safe_serialize(result, key)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text + "\n", encoding="utf-8")
    for i in result["items"]:
        print(f"{i['status']:<8} {i['id']:<32} {redact(i['detail'], key)}")
    print(f"\nOVERALL: {result['overall']}\nResult JSON (no secrets): {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
