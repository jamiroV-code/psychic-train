"""Politeness: per-host minimum delay, global and per-host concurrency, honest user agent."""
from __future__ import annotations

import threading
import time
from contextlib import contextmanager

USER_AGENT = "data-integration-tooling/0.1 (owner-run research tool; honours robots.txt)"


class Politeness:
    def __init__(self, min_delay: float = 1.0, max_concurrent: int = 2, max_per_host: int = 1,
                 clock=time.monotonic, sleeper=time.sleep):
        self.min_delay = max(0.0, float(min_delay))
        self._clock = clock
        self._sleep = sleeper
        self._max_per_host = max(1, int(max_per_host))
        self._global = threading.BoundedSemaphore(max(1, int(max_concurrent)))
        self._lock = threading.Lock()
        self._next_start: dict[str, float] = {}
        self._host_sems: dict[str, threading.BoundedSemaphore] = {}

    def _host_sem(self, host: str) -> threading.BoundedSemaphore:
        with self._lock:
            return self._host_sems.setdefault(host, threading.BoundedSemaphore(self._max_per_host))

    def _reserve_wait(self, host: str) -> float:
        with self._lock:
            now = self._clock()
            start = max(now, self._next_start.get(host, now))
            self._next_start[host] = start + self.min_delay
            return start - now

    @contextmanager
    def slot(self, host: str):
        """Hold a concurrency slot for `host`, waiting out the minimum delay first."""
        host = (host or "").lower()
        host_sem = self._host_sem(host)
        with self._global, host_sem:
            wait = self._reserve_wait(host)
            if wait > 0:
                self._sleep(wait)
            yield
