"""B2 E5/E6 real temporary state/OS locks, fake UTC clocks, no requests."""
from __future__ import annotations

import json
import multiprocessing
import os
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from api.data import cache
from api.data.attention import x_pool, x_proxy as p
from api.data.attention.x_proxy_private import atomic_json, state_lock

NOW = datetime(2026, 11, 4, 12, tzinfo=UTC)


@pytest.fixture(autouse=True)
def isolated(attention_cache):
    return attention_cache


class Clock:
    def __init__(self, now=NOW): self.now = now
    def __call__(self): return self.now


def pool(clock=None, labels=("alpha", "beta"), cap=None):
    return x_pool.XPool(list(labels), clock=clock or Clock(), cap=cap)


def routed(instance, label="alpha"):
    instance.proxy_required = True
    instance.reconcile_proxy(label, str(uuid4()), str(uuid4()))
    instance.proxy_result(label, reason=None)


def test_old_and_partial_migration_read_only_then_persist_complete():
    instance = pool()
    instance.begin_pass()
    raw = json.loads(instance.path.read_text())
    raw.pop("proxy_provider_budget")
    for account in raw["accounts"].values():
        for key in x_pool.B2_ACCOUNT_KEYS:
            account.pop(key)
    raw["accounts"]["alpha"]["reads_day"] = NOW.date().isoformat()
    raw["accounts"]["alpha"]["reads_used"] = 7
    atomic_json(instance.path, raw)
    before = instance.path.read_bytes()
    loaded = pool()
    assert loaded._s["proxy_provider_budget"] == {"day": None, "used": 0}
    assert loaded.health()["accounts"][0]["proxy_state"] == "unknown"
    assert loaded.path.read_bytes() == before
    loaded.charge("alpha", 2)
    saved = json.loads(loaded.path.read_text())
    assert saved["accounts"]["alpha"]["reads_used"] == 9
    assert set(saved["accounts"]["alpha"]) == x_pool.ACCOUNT_KEYS
    assert saved["proxy_provider_budget"] == {"day": None, "used": 0}


@pytest.mark.parametrize("budget", [{"day": None, "used": True}, {"day": None, "used": 1},
    {"day": NOW.date().isoformat(), "used": -1}, {"day": NOW.date().isoformat(), "used": 900},
    {"day": "bad", "used": 0}, {"day": NOW.date().isoformat(), "used": 0, "in_flight": True},
    {"day": (NOW + timedelta(days=1)).date().isoformat(), "used": 0}])
def test_corrupt_future_and_out_of_range_budget_refused(budget):
    instance = pool()
    instance.begin_pass()
    doc = json.loads(instance.path.read_text())
    doc["proxy_provider_budget"] = budget
    atomic_json(instance.path, doc)
    with pytest.raises(x_pool.XPoolStateError):
        pool()


@pytest.mark.parametrize("key,value", [("proxy_id", "https://SECRET"), ("identity_revision", 1),
    ("proxy_health", "direct"), ("proxy_reason", "SECRET"), ("proxy_reason", {}),
    ("proxy_checked_at", "2026-11-04T12:00:00+01:00"), ("proxy_health", "healthy")])
def test_proxy_state_exact_types_and_measurement_requirements(key, value):
    instance = pool()
    instance.begin_pass()
    doc = json.loads(instance.path.read_text())
    doc["accounts"]["alpha"][key] = value
    atomic_json(instance.path, doc)
    with pytest.raises(x_pool.XPoolStateError):
        pool()


def test_provider_null_day_reservation_is_durable_before_send_no_refund():
    instance = pool()
    instance.begin_pass()
    seen = []
    def send():
        seen.append(json.loads(instance.path.read_text())["proxy_provider_budget"])
        raise RuntimeError("synthetic request failure")
    with pytest.raises(RuntimeError):
        instance.provider_request(send)
    assert seen == [{"day": NOW.date().isoformat(), "used": 1}]
    assert pool()._s["proxy_provider_budget"]["used"] == 1


def test_cap_and_final_eleven_seconds_send_nothing():
    instance = pool()
    instance.begin_pass()
    doc = json.loads(instance.path.read_text())
    doc["proxy_provider_budget"] = {"day": NOW.date().isoformat(), "used": 899}
    atomic_json(instance.path, doc)
    with pytest.raises(p.ProxyFailure, match="proxy_budget"):
        instance.provider_request(lambda: pytest.fail("sent at cap"))
    clock = Clock(NOW.replace(hour=23, minute=59, second=49))
    instance = pool(clock)
    doc["proxy_provider_budget"] = {"day": None, "used": 0}
    atomic_json(instance.path, doc)
    with pytest.raises(p.ProxyFailure, match="proxy_budget"):
        instance.provider_request(lambda: pytest.fail("sent in final eleven seconds"))
    assert pool()._s["proxy_provider_budget"] == {"day": None, "used": 0}


def test_day_rollover_reset_and_between_reservation_send_no_refund(monkeypatch):
    clock = Clock()
    instance = pool(clock)
    instance.begin_pass()
    instance.provider_request(lambda: None)
    clock.now += timedelta(days=1)
    instance.provider_request(lambda: None)
    assert instance._s["proxy_provider_budget"] == {"day": clock.now.date().isoformat(), "used": 1}
    save = instance._save
    def rollover_save():
        save()
        clock.now += timedelta(days=1)
    monkeypatch.setattr(instance, "_save", rollover_save)
    with pytest.raises(p.ProxyFailure, match="proxy_budget"):
        instance.provider_request(lambda: pytest.fail("sent after reservation day changed"))
    persisted = json.loads(instance.path.read_text())["proxy_provider_budget"]
    assert persisted["used"] == 2 and persisted["day"] < clock.now.date().isoformat()


def test_stale_collector_save_cannot_overwrite_provider_reservation():
    first = pool()
    first.begin_pass()
    second = pool()
    second.provider_request(lambda: None)
    first.charge("alpha", 3)
    fresh = pool()
    assert fresh._s["proxy_provider_budget"]["used"] == 1
    assert fresh.reads_today("alpha") == 3


def test_nested_mutation_uses_explicit_ownership_not_second_lock():
    instance = pool()
    assert instance.note_parse_drop("alpha", "stripped") == 1
    assert instance.note_parse_drop("alpha", "stripped") == 2
    assert instance.account_state("alpha")[0] == "suspect"
    assert instance._lock_owned is None


def test_provider_holds_shared_lock_through_completion_even_same_pool_threads():
    instance = pool()
    instance.begin_pass()
    entered, finish, charged = threading.Event(), threading.Event(), threading.Event()
    failures = []
    def request():
        try:
            instance.provider_request(lambda: (entered.set(), finish.wait(3)))
        except BaseException as error:
            failures.append(type(error).__name__)
    def charge():
        try:
            instance.charge("alpha", 1)
            charged.set()
        except BaseException as error:
            failures.append(type(error).__name__)
    a = threading.Thread(target=request)
    a.start()
    assert entered.wait(3)
    b = threading.Thread(target=charge)
    b.start()
    assert not charged.wait(0.1)
    finish.set()
    a.join(5)
    b.join(5)
    assert not a.is_alive() and not b.is_alive() and charged.is_set() and failures == []
    assert pool()._s["proxy_provider_budget"]["used"] == 1


def _provider_process(root, entered, release, counter, output, crash=False):
    cache.CACHE_ROOT = Path(root)
    instance = x_pool.XPool(["alpha", "beta"], clock=lambda: NOW)
    def send():
        with counter.get_lock(): counter.value += 1
        entered.set()
        if crash: os._exit(31)
        release.wait(5)
        return "sent"
    try:
        output.put(instance.provider_request(send))
    except p.ProxyFailure as error:
        output.put(error.reason)


def test_two_processes_one_remaining_quota_and_single_inflight():
    instance = pool()
    instance.begin_pass()
    doc = json.loads(instance.path.read_text())
    doc["proxy_provider_budget"] = {"day": NOW.date().isoformat(), "used": 898}
    atomic_json(instance.path, doc)
    ctx = multiprocessing.get_context("spawn")
    entered, release, counter, output = ctx.Event(), ctx.Event(), ctx.Value("i", 0), ctx.Queue()
    children = [ctx.Process(target=_provider_process, args=(str(cache.CACHE_ROOT), entered, release, counter, output)) for _ in range(2)]
    try:
        children[0].start()
        assert entered.wait(10)
        children[1].start()
        assert counter.value == 1
        release.set()
        for child in children: child.join(12)
        assert all(child.exitcode == 0 for child in children)
        assert sorted(output.get(timeout=2) for _ in children) == ["proxy_budget", "sent"]
        assert counter.value == 1 and pool()._s["proxy_provider_budget"]["used"] == 899
    finally:
        release.set()
        for child in children:
            if child.is_alive(): child.terminate()
            if child.pid is not None: child.join(3)
        output.close()


def test_process_death_releases_lock_but_consumes_reservation():
    instance = pool()
    instance.begin_pass()
    ctx = multiprocessing.get_context("spawn")
    entered, release, counter, output = ctx.Event(), ctx.Event(), ctx.Value("i", 0), ctx.Queue()
    child = ctx.Process(target=_provider_process, args=(str(cache.CACHE_ROOT), entered, release, counter, output, True))
    try:
        child.start()
        assert entered.wait(10)
        child.join(10)
        assert child.exitcode == 31
        recovered = pool()
        assert recovered._s["proxy_provider_budget"]["used"] == 1
        recovered.provider_request(lambda: None)
        assert pool()._s["proxy_provider_budget"]["used"] == 2
    finally:
        if child.is_alive(): child.terminate()
        child.join(3)
        output.close()


def test_quarantine_wake_precedes_later_lock_and_never_clears_day_pause():
    clock = Clock()
    instance = pool(clock, cap=1)
    routed(instance)
    routed(instance, "beta")
    instance.charge("alpha", 1)
    instance.proxy_result("alpha", reason="proxy_transport", quarantine_seconds=600)
    instance.wait_for_lock("beta", NOW + timedelta(hours=1))
    assert instance.pause_no_account() == "proxy_quarantine"
    assert instance.resume_at() == NOW + timedelta(seconds=600)
    instance.pause_day("cloudflare_block")
    assert instance.pause_for_proxies()
    assert instance.pause_reason() == "cloudflare_block"
    assert instance.resume_at() == NOW + timedelta(seconds=600)
    clock.now += timedelta(seconds=601)
    instance.proxy_result("alpha", reason=None)
    assert instance.account_state("alpha") == ("locked", "account_cap")
    assert instance.pause_reason() == "cloudflare_block"


def test_route_change_preserves_charges_and_invalidates_only_changed_canary():
    instance = pool()
    routed(instance)
    routed(instance, "beta")
    instance.charge("alpha", 7)
    instance.set_canary_passed(labels=["alpha", "beta"])
    prior_beta = dict(instance._acct("beta"))
    assert instance.reconcile_proxy("alpha", str(uuid4()), str(uuid4()))
    assert instance.reads_today("alpha") == 7 and instance._acct("beta") == prior_beta
    assert instance._s["canary_labels"] == ["beta"] and not instance.canary_passed_today()
    assert "8.8.8.8" not in instance.path.read_text()


def test_stopped_rollback_exact_keys_preserves_part_a_data():
    instance = pool()
    routed(instance)
    instance.charge("alpha", 4)
    doc = json.loads(instance.path.read_text())
    doc.pop("proxy_provider_budget")
    for account in doc["accounts"].values():
        for key in x_pool.B2_ACCOUNT_KEYS: account.pop(key)
    assert doc["accounts"]["alpha"]["reads_used"] == 4
    assert not any(key.startswith("proxy_") or key == "identity_revision" for key in doc["accounts"]["alpha"])
    atomic_json(instance.path, doc)
    assert pool().reads_today("alpha") == 4


def test_changed_recent_account_canary_prioritized_and_pending_survives_batch():
    labels = ("alpha", "beta", "gamma", "delta", "epsilon")
    instance = pool(labels=labels)
    instance.begin_pass()
    instance.mark_canaried(labels)
    instance.set_canary_passed(labels=labels)
    for label in labels:
        instance.reconcile_proxy(label, str(uuid4()), str(uuid4()))
    instance.proxy_required = False
    first = instance.canary_accounts()
    assert len(first) == 3
    instance.mark_canaried(first)
    instance.set_canary_passed(labels=first)
    assert not instance.canary_passed_today()
    assert set(labels) - set(first) <= set(instance.canary_accounts())
    second = instance.canary_accounts()
    instance.mark_canaried(second)
    instance.set_canary_passed(labels=second)
    assert instance.canary_passed_today()
    assert set(instance.canary_labels()) == set(labels)
