"""S-Cookie-X: X session wiring (CX-1 triggers, CX-2 hand-off, CX-3 reactivation, harvest pool keys, the X day
guard and the X route provider over the B2 runtime). Fake library, fake session results and fake runtimes only:
no browser is launched and nothing is sent."""
from __future__ import annotations

import json
import types
from datetime import datetime, timedelta, timezone

import pytest

from api.data.attention import browser_relay as relay
from api.data.attention import browser_session as bs
from api.data.attention import daily_facts
from api.data.attention import twscrape_reader as tr
from api.data.attention import x_pool as xp
from api.tests.data.attention.test_twscrape_reader import (  # noqa: F401 - `lib` is a fixture
    GOOD_ENV, FakePool, accounts, cfg, lib, lookup, row)

T0 = datetime(2026, 10, 27, 10, 0, tzinfo=timezone.utc)
LABELS = ["acct1", "acct2"]
AUTH, CT0 = "a" * 40, "b" * 64
HARVEST_DEFAULTS = {"harvest_day": None, "harvest_state": "none", "harvest_reason": None}


@pytest.fixture(autouse=True)
def _isolated(attention_cache):
    return attention_cache


class Clock:
    def __init__(self, now=T0):
        self.now = now

    def __call__(self):
        return self.now


def state():
    return json.loads(xp.XPool(LABELS, clock=Clock()).path.read_text(encoding="utf-8"))


def result(state_, reason=None, cookies=(), label="acct1", mode="automatic"):
    return bs.SessionResult("x", label, state_, reason, mode, mode != "automatic", ("auth_token", "ct0"),
                            None, "ge_30d", tuple(cookies))


def jar(auth=AUTH, ct0=CT0, extra=()):
    return (("auth_token", auth, None), ("ct0", ct0, None), ("guest_id", "v1%3A1", None), *extra)


class Calls:
    def __init__(self, *results):
        self.results, self.seen = list(results), []

    def __call__(self, label, mode):
        self.seen.append((label, mode))
        return self.results.pop(0)


# --- pool keys --------------------------------------------------------------------------------------------------

def test_harvest_keys_literal_defaults_for_fresh_and_migrated_accounts():
    assert xp.HARVEST_ACCOUNT_DEFAULTS == HARVEST_DEFAULTS
    pool = xp.XPool(LABELS, clock=Clock())
    pool.begin_pass()
    assert {k: state()["accounts"]["acct1"][k] for k in HARVEST_DEFAULTS} == HARVEST_DEFAULTS
    doc = state()
    for a in doc["accounts"].values():
        for k in HARVEST_DEFAULTS:
            del a[k]
    pool.path.write_text(json.dumps(doc), encoding="utf-8")
    xp.XPool(LABELS, clock=Clock()).begin_pass()
    assert {k: state()["accounts"]["acct2"][k] for k in HARVEST_DEFAULTS} == HARVEST_DEFAULTS


@pytest.mark.parametrize("bad", [
    {"harvest_day": "2026-10-27T00:00:00+00:00"}, {"harvest_day": 1}, {"harvest_state": "made_up"},
    {"harvest_state": None}, {"harvest_reason": "not_allowlisted"}, {"harvest_reason": 3},
])
def test_harvest_bad_values_are_rejected(bad):
    pool = xp.XPool(LABELS, clock=Clock())
    pool.begin_pass()
    doc = state()
    doc["accounts"]["acct1"].update(bad)
    pool.path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(xp.XPoolStateError):
        xp.XPool(LABELS, clock=Clock())


def test_harvest_rollback_strip_set_is_exactly_the_three_keys():
    assert set(xp.HARVEST_ACCOUNT_DEFAULTS) <= xp.ACCOUNT_KEYS and len(xp.HARVEST_ACCOUNT_DEFAULTS) == 3
    assert not set(xp.HARVEST_ACCOUNT_DEFAULTS) & (set(xp.B2_ACCOUNT_KEYS) | set(xp.XDRIFT_ACCOUNT_DEFAULTS)
                                                   | set(xp.B3_ACCOUNT_DEFAULTS))


# --- the X day guard --------------------------------------------------------------------------------------------

def test_day_guard_once_per_account_per_utc_day_across_restart():
    clock = Clock()
    pool = xp.XPool(LABELS, clock=clock)
    day = T0.date().isoformat()
    assert pool.try_claim("x", "acct1", day) is True
    assert pool.try_claim("x", "acct1", day) is False
    restarted = xp.XPool(LABELS, clock=clock)  # a CLI process or a restarted worker sees the same claim
    assert restarted.try_claim("x", "acct1", day) is False
    assert restarted.try_claim("x", "acct2", day) is True
    assert restarted.try_claim("x", "acct1", (T0.date() + timedelta(days=1)).isoformat()) is True
    assert pool.try_claim("reddit", "acct2", "2026-10-29") is False
    assert pool.try_claim("x", "acct2", "yesterday") is False


def test_harvest_due_triggers_login_required_and_age_only_when_enabled():
    pool = xp.XPool(LABELS, clock=Clock())
    pool.mark_inactive("acct1", "x_login_required")
    assert pool.harvest_due({"acct1": None, "acct2": 9}, enabled=False, refresh_age_days=3) == []
    assert pool.harvest_due({"acct1": None, "acct2": 9}, enabled=True, refresh_age_days=None) == ["acct1"]
    assert pool.harvest_due({"acct1": None, "acct2": 2}, enabled=True, refresh_age_days=3) == ["acct1"]
    assert pool.harvest_due({"acct1": None, "acct2": 3}, enabled=True, refresh_age_days=3) == ["acct1", "acct2"]
    assert pool.harvest_due({"acct1": None, "acct2": None}, enabled=True, refresh_age_days=3) == ["acct1"]
    pool.try_claim("x", "acct1", T0.date().isoformat())
    assert pool.harvest_due({}, enabled=True, refresh_age_days=None) == []  # never a second automatic attempt


def test_suspended_and_needs_owner_accounts_are_never_due():
    pool = xp.XPool(LABELS, clock=Clock())
    pool.mark_inactive("acct1", "x_account_suspended")
    pool.note_harvest("acct2", "needs_owner", "login_page")
    assert pool.harvest_due({"acct1": 50, "acct2": 50}, enabled=True, refresh_age_days=1) == []
    assert pool.account_state("acct2") == ("inactive", "x_login_required")


# --- hand-off and reactivation ----------------------------------------------------------------------------------

def _start(tmp_path, lib_, monkeypatch, **over):
    saved = []

    async def save(self, account):
        saved.append((self.db, account))

    store = {}

    async def add(self, username, cookies):
        self.lib.calls.append(("add_account_cookies", self.db, username))
        store[self.db] = cookies

    monkeypatch.setattr(FakePool, "save", save, raising=False)
    monkeypatch.setattr(FakePool, "add_account_cookies", add)
    d = accounts(tmp_path)
    config = cfg(d, x_cookie_harvest_enabled=True, x_account_profiles={"acct1": "p1", "acct2": "p2"}, **over)
    s = tr.start(config, env=GOOD_ENV, repo_root=tmp_path / "repo", dist_lookup=lookup(), load=tr.load_library,
                 platform="manylinux_x86_64", dump_roots=[tmp_path / "tmp"])
    s.adapter._items = {("acct1", "boot"): object(), ("acct2", "boot"): object()}
    s.adapter._route_failures = {}
    return s, config, d, store, saved


def test_success_upserts_one_ct0_evicts_reader_schedules_canary_and_reactivates(tmp_path, lib, monkeypatch):
    s, config, d, store, saved = _start(tmp_path, lib, monkeypatch)
    pool = xp.from_config(config, clock=Clock())
    pool.set_canary_passed(labels=LABELS)
    pool.mark_canaried(LABELS)
    pool.mark_inactive("acct1", "x_login_required")
    lib.rows["acct1"] = row(active=False, error="login required", locks={"SearchTimeline": "L"})
    lib.rows["acct1"].stats = {"SearchTimeline": 7}
    old = s.readers["acct1"]
    check = Calls(result("logged_in", cookies=jar(extra=(("ct0", CT0, None),))))
    assert s.harvest(config, pool, T0, check=check) == {"acct1": "ok"}
    assert check.seen == [("acct1", "automatic")]
    assert store[str(d / "acct1.db")] == f"auth_token={AUTH}; ct0={CT0}"  # validated pair, one ct0
    db_row = saved[-1][1]
    assert (db_row.active, db_row.error_msg, db_row.locks) == (True, None, {"SearchTimeline": "L"})
    assert s.readers["acct1"] is not old and s.readers["acct2"] is not None  # the next real read reopens the DB
    assert [a["db"] for a in lib.apis].count(str(d / "acct1.db")) == 2
    assert ("acct1", "boot") not in s.adapter._items and ("acct2", "boot") in s.adapter._items
    assert pool.account_state("acct1") == ("active", None)
    assert pool.canary_passed_today() is False and pool.canary_accounts()[0] == "acct1"
    assert tr.cookie_ages(config, now=T0) == {"acct1": 0, "acct2": None}
    a = state()["accounts"]["acct1"]
    assert (a["harvest_state"], a["harvest_reason"], a["harvest_day"]) == ("ok", None, None)
    facts = [e for e in daily_facts.read_events(T0.date()) if e["kind"] == "session_check"]
    assert facts and facts[-1]["account"] == "acct1" and facts[-1]["result_class"] == "logged_in"


def test_conflicting_or_malformed_cookies_are_refused_before_any_upsert(tmp_path, lib, monkeypatch):
    s, config, d, store, _ = _start(tmp_path, lib, monkeypatch)
    for i, cookies in enumerate((jar(extra=(("ct0", "c" * 64, None),)), jar(auth="short"), jar(ct0="b;c=d" * 8),
                                 (("ct0", CT0, None),))):
        pool = xp.from_config(config, clock=Clock(T0 + timedelta(days=i)))
        pool.mark_inactive("acct1", "x_login_required")
        assert s.harvest(config, pool, T0 + timedelta(days=i), check=Calls(result("logged_in", cookies=cookies))) \
            == {"acct1": "failed"}
        assert state()["accounts"]["acct1"]["harvest_reason"] == "cookie_invalid"
    assert store == {} and pool.account_state("acct1") == ("inactive", "x_login_required")


def test_age_trigger_refreshes_an_active_account_without_touching_its_state(tmp_path, lib, monkeypatch):
    s, config, d, store, _ = _start(tmp_path, lib, monkeypatch, x_cookie_refresh_age_days=3)
    tr.refresh_cookies("acct2", "auth_token=x; ct0=y", config=config, env=GOOD_ENV, now=T0 - timedelta(days=4),
                       repo_root=tmp_path / "repo")
    tr.refresh_cookies("acct1", "auth_token=x; ct0=y", config=config, env=GOOD_ENV, now=T0 - timedelta(days=1),
                       repo_root=tmp_path / "repo")
    pool = xp.from_config(config, clock=Clock())
    check = Calls(result("logged_in", label="acct2", cookies=jar()))
    assert s.harvest(config, pool, T0, check=check) == {"acct2": "ok"}
    assert check.seen == [("acct2", "automatic")]
    assert tr.cookie_ages(config, now=T0) == {"acct1": 1, "acct2": 0}
    assert pool.account_state("acct2") == ("active", None)


@pytest.mark.parametrize("state_,reason", [("login_required", "login_page"), ("challenge", "challenge_page")])
def test_logged_out_or_challenge_pauses_needs_owner_and_no_second_attempt(tmp_path, lib, monkeypatch, state_,
                                                                          reason):
    s, config, d, store, _ = _start(tmp_path, lib, monkeypatch, x_cookie_refresh_age_days=1)
    tr.refresh_cookies("acct1", "auth_token=x; ct0=y", config=config, env=GOOD_ENV, now=T0 - timedelta(days=2),
                       repo_root=tmp_path / "repo")
    store.clear()
    pool = xp.from_config(config, clock=Clock())
    check = Calls(result(state_, reason))
    assert s.harvest(config, pool, T0, check=check) == {"acct1": "needs_owner"}
    assert pool.account_state("acct1") == ("inactive", "x_login_required")
    a = state()["accounts"]["acct1"]
    assert (a["harvest_state"], a["harvest_reason"]) == ("needs_owner", reason)
    assert s.harvest(config, pool, T0, check=check) == {} and len(check.seen) == 1
    assert s.harvest(config, xp.from_config(config, clock=Clock(T0 + timedelta(days=1))), T0 + timedelta(days=1),
                     check=check) == {}  # stays with the owner
    assert store == {}


def test_refused_gate_records_reason_and_keeps_the_account(tmp_path, lib, monkeypatch):
    s, config, d, store, _ = _start(tmp_path, lib, monkeypatch)
    pool = xp.from_config(config, clock=Clock())
    pool.mark_inactive("acct1", "x_login_required")
    assert s.harvest(config, pool, T0, check=Calls(result("refused", "containment_residual_unaccepted"))) \
        == {"acct1": "refused"}
    a = state()["accounts"]["acct1"]
    assert (a["harvest_state"], a["harvest_reason"]) == ("refused", "containment_residual_unaccepted")
    assert store == {}


def test_suspension_is_never_revived(tmp_path, lib, monkeypatch):
    s, config, d, store, _ = _start(tmp_path, lib, monkeypatch)
    pool = xp.from_config(config, clock=Clock())
    pool.mark_inactive("acct1", "x_account_suspended")
    check = Calls(result("logged_in", cookies=jar()))
    assert tr.harvest_account("acct1", config=config, pool=pool, check=check, upsert=lambda *a, **k: None,
                              mode="interactive") == ("failed", "account_suspended")
    assert check.seen == [] and pool.account_state("acct1") == ("inactive", "x_account_suspended")
    pool.note_harvest("acct1", "ok")
    assert pool.account_state("acct1") == ("inactive", "x_account_suspended")


def test_default_check_wires_the_pool_day_guard_and_x_route_provider(tmp_path, lib, monkeypatch):
    s, config, d, store, _ = _start(tmp_path, lib, monkeypatch, browser_path=str(tmp_path / "edge.exe"),
                                    browser_profiles_dir=str(tmp_path / "profiles"))
    seen = []
    monkeypatch.setattr(bs.bh, "BrowserHost", lambda *a, **k: "HOST")

    def fake_check(site, label, *, host, profile_name, day_guard, routes, mode, timeout):
        seen.append((site, label, host, profile_name, mode, timeout, type(routes).__name__))
        if mode == "automatic" and not day_guard.try_claim(site, label, T0.date().isoformat()):
            return bs.SessionResult(site, label, "failed", "daily_check_used", mode, False)
        return result("refused", "browser_unadmitted")

    monkeypatch.setattr(bs, "check_session", fake_check)
    pool = xp.from_config(config, clock=Clock())
    pool.mark_inactive("acct1", "x_login_required")
    assert s.harvest(config, pool, T0) == {"acct1": "refused"}
    assert seen == [("x", "acct1", "HOST", "p1", "automatic", config.x_harvest_timeout_s, "XRouteProvider")]
    assert state()["accounts"]["acct1"]["harvest_day"] == T0.date().isoformat()
    check = tr.session_check(config, xp.from_config(config, clock=Clock()), s.runtime)
    assert check("acct1", "automatic").reason == "daily_check_used"  # the CLI and the worker share the claim


def test_harvest_status_block_only_when_enabled():
    pool = xp.XPool(LABELS, clock=Clock())
    assert "harvest" not in pool.health()["accounts"][0]
    pool.harvest_status = True
    pool.try_claim("x", "acct1", T0.date().isoformat())
    pool.note_harvest("acct1", "refused", "browser_busy")
    assert pool.health()["accounts"][0]["harvest"] == {"state": "refused", "reason": "browser_busy",
                                                       "last_at": T0.date().isoformat()}


# --- the X route provider (CK-6) --------------------------------------------------------------------------------

def _runtime(*, policy=None, admitted=True, required=False, now=T0):
    config = cfg("", x_proxy_required=required)
    snap = types.SimpleNamespace(config=config, policy=policy, revisions={"acct1": "rev-1"},
                                 assignments={"acct1": types.SimpleNamespace(route="ROUTE")} if policy else {})
    rt = types.SimpleNamespace(snapshot=snap, clock=lambda: now,
                               admissions={"acct1": types.SimpleNamespace(revision="rev-1",
                                                                          expires_at=now + timedelta(minutes=30))})
    rt.admitted = lambda label: admitted and label in rt.admissions
    return rt


def test_route_provider_direct_proxy_and_refusals():
    direct = tr.XRouteProvider(_runtime(), clock=lambda: 100.0).admitted_route("x", "acct1")
    assert isinstance(direct, bs.AdmittedRoute) and direct.mode == "direct" and direct.revision == "rev-1"
    assert direct.admission() == relay.Admission("rev-1", 100.0 + tr.DIRECT_ADMISSION_S)
    rt = _runtime(policy=object())
    proxy = tr.XRouteProvider(rt, clock=lambda: 100.0).admitted_route("x", "acct1")
    assert (proxy.mode, proxy.revision, proxy.route) == ("proxy", "rev-1", "ROUTE")
    assert proxy.admission() == relay.Admission("rev-1", 100.0 + 1800.0)
    rt.admissions.clear()
    assert proxy.admission() is None  # admission withdrawn mid-session: the relay refuses the next CONNECT
    for runtime, site, label in ((_runtime(policy=object(), admitted=False), "x", "acct1"),
                                 (_runtime(required=True), "x", "acct1"), (_runtime(), "reddit", "acct1"),
                                 (_runtime(), "x", "acct2"), (None, "x", "acct1")):
        assert tr.XRouteProvider(runtime).admitted_route(site, label) == "proxy_not_admitted"


# --- owner command ----------------------------------------------------------------------------------------------

def test_harvest_cli_prints_codes_only(tmp_path, monkeypatch, capsys):
    from api.data.attention import web_queries
    config = cfg("")
    monkeypatch.setattr(web_queries, "load", lambda *a: types.SimpleNamespace(config=config))
    calls = []

    def fake(label, *, config, now, config_path=None, interactive=False):
        calls.append((label, interactive))
        return "needs_owner", "login_page"

    monkeypatch.setattr(tr, "harvest_cli", fake)
    assert tr.main(["--harvest-cookies", "acct1", "--interactive"]) == 2
    assert calls == [("acct1", True)]
    assert capsys.readouterr().out.strip() == "harvest status=needs_owner reason=login_page label=acct1"
    with pytest.raises(SystemExit):
        tr.main(["--refresh-cookies", "acct1", "--interactive"])


def test_harvest_cli_owner_interactive_bypasses_day_guard_and_upserts(tmp_path, lib, monkeypatch):
    s, config, d, store, _ = _start(tmp_path, lib, monkeypatch)
    xp.from_config(config, clock=Clock()).try_claim("x", "acct1", T0.date().isoformat())
    rt = types.SimpleNamespace(snapshot=types.SimpleNamespace(policy=None), reconcile=lambda pool: set())
    check = Calls(result("logged_in", cookies=jar(), mode="interactive"))
    out = tr.harvest_cli("acct1", config=config, now=T0, interactive=True, runtime_factory=lambda *a, **k: rt,
                         check=check, env=GOOD_ENV, repo_root=tmp_path / "repo")
    assert out == ("ok", None) and check.seen == [("acct1", "interactive")]
    assert store[str(d / "acct1.db")] == f"auth_token={AUTH}; ct0={CT0}"
    assert AUTH not in (d / "cookie_ages.json").read_text(encoding="utf-8")


def test_no_cookie_value_reaches_state_facts_or_health(tmp_path, lib, monkeypatch):
    s, config, d, store, _ = _start(tmp_path, lib, monkeypatch)
    pool = xp.from_config(config, clock=Clock())
    pool.mark_inactive("acct1", "x_login_required")
    lib.rows["acct1"] = row(active=False, error="login required")
    lib.rows["acct1"].stats = {}
    s.harvest(config, pool, T0, check=Calls(result("logged_in", cookies=jar())))
    texts = [pool.path.read_text(encoding="utf-8"), json.dumps(pool.health()), json.dumps(pool.log),
             (d / "cookie_ages.json").read_text(encoding="utf-8")]
    texts += [p.read_text(encoding="utf-8") for p in daily_facts.facts_dir().glob("*.jsonl")]
    assert not any(AUTH in t or CT0 in t for t in texts)
