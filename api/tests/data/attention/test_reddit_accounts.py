"""S-RAcct-A: the Reddit account pool state (selection, caps, rest, ready, day guard). File-only, no network."""
from __future__ import annotations

import json
import threading
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from api.analytics.attention import sources
from api.data import cache
from api.data.attention import reddit_accounts as ra

T0 = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _isolated(attention_cache):
    return attention_cache


class Clock:
    def __init__(self, now: datetime = T0):
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kw) -> None:
        self.now += timedelta(**kw)


def state_file():
    return cache.CACHE_ROOT / "attention" / "_pc_state" / "reddit_accounts.json"


def ready_file():
    return cache.CACHE_ROOT / "attention" / "_pc_state" / "reddit_account_ready.json"


def mark_ready(*labels, day: date = T0.date() - timedelta(days=1)) -> None:
    ready_file().parent.mkdir(parents=True, exist_ok=True)
    ready_file().write_text(json.dumps({"ready": {x: day.isoformat() for x in labels}}))


def pool(labels=("ra_one", "ra_two"), clock=None, cap=200, rest_days=0, **kw) -> ra.RedditAccounts:
    kw.setdefault("admission", lambda site, label: "proxy" if kw.get("proxy_required") else "direct")
    return ra.RedditAccounts(list(labels), clock=clock or Clock(), cap=cap, rest_days=rest_days, **kw)


def saved() -> dict:
    return json.loads(state_file().read_text())


# --- state file: exact keys, migration, rollback ---

def test_fresh_state_is_exact_key_and_matches_status_contract():
    mark_ready("ra_one", "ra_two")
    p = pool()
    p.begin_pass()
    doc = saved()
    assert set(doc) == {"accounts"}
    entry = doc["accounts"]["ra_one"]
    assert set(entry) == ra.ACCOUNT_KEYS
    for key in ("state", "reason", "reads_day", "reads_used", "rest_until", "last_used", "session_state",
                "session_checked_at", "session_day", "proxy_state", *ra.B2_ACCOUNT_KEYS):
        assert key in entry
    assert len(ra.B2_ACCOUNT_KEYS) == 7
    assert entry["state"] == "active" and entry["reads_used"] == 0 and entry["proxy_state"] == "direct"


def test_old_state_file_migrates_by_setdefault():
    state_file().parent.mkdir(parents=True, exist_ok=True)
    old = {"state": "active", "reason": None, "reads_day": None, "reads_used": 3, "rest_until": None,
           "last_used": None}
    state_file().write_text(json.dumps({"accounts": {"ra_one": old}}))
    mark_ready("ra_one")
    p = pool(labels=("ra_one",))
    p.begin_pass()
    entry = saved()["accounts"]["ra_one"]
    assert set(entry) == ra.ACCOUNT_KEYS and entry["reads_used"] == 3 and entry["session_day"] is None


def test_unknown_key_or_bad_value_is_refused_not_guessed():
    state_file().parent.mkdir(parents=True, exist_ok=True)
    entry = dict.fromkeys(ra.ACCOUNT_KEYS) | {"state": "active", "reads_used": 0, "extra": 1}
    state_file().write_text(json.dumps({"accounts": {"ra_one": entry}}))
    with pytest.raises(ra.RedditAccountStateError):
        pool(labels=("ra_one",)).begin_pass()
    state_file().write_text(json.dumps({"accounts": {"ra_one": {"state": "flying"}}}))
    with pytest.raises(ra.RedditAccountStateError):
        pool(labels=("ra_one",)).begin_pass()
    state_file().write_text("{not json")
    with pytest.raises(ra.RedditAccountStateError):
        pool(labels=("ra_one",)).begin_pass()


def test_unconfigured_label_is_kept_untouched_and_never_selected():
    mark_ready("ra_one", "ra_two")
    pool().begin_pass()
    p = pool(labels=("ra_one",))
    p.begin_pass()
    assert "ra_two" in saved()["accounts"]
    assert p.select() == "ra_one" and p.select(exclude=("ra_one",)) is None


def test_rollback_leaves_no_other_file_and_reader_tolerates_absence():
    cfg = SimpleNamespace(reddit_browser_accounts=({"label": "ra_one", "profile": "p1"},),
                          reddit_browser_account_daily_cap=200)
    rows = sources.reddit_accounts(cfg, T0)
    assert rows[0].state == "unknown"
    mark_ready("ra_one")
    pool(labels=("ra_one",)).begin_pass()
    names = sorted(x.name for x in state_file().parent.iterdir() if not x.name.endswith(".lock"))
    assert names == ["reddit_account_ready.json", "reddit_accounts.json"]


def test_status_reader_reads_what_the_pool_writes():
    mark_ready("ra_one")
    p = pool(labels=("ra_one",))
    p.charge("ra_one", 5)
    cfg = SimpleNamespace(reddit_browser_accounts=({"label": "ra_one", "profile": "p1"},),
                          reddit_browser_account_daily_cap=200)
    row = sources.reddit_accounts(cfg, T0)[0]
    assert (row.state, row.reads_today, row.ready, row.proxy_state) == ("active", 5, True, "direct")


# --- selection gates ---

def test_least_recently_used_with_registration_tie_break():
    mark_ready("ra_one", "ra_two")
    clock = Clock()
    p = pool(clock=clock)
    assert p.select() == "ra_one"
    p.mark_used("ra_one")
    clock.advance(minutes=1)
    assert p.select() == "ra_two"
    p.mark_used("ra_two")
    assert p.select() == "ra_one"


def test_cap_skip_with_reason_and_reset_next_day():
    mark_ready("ra_one", "ra_two")
    clock = Clock()
    p = pool(clock=clock, cap=10)
    p.charge("ra_one", 10)
    assert p.account_state("ra_one") == ("locked", "cap")
    assert p.select() == "ra_two"
    assert saved()["accounts"]["ra_one"]["state"] == "locked"
    clock.advance(days=1)
    assert p.account_state("ra_one") == ("active", None)


def test_ready_gate_joins_the_next_utc_day_only():
    clock = Clock()
    p = pool(labels=("ra_one",), clock=clock)
    assert p.account_state("ra_one") == ("resting", "resting")
    ra.write_ready("ra_one", clock(), labels=("ra_one",))
    assert json.loads(ready_file().read_text()) == {"ready": {"ra_one": T0.date().isoformat()}}
    assert p.account_state("ra_one") == ("resting", "resting")
    clock.advance(days=1)
    assert p.account_state("ra_one") == ("active", None)


def test_write_ready_refuses_unconfigured_label():
    with pytest.raises(ValueError):
        ra.write_ready("ra_bad", T0, labels=("ra_one",))
    assert not ready_file().exists()


def test_rest_gate_holds_newly_registered_account_for_rest_days():
    mark_ready("ra_one")
    clock = Clock()
    p = pool(labels=("ra_one",), clock=clock, rest_days=7)
    p.begin_pass()
    assert p.account_state("ra_one") == ("resting", "resting")
    assert saved()["accounts"]["ra_one"]["rest_until"] == (T0 + timedelta(days=7)).isoformat()
    clock.advance(days=7)
    assert p.account_state("ra_one") == ("active", None)


def test_route_must_be_admitted_when_proxy_required():
    mark_ready("ra_one")
    p = pool(labels=("ra_one",), proxy_required=True)
    assert p.account_state("ra_one") == ("locked", "proxy_not_admitted")
    p.set_proxy("ra_one", proxy_health="quarantined")
    assert p.account_state("ra_one") == ("locked", "proxy_quarantined")
    p.set_proxy("ra_one", proxy_health="healthy")
    assert p.account_state("ra_one") == ("active", None)
    assert saved()["accounts"]["ra_one"]["proxy_state"] == "healthy"


def test_no_ready_account_is_missing_not_zero():
    p = pool()
    result = ra.run_poll(p, lambda label: pytest.fail("nothing may be read"))
    assert result.value is None and result.reason == "no_ready_account" and result.label is None
    assert result.attempts == ()


# --- polls: one account, never split, failover once, counted once ---

def test_poll_read_by_one_account_start_to_finish():
    mark_ready("ra_one", "ra_two")
    p = pool()
    calls = []

    def read(label):
        calls.append(label)
        return {"posts": 3}, 4

    result = ra.run_poll(p, read)
    assert calls == ["ra_one"] and result.label == "ra_one" and result.value == {"posts": 3}
    assert result.reason is None and p.reads_today("ra_one") == 4 and p.reads_today("ra_two") == 0


def test_lost_account_poll_retried_once_on_another_and_counted_once():
    mark_ready("ra_one", "ra_two")
    p = pool()
    calls = []

    def read(label):
        calls.append(label)
        if label == "ra_one":
            raise ra.AccountLost("reddit_login_required", navigations=2)
        return {"posts": 3}, 5

    result = ra.run_poll(p, read)
    assert calls == ["ra_one", "ra_two"]
    assert result.value == {"posts": 3} and result.label == "ra_two" and result.attempts == ("ra_one", "ra_two")
    assert p.reads_today("ra_one") == 2 and p.reads_today("ra_two") == 5  # failed attempt charged, data once
    assert p.account_state("ra_one") == ("paused", "reddit_login_required")


def test_second_loss_stops_the_poll_without_a_third_attempt():
    mark_ready("ra_one", "ra_two", "ra_three")
    p = pool(labels=("ra_one", "ra_two", "ra_three"))
    calls = []

    def read(label):
        calls.append(label)
        raise ra.AccountLost("challenge", navigations=1)

    result = ra.run_poll(p, read)
    assert calls == ["ra_one", "ra_two"] and result.value is None and result.reason == "challenge"
    assert p.account_state("ra_three") == ("active", None)


def test_loss_with_no_other_account_is_no_ready_account():
    mark_ready("ra_one")
    p = pool(labels=("ra_one",))
    result = ra.run_poll(p, lambda label: (_ for _ in ()).throw(ra.AccountLost("suspended")))
    assert result.value is None and result.reason == "no_ready_account" and result.attempts == ("ra_one",)
    assert p.account_state("ra_one") == ("paused", "suspended")


def test_unknown_loss_reason_is_refused():
    with pytest.raises(ValueError):
        ra.AccountLost("made_up")


def test_pause_survives_restart_and_logged_in_session_reactivates():
    mark_ready("ra_one")
    clock = Clock()
    pool(labels=("ra_one",), clock=clock).pause("ra_one", "reddit_login_required")
    p = pool(labels=("ra_one",), clock=clock)
    assert p.account_state("ra_one") == ("paused", "reddit_login_required")
    p.record_session("ra_one", "logged_in")
    assert p.account_state("ra_one") == ("active", None)
    entry = saved()["accounts"]["ra_one"]
    assert entry["session_state"] == "logged_in" and entry["session_checked_at"] == T0.isoformat()


def test_logged_out_session_pauses_and_suspended_is_not_reopened_by_login():
    mark_ready("ra_one")
    p = pool(labels=("ra_one",))
    p.record_session("ra_one", "logged_out")
    assert p.account_state("ra_one") == ("paused", "reddit_login_required")
    p.pause("ra_one", "suspended")
    p.record_session("ra_one", "logged_in")
    assert p.account_state("ra_one") == ("paused", "suspended")


# --- CK-2 day guard ---

def test_day_guard_claims_once_per_day_and_survives_restart():
    mark_ready("ra_one")
    day = T0.date().isoformat()
    assert pool(labels=("ra_one",)).try_claim("reddit", "ra_one", day) is True
    assert pool(labels=("ra_one",)).try_claim("reddit", "ra_one", day) is False
    assert pool(labels=("ra_one",)).try_claim("reddit", "ra_one", "2026-11-08") is True
    assert saved()["accounts"]["ra_one"]["session_day"] == "2026-11-08"


def test_day_guard_refuses_wrong_site_label_or_day():
    p = pool(labels=("ra_one",))
    for args in (("x", "ra_one", "2026-11-07"), ("reddit", "ra_bad", "2026-11-07"), ("reddit", "ra_one", "07/11")):
        with pytest.raises(ValueError):
            p.try_claim(*args)


def test_day_guard_is_atomic_across_concurrent_claimants():
    pool(labels=("ra_one",)).begin_pass()
    wins, barrier = [], threading.Barrier(6)

    def claim():
        barrier.wait()
        wins.append(pool(labels=("ra_one",)).try_claim("reddit", "ra_one", "2026-11-07"))

    threads = [threading.Thread(target=claim) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(wins) == [False] * 5 + [True]


# --- config and CLI ---

def test_from_config_reads_labels_cap_and_rest():
    cfg = SimpleNamespace(reddit_browser_accounts=({"label": "ra_one", "profile": "p1"},),
                          reddit_browser_account_daily_cap=50, reddit_browser_account_rest_days=3)
    p = ra.from_config(cfg, clock=Clock())
    assert p.labels == ["ra_one"] and p.cap == 50 and p.rest_days == 3


def test_cli_mark_ready_writes_codes_only(monkeypatch, capsys):
    cfg = SimpleNamespace(reddit_browser_accounts=({"label": "ra_one", "profile": "p1"},))
    monkeypatch.setattr(ra, "_load_config", lambda path: cfg)
    assert ra.main(["--mark-ready", "ra_one"]) == 0
    assert capsys.readouterr().out.strip() == "ready status=ok label=ra_one"
    assert "ra_one" in json.loads(ready_file().read_text())["ready"]
    assert ra.main(["--mark-ready", "nope"]) == 2
    assert capsys.readouterr().out.strip() == "ready status=refused"


def test_day_guard_does_not_reopen_on_clock_rollback():
    p = pool(labels=("ra_one",))
    assert p.try_claim("reddit", "ra_one", "2026-11-08")
    assert not p.try_claim("reddit", "ra_one", "2026-11-07")
    assert not p.try_claim("reddit", "ra_one", "2026-11-08")


def test_default_admission_is_closed_even_for_healthy_account():
    mark_ready("ra_one")
    p = ra.RedditAccounts(["ra_one"], clock=Clock())
    assert p.select() is None
    assert p.account_state("ra_one") == ("locked", "proxy_not_admitted")


@pytest.mark.parametrize("required,paths,expected", [
    (False, (None, None, None), False),
    (True, (None, None, None), True),
    (False, ("list", None, None), True),
    (False, (None, "assignments", None), True),
    (False, (None, None, "policy"), True),
])
def test_config_never_silently_selects_direct(required, paths, expected):
    cfg = SimpleNamespace(reddit_browser_accounts=({"label": "ra_one", "profile": "p1"},),
                          reddit_browser_account_daily_cap=50, reddit_browser_account_rest_days=0,
                          x_proxy_required=required, x_proxy_list_path=paths[0],
                          x_proxy_assignments_path=paths[1], x_proxy_policy_path=paths[2])
    mark_ready("ra_one")
    p = ra.from_config(cfg, clock=Clock(), admission=lambda site, label: "direct")
    assert p.proxy_required is expected
    assert (p.select() is None) is expected
