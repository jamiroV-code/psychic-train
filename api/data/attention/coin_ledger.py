"""Per-coin onboarding ledger state machine (T223, D-31). Pure: no I/O, no wall clock.

Document: {"last_advanced_date", "seeded_at", "coins": {coin id: entry}}; entry keys are ENTRY_KEYS.
States: `watching` (probation), `member`, `inactive`. The day is always the snapshot's own date:
a snapshot dated on or before `last_advanced_date` changes nothing (a same-day rerun counts once), and a missing
snapshot day is neutral (there is simply no call). A snapshot without `exit_band_rank` contiguous ranks is
`unavailable` and changes nothing.

Rules (owner decisions O1, O2, O7): a coin first seen in the top 100 is `watching` with count 1; a top-100 day adds
1, a day outside the top 100 resets the count to 0; `probation_days` makes it a `member`. A `member` outside the
exit band (rank > `exit_band_rank`, or absent) for `exit_days` consecutive snapshots becomes `inactive`; a return
to the band cancels that count. A `watching` coin outside the band for `exit_days` snapshots is removed. An
`inactive` coin back in the top 100 is `watching` again with count 1 and keeps its class.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
import re
from datetime import date

from api.data.attention.onboarding_settings import SYMBOL_RE

ID_RE = re.compile(r"[a-z0-9][a-z0-9._-]{0,99}")


def valid_date(value) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False

TOP = 100
MAX_UNUSABLE = 5   # ranks the snapshot may lack because the coin's symbol or id was refused at write time
STATES = ("watching", "member", "inactive")
ENTRY_KEYS = ("symbol", "state", "first_seen", "last_in_top100", "last_in_top120", "consecutive_top100",
              "consecutive_outside120", "class", "class_evidence", "class_source", "seeded", "updated")


@dataclass
class Result:
    ledger: dict
    status: str                     # advanced | seeded | same-date | unavailable
    reason: str = ""
    events: list[tuple[str, str]] = field(default_factory=list)   # (event, coin id)


def empty() -> dict:
    return {"last_advanced_date": None, "seeded_at": None, "coins": {}}


def band_rows(snapshot, band: int) -> dict[str, dict] | None:
    """{coin id: row} when the snapshot reaches rank `band` and at most MAX_UNUSABLE ranks below it are missing, else None.

    The live markets answer can hold a coin whose symbol the snapshot refuses (non-ASCII, P-O0); that rank stays
    unused. A truncated snapshot (no row at rank `band`) or many gaps is still `unavailable`."""
    if not isinstance(snapshot, dict) or not valid_date(snapshot.get("date")):
        return None
    rows = snapshot.get("coins")
    if not isinstance(rows, list):
        return None
    by_rank: dict[int, dict] = {}
    ids = set()
    for r in rows:
        if not isinstance(r, dict):
            return None
        rank, cid, symbol = r.get("rank"), r.get("id"), r.get("symbol")
        if (type(rank) is not int or rank < 1 or rank in by_rank
                or not isinstance(cid, str) or not ID_RE.fullmatch(cid) or cid in ids
                or not isinstance(symbol, str) or not SYMBOL_RE.fullmatch(symbol)):
            return None
        by_rank[rank] = r
        ids.add(cid)
    missing = sum(1 for k in range(1, band + 1) if k not in by_rank)
    if band not in by_rank or missing > MAX_UNUSABLE:
        return None
    return {by_rank[k]["id"]: by_rank[k] for k in sorted(by_rank)}


def _entry(row: dict, day: str, *, state: str, count: int, seeded: bool = False, cls: str = "unknown",
           source: str = "auto") -> dict:
    return {"symbol": str(row.get("symbol", "")).upper(), "state": state, "first_seen": day, "last_in_top100": day,
            "last_in_top120": day, "consecutive_top100": count, "consecutive_outside120": 0, "class": cls,
            "class_evidence": {}, "class_source": source, "seeded": seeded, "updated": day}


def seed(snapshot, settings) -> Result:
    """Owner decision O7: every coin at rank 1..100 is a `member`, class `normal` (class_source `owner`)."""
    rows = band_rows(snapshot, settings.exit_band_rank)
    if rows is None:
        return Result(empty(), "unavailable", "snapshot without contiguous ranks")
    day = snapshot["date"]
    doc = {"last_advanced_date": day, "seeded_at": day, "coins": {}}
    for cid, r in rows.items():
        if r["rank"] <= TOP:
            doc["coins"][cid] = _entry(r, day, state="member", count=settings.probation_days, seeded=True,
                                       cls="normal", source="owner")
    return Result(doc, "seeded", "", [("seeded", cid) for cid in doc["coins"]])


def advance(ledger: dict, snapshot, settings) -> Result:
    rows = band_rows(snapshot, settings.exit_band_rank)
    if rows is None:
        return Result(ledger, "unavailable", "snapshot without contiguous ranks")
    day = snapshot["date"]
    last = ledger.get("last_advanced_date")
    if isinstance(last, str) and day <= last:
        return Result(ledger, "same-date", "snapshot already processed")
    doc = copy.deepcopy(ledger)
    coins: dict = doc.setdefault("coins", {})
    events: list[tuple[str, str]] = []
    band = settings.exit_band_rank
    for cid in list(coins):
        e = coins[cid]
        r = rows.get(cid)
        rank = r["rank"] if r else None
        in100, in_band = rank is not None and rank <= TOP, rank is not None and rank <= band
        if r:
            e["symbol"] = str(r.get("symbol", e["symbol"])).upper()
        if in100:
            e["last_in_top100"] = day
        if in_band:
            e["last_in_top120"] = day
        e["consecutive_outside120"] = 0 if in_band else e["consecutive_outside120"] + 1
        e["updated"] = day
        if e["state"] == "watching":
            e["consecutive_top100"] = e["consecutive_top100"] + 1 if in100 else 0
            if e["consecutive_outside120"] >= settings.exit_days:
                del coins[cid]
                events.append(("removed", cid))
            elif e["consecutive_top100"] >= settings.probation_days:
                e["state"] = "member"
                events.append(("joined", cid))
        elif e["state"] == "member":
            e["consecutive_top100"] = e["consecutive_top100"] + 1 if in100 else 0
            if e["consecutive_outside120"] >= settings.exit_days:
                e["state"] = "inactive"
                events.append(("inactive", cid))
        elif e["state"] == "inactive" and in100:
            e.update(state="watching", consecutive_top100=1, consecutive_outside120=0)
            events.append(("returned", cid))
    for cid, r in rows.items():
        if cid not in coins and r["rank"] <= TOP:
            coins[cid] = _entry(r, day, state="watching", count=1)
            events.append(("entered", cid))
            if settings.probation_days <= 1:
                coins[cid]["state"] = "member"
    doc["last_advanced_date"] = day
    return Result(doc, "advanced", "", events)
