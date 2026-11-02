"""T223 O0: the pure onboarding ledger state machine (AC1-AC5)."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from api.data.attention import coin_ledger as cl
from api.data.attention.onboarding_settings import Settings

S = Settings()
D0 = date(2026, 11, 1)


def snap(day: int, placed: dict[str, int] | None = None, n: int = 120) -> dict:
    """120 filler coins at their ranks; `placed` moves the named ids to the given rank (None = absent)."""
    placed = placed or {}
    order = [f"fill-{i}" for i in range(1, n + 1)]
    for cid, rank in placed.items():
        if rank is not None:
            order.insert(rank - 1, cid)
    order = order[:max(n, 0)]
    return {"date": (D0 + timedelta(days=day)).isoformat(),
            "coins": [{"id": cid, "symbol": cid.upper().replace("-", "_"), "rank": i + 1}
                      for i, cid in enumerate(order)]}


def run(days: list[dict], ledger=None, settings=S) -> dict:
    led = ledger or cl.empty()
    for s in days:
        led = cl.advance(led, s, settings).ledger
    return led


def test_new_entrant_is_watching_with_count_one():
    led = run([snap(0, {"newc": 50})])
    e = led["coins"]["newc"]
    assert (e["state"], e["consecutive_top100"], e["class"], e["class_source"]) == ("watching", 1, "unknown", "auto")
    assert led["last_advanced_date"] == "2026-11-01"


def test_rank_101_to_120_does_not_enter():
    assert "edge" not in run([snap(0, {"edge": 110})])["coins"]


def test_thirteen_days_then_drop_stays_watching_and_resets():
    days = [snap(d, {"newc": 50}) for d in range(13)] + [snap(13, {"newc": 110})]
    e = run(days)["coins"]["newc"]
    assert (e["state"], e["consecutive_top100"]) == ("watching", 0)


def test_fourteen_days_joins():
    led = run([snap(d, {"newc": 50}) for d in range(13)])
    assert led["coins"]["newc"]["state"] == "watching"
    led = run([snap(13, {"newc": 50})], led)
    assert led["coins"]["newc"]["state"] == "member"


def test_drop_and_return_restarts_the_count():
    days = [snap(d, {"newc": 50}) for d in range(10)] + [snap(10, {"newc": 105})] + \
           [snap(d, {"newc": 50}) for d in range(11, 24)]
    e = run(days)["coins"]["newc"]
    assert (e["state"], e["consecutive_top100"]) == ("watching", 13)
    assert run([snap(24, {"newc": 50})], run(days))["coins"]["newc"]["state"] == "member"


def test_missing_snapshot_day_is_neutral():
    days = [snap(d, {"newc": 50}) for d in range(14) if d != 5] + [snap(14, {"newc": 50})]
    assert run(days)["coins"]["newc"]["state"] == "member"


def test_same_date_rerun_is_a_noop_and_first_run_wins():
    led = run([snap(0, {"newc": 50})])
    res = cl.advance(led, snap(0, {"newc": 50, "other": 10}), S)
    assert res.status == "same-date" and res.ledger is led and "other" not in res.ledger["coins"]
    assert cl.advance(led, snap(-1, {"newc": 50}), S).status == "same-date"


@pytest.mark.parametrize("bad", [snap(0, n=119), {"date": "2026-11-01", "coins": "x"}, {"coins": []}, None])
def test_short_or_broken_snapshot_is_unavailable(bad):
    led = run([snap(0, {"newc": 50})])
    res = cl.advance(led, bad, S)
    assert res.status == "unavailable" and res.ledger is led


def test_a_few_unusable_ranks_are_tolerated_but_many_or_a_cut_end_are_not():
    def gapped(*ranks):
        s = snap(1)
        s["coins"] = [c for c in s["coins"] if c["rank"] not in ranks]
        return s
    ok = cl.advance(cl.empty(), gapped(60, 102), S)
    assert ok.status == "advanced" and "id-60" not in ok.ledger["coins"] and len(ok.ledger["coins"]) == 99
    assert cl.advance(cl.empty(), gapped(1, 2, 3, 4, 5, 6), S).status == "unavailable"
    assert cl.advance(cl.empty(), gapped(120), S).status == "unavailable"


def member_ledger() -> dict:
    return run([snap(d, {"m": 40}) for d in range(14)])


def test_member_at_rank_101_to_120_stays_member():
    led = run([snap(d, {"m": 115}) for d in range(14, 40)], member_ledger())
    assert led["coins"]["m"]["state"] == "member"


def test_exit_on_day_seven_not_six():
    led = run([snap(d, {"m": None}) for d in range(14, 20)], member_ledger())
    assert led["coins"]["m"]["state"] == "member" and led["coins"]["m"]["consecutive_outside120"] == 6
    led = run([snap(20, {"m": 130})], led)
    assert led["coins"]["m"]["state"] == "inactive"


def test_return_on_day_five_cancels_the_exit():
    led = run([snap(d, {"m": None}) for d in range(14, 18)] + [snap(18, {"m": 119})], member_ledger())
    assert led["coins"]["m"]["consecutive_outside120"] == 0
    led = run([snap(d, {"m": None}) for d in range(19, 25)], led)
    assert led["coins"]["m"]["state"] == "member"


def test_watching_coin_is_removed_after_exit_days_outside_the_band():
    led = run([snap(0, {"w": 50})] + [snap(d, {"w": None}) for d in range(1, 7)])
    assert "w" in led["coins"]
    res = cl.advance(led, snap(7, {"w": None}), S)
    assert "w" not in res.ledger["coins"] and ("removed", "w") in res.events


def test_inactive_keeps_class_and_returns_to_watching():
    led = member_ledger()
    led["coins"]["m"].update({"class": "normal", "class_source": "auto"})
    led = run([snap(d, {"m": None}) for d in range(14, 21)], led)
    assert led["coins"]["m"]["state"] == "inactive"
    led = run([snap(30, {"m": 90})], led)
    e = led["coins"]["m"]
    assert (e["state"], e["consecutive_top100"], e["class"]) == ("watching", 1, "normal")


def test_seed_takes_rank_1_to_100_only_as_normal_owner_members():
    res = cl.seed(snap(0, {"edge": 110}), S)
    coins = res.ledger["coins"]
    assert res.status == "seeded" and len(coins) == 100 and "edge" not in coins
    assert {(e["state"], e["class"], e["class_source"], e["seeded"]) for e in coins.values()} == {
        ("member", "normal", "owner", True)}
    assert res.ledger["seeded_at"] == res.ledger["last_advanced_date"] == "2026-11-01"
    assert cl.seed(snap(0, n=50), S).status == "unavailable"


def test_settings_drive_the_numbers():
    fast = Settings(probation_days=2, exit_days=1)
    led = run([snap(0, {"x": 5}), snap(1, {"x": 5})], settings=fast)
    assert led["coins"]["x"]["state"] == "member"
    assert run([snap(2, {"x": None})], led, fast)["coins"]["x"]["state"] == "inactive"


@pytest.mark.parametrize("kind", ["duplicate-id", "duplicate-rank", "date", "symbol", "id"])
def test_untrustworthy_snapshot_cannot_seed_or_advance(kind):
    snapshot = snap(1)
    if kind == "duplicate-id":
        snapshot["coins"][1]["id"] = snapshot["coins"][0]["id"]
    elif kind == "duplicate-rank":
        snapshot["coins"].append(dict(snapshot["coins"][0]))
    elif kind == "date":
        snapshot["date"] = "2026-02-30"
    elif kind == "symbol":
        snapshot["coins"][0]["symbol"] = "BAD-SYMBOL"
    else:
        snapshot["coins"][0]["id"] = "../bad"
    ledger = member_ledger()
    assert cl.seed(snapshot, S).status == "unavailable"
    result = cl.advance(ledger, snapshot, S)
    assert result.status == "unavailable" and result.ledger is ledger
