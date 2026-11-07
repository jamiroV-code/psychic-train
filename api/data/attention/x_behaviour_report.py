"""S-B3R (collector-identity-pool finish plan, B3 (c)): offline benefit/removal analyzer for the five X behaviour
measures.

Reads ONLY the durable daily facts (`daily_facts.read_events`), never the pool state, so a later day's reset cannot
pass for an earlier day's truth. Each UTC event day is put in one arm by its switch provenance:
- `baseline`: every measure off for the whole day;
- `<measure>`: exactly that measure on, the others off, for the whole day;
- `combined` (two or more on), `changed` (a measure flipped during the day) and `no_provenance` (no facts) are
  counted but never compared. Non-measure switches do not affect the arm.

Per-day metrics (source `xsearch_web`): completed units, accounts used and units per account, spent reads (unit reads
plus mixed-call charges), challenges, lock/pause/quarantine events, missing coin-days (eligible symbols in the day's
universe snapshot with no unit completed that day; unknown without a snapshot) and shrink events (units whose result
count started or extended a shrink run, replayed with `x_behaviour.record_result` over the facts in the range).

Decision per measure: `inconclusive` below `MIN_DAYS` comparable days in either arm. Otherwise `keep` when the mean
harm per day (challenges + lock/pause events) is strictly lower than the baseline's and missing coin-days are not
higher (when both arms have universe data); else `remove` (a measure that costs reads without reducing harm is
removed). Quiet hours and warm-up have no primary evidence (REF-X §4.3); this report is the evidence path.

CLI: `python -m api.data.attention.x_behaviour_report --from YYYY-MM-DD --to YYYY-MM-DD`. Pure file reads; no network.
"""
from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable, Mapping
from datetime import date, timedelta

from api.data.attention import daily_facts, x_behaviour

MEASURES = ("x_quiet_hours_enabled", "x_mixed_traffic_enabled", "x_variation_enabled",
            "x_adaptive_cooldown_enabled", "x_warmup_enabled")
MIN_DAYS = 7
MAX_RANGE_DAYS = 366
SOURCE = "xsearch_web"
QUERY_CLASS = "coin_day"
HARM_STATES = frozenset({"pause", "lock", "quarantine"})
METRICS = ("units", "units_per_account", "reads", "challenges", "locked_paused", "missing_coin_days",
           "shrink_events")


def classify(events: Iterable[Mapping[str, object]]) -> str:
    """The day's arm from its switch provenance events."""
    states = {tuple(bool((e.get("switches") or {}).get(m)) for m in MEASURES)
              for e in events if e.get("kind") == "switch_provenance"}
    if not states:
        return "no_provenance"
    if len(states) > 1:
        return "changed"
    on = [m for m, v in zip(MEASURES, states.pop()) if v]
    if not on:
        return "baseline"
    return on[0] if len(on) == 1 else "combined"


def _ours(ev: Mapping[str, object]) -> bool:
    return ev.get("source") == SOURCE


def day_metrics(events: list[Mapping[str, object]]) -> dict:
    """Metrics of one day's events (shrink events are filled in by `analyze`, which replays across days)."""
    units = [e for e in events if e.get("kind") == "unit_completed" and _ours(e)]
    accounts = {e.get("account") for e in units}
    reads = sum(int(e.get("reads") or 0) for e in units) + sum(
        int(e.get("reads") or 0) for e in events if e.get("kind") == "mixed_call" and _ours(e))
    snapshot = next((e for e in events if e.get("kind") == "universe_snapshot" and _ours(e)), None)
    missing = None
    if snapshot is not None:
        done = {e.get("coin") for e in units}
        missing = sum(1 for s in snapshot.get("eligible_symbols") or [] if s not in done)
    return {"arm": classify(events), "units": len(units), "accounts": len(accounts),
            "units_per_account": round(len(units) / len(accounts), 4) if accounts else 0.0, "reads": reads,
            "challenges": sum(1 for e in events if e.get("kind") == "challenge" and _ours(e)),
            "locked_paused": sum(1 for e in events if e.get("kind") == "account_state" and _ours(e)
                                 and e.get("state") in HARM_STATES),
            "missing_coin_days": missing, "shrink_events": 0}


def _mean(values: list) -> float | None:
    known = [v for v in values if v is not None]
    return round(sum(known) / len(known), 4) if known else None


def _decide(base: list[dict], arm: list[dict]) -> str:
    if len(base) < MIN_DAYS or len(arm) < MIN_DAYS:
        return "inconclusive"
    harm_base = _mean([d["challenges"] + d["locked_paused"] for d in base])
    harm_arm = _mean([d["challenges"] + d["locked_paused"] for d in arm])
    miss_base = _mean([d["missing_coin_days"] for d in base])
    miss_arm = _mean([d["missing_coin_days"] for d in arm])
    coverage_ok = miss_base is None or miss_arm is None or miss_arm <= miss_base
    return "keep" if harm_arm < harm_base and coverage_ok else "remove"


def analyze(start: date, end: date) -> dict:
    """Deterministic report over the UTC days `start..end` inclusive."""
    if end < start:
        raise ValueError("--to is before --from")
    span = (end - start).days + 1
    if span > MAX_RANGE_DAYS:
        raise ValueError(f"range longer than {MAX_RANGE_DAYS} days")
    days: list[dict] = []
    history: dict[str, tuple[list[dict], int]] = {}
    for i in range(span):
        day = start + timedelta(days=i)
        events = daily_facts.read_events(day)
        metrics = day_metrics(events) | {"day": day.isoformat()}
        for ev in events:
            if ev.get("kind") != "unit_completed" or not _ours(ev):
                continue
            hist, run = history.get(str(ev.get("account")), ([], 0))
            new_hist, new_run = x_behaviour.record_result(hist, run, day=day, count=int(ev.get("raw_results") or 0),
                                                          query_class=QUERY_CLASS, canary=False)
            if new_run > run:
                metrics["shrink_events"] += 1
            history[str(ev.get("account"))] = (new_hist, new_run)
        days.append(metrics)
    arms: dict[str, int] = {}
    for d in days:
        arms[d["arm"]] = arms.get(d["arm"], 0) + 1
    base = [d for d in days if d["arm"] == "baseline"]
    rows = []
    for m in MEASURES:
        arm = [d for d in days if d["arm"] == m]
        rows.append({"measure": m, "decision": _decide(base, arm), "baseline_days": len(base),
                     "measure_days": len(arm),
                     "metrics": {k: {"baseline": _mean([d[k] for d in base]), "measure": _mean([d[k] for d in arm])}
                                 for k in METRICS}})
    return {"from": start.isoformat(), "to": end.isoformat(), "min_days": MIN_DAYS, "arms": arms, "days": days,
            "rows": rows}


def render(report: dict) -> str:
    lines = [f"X behaviour measures {report['from']}..{report['to']} (inconclusive below {report['min_days']} "
             f"comparable days per arm)",
             "arms: " + ", ".join(f"{k}={v}" for k, v in sorted(report["arms"].items()))]
    for row in report["rows"]:
        lines.append(f"{row['measure']}: {row['decision']} baseline_days={row['baseline_days']} "
                     f"measure_days={row['measure_days']}")
        for k, v in row["metrics"].items():
            lines.append(f"  {k}: baseline={v['baseline']} measure={v['measure']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="x_behaviour_report", description=__doc__.splitlines()[0])
    parser.add_argument("--from", dest="start", required=True, type=date.fromisoformat)
    parser.add_argument("--to", dest="end", required=True, type=date.fromisoformat)
    args = parser.parse_args(argv)
    try:
        report = analyze(args.start, args.end)
    except ValueError as exc:
        print(f"x_behaviour_report: {exc}", file=sys.stderr)
        return 2
    print(render(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
