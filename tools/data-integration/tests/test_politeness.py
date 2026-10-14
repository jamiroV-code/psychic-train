"""Politeness: per-host delay, concurrency caps, honest user agent, fake clock and sleeper."""
from __future__ import annotations

import threading
import time

from data_integration.politeness import USER_AGENT, Politeness


class FakeTime:
    def __init__(self):
        self.now = 100.0
        self.sleeps: list[float] = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def test_burst_to_one_host_is_spaced_by_min_delay():
    ft = FakeTime()
    p = Politeness(min_delay=5.0, clock=ft.clock, sleeper=ft.sleep)
    starts = []
    for _ in range(4):
        with p.slot("a.example.test"):
            starts.append(ft.now)
    assert [round(b - a, 6) for a, b in zip(starts, starts[1:])] == [5.0, 5.0, 5.0]
    assert ft.sleeps[0] == 0 or len(ft.sleeps) == 3


def test_different_hosts_do_not_wait_on_each_other():
    ft = FakeTime()
    p = Politeness(min_delay=5.0, clock=ft.clock, sleeper=ft.sleep)
    with p.slot("a.example.test"):
        pass
    with p.slot("b.example.test"):
        pass
    assert ft.sleeps == []


def test_no_wait_once_delay_has_elapsed():
    ft = FakeTime()
    p = Politeness(min_delay=5.0, clock=ft.clock, sleeper=ft.sleep)
    with p.slot("a.example.test"):
        pass
    ft.now += 6
    with p.slot("a.example.test"):
        pass
    assert ft.sleeps == []


def test_per_host_concurrency_cap_is_one():
    p = Politeness(min_delay=0, max_per_host=1, max_concurrent=4, sleeper=lambda s: None)
    active, peak, lock = [0], [0], threading.Lock()

    def work():
        with p.slot("a.example.test"):
            with lock:
                active[0] += 1
                peak[0] = max(peak[0], active[0])
            time.sleep(0.02)
            with lock:
                active[0] -= 1

    threads = [threading.Thread(target=work) for _ in range(5)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert peak[0] == 1


def test_global_concurrency_cap():
    p = Politeness(min_delay=0, max_per_host=5, max_concurrent=2, sleeper=lambda s: None)
    active, peak, lock = [0], [0], threading.Lock()

    def work(host):
        with p.slot(host):
            with lock:
                active[0] += 1
                peak[0] = max(peak[0], active[0])
            time.sleep(0.02)
            with lock:
                active[0] -= 1

    threads = [threading.Thread(target=work, args=(f"h{i}.example.test",)) for i in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert peak[0] <= 2


def test_slot_released_after_exception():
    p = Politeness(min_delay=0, max_per_host=1, sleeper=lambda s: None)
    try:
        with p.slot("a.example.test"):
            raise RuntimeError("x")
    except RuntimeError:
        pass
    with p.slot("a.example.test"):
        pass


def test_user_agent_is_honest_and_has_no_contact_data():
    assert "data-integration" in USER_AGENT
    assert "Mozilla" not in USER_AGENT
    assert "@" not in USER_AGENT and "http" not in USER_AGENT.lower()
