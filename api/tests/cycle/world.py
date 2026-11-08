"""Three UTC-day acceptance world built on the production worker and real upstream reader."""
from __future__ import annotations

import asyncio
import dataclasses
import json
import random
from contextlib import ExitStack
from datetime import UTC, datetime, timedelta

from api.data import attention_pc_refresh as worker_module, cache
from api.data.attention import pc_pace, twscrape_reader as tr, web_queries as wq
from api.data.attention import x_filters, x_pool, x_queryids, x_window
from api.tests.cycle.services import AUTH, CSRF, Clock, Origin


class CycleWorld:
    def __init__(self, root, patch):
        self.root, self.patch = root, patch
        self.stack = ExitStack()
        self.clock = Clock()
        self.results = {}
        self.labels = tuple(AUTH)
        self.worker = None
        self.start = None

    def __enter__(self):
        self.cache = self.root / "cache"
        self.private = self.root / "private"
        self.private.mkdir()
        certs = self.private / "tls"
        certs.mkdir()
        self.patch.setattr(cache, "CACHE_ROOT", self.cache)
        cache.bootstrap_cache_dirs()
        self.origin = Origin(certs, self.clock)
        self.stack.callback(self.origin.close)
        self.origin.install(self.patch)
        self.lib = tr.load_library()
        for label in self.labels[:-1]:  # acc_e registers later (C7), with its own account file then
            api = self.lib.API(str(self.private / f"{label}.db"))
            asyncio.run(api.pool.add_account_cookies(label, f"auth_token={AUTH[label]}; ct0={CSRF}"))
        q = wq.load()
        self.coins = [s for s in q.coins if x_window.coin_terms(q, s) is not None][:14]
        assert len(self.coins) == 14
        self.config = dataclasses.replace(q.config, x_accounts=self.labels[:-1],
            x_accounts_db_path=str(self.private), x_account_daily_cap=80, x_account_rest_days=0, x_pool_max=5,
            x_daily_post_budget=800, x_backfill_days=0, x_proxy_required=False,
            x_proxy_list_path=None, x_proxy_assignments_path=None, x_proxy_policy_path=None,
            x_queryid_mode="off", x_cookie_harvest_enabled=False, x_quiet_hours_enabled=False,
            x_mixed_traffic_enabled=False, x_variation_enabled=False, x_adaptive_cooldown_enabled=False,
            x_warmup_enabled=False, reddit_live_methods=())
        self.queries = dataclasses.replace(q, config=self.config)
        # The real start(): env guard, pin, account files, B2 runtime (all-null direct), identity adapter, readers.
        self.start = tr.start(self.config, env=dict(tr.REQUIRED_ENV), dump_roots=[])
        self.stack.callback(self.start.close)
        self.worker = worker_module.AttentionPcWorker(clock=self.clock, wait=self.clock.wait,
            queries=lambda: self.queries, symbols=lambda q, source: self.coins,
            x_start=lambda cfg: self.start, x_cleanup=lambda: None, seed=19,
            reddit_ledger=lambda: None)
        return self

    def __exit__(self, *args):
        return self.stack.__exit__(*args)

    def set_config(self, **changes):
        self.config = dataclasses.replace(self.config, **changes)
        self.queries = dataclasses.replace(self.queries, config=self.config)

    def record(self, scenario, **observed):
        self.results[scenario] = {"state": "passed", "observed": observed}

    def pool(self):
        return x_pool.from_config(self.config, clock=self.clock)

    def source(self):
        return self.worker.streams[worker_module.X_SOURCE].source_state(self.queries)

    def prefer(self, pool, label):
        # Drive the real LRU selection using real usage timestamps, not a replacement selector.
        self.clock.sleep(600)
        for other in pool.labels:
            if other != label:
                pool.mark_used(other)

    def unit(self, pool, symbol="SOL"):
        day = self.clock().date() - timedelta(days=1)
        terms = x_window.coin_terms(self.queries, symbol)
        query = x_window.build_query(terms, day, syntax=self.config.x_window_syntax, lang="en")
        return x_pool.run_unit(pool, self.start.readers, self.source(), self.config, symbol=symbol, day=day,
            query=query, coin=x_filters.Coin(symbol, self.queries.coins[symbol]["name"]),
            policy=x_filters.FilterPolicy.from_config(self.config, self.queries.coins[symbol]),
            rng=random.Random(19), sleep=self.clock.sleep, bind=self.start.bind_query)

    def next_day(self, minutes=30):
        """Advance the virtual UTC clock to the next day; wall-clock deadlines stay real."""
        nxt = datetime.combine(self.clock().date() + timedelta(days=1), datetime.min.time(), tzinfo=UTC)
        self.clock.sleep((nxt - self.clock()).total_seconds() + minutes * 60)

    def canary(self, pool):
        out = x_pool.run_daily_canary(pool, self.start.readers, self.source(), self.config,
                                      rng=random.Random(19), sleep=self.clock.sleep)
        assert out.passed, out
        return out

    def baseline(self):
        stream = self.worker.streams[worker_module.X_SOURCE]
        outcome = stream.run_pass(stop_at=self.clock() + timedelta(hours=23))
        pool, source = self.pool(), self.source()
        assert pool.canary_passed_today()
        assert source.used <= self.config.x_daily_post_budget
        assert "behaviour" not in pool.health()
        coin_requests = [r for r in self.origin.requests if r.get("symbol")]
        assert coin_requests and len({r["label"] for r in coin_requests}) > 1
        times = sorted({r["at"] for r in coin_requests if not r.get("cursor")})
        assert len(times) > 1 and all(a < b for a, b in zip(times, times[1:]))
        assert any(pool.account_state(label) == ("locked", "account_cap") for label in pool.labels)
        units = {}
        for row in coin_requests:
            units.setdefault(row["symbol"], set()).add(row["label"])
        assert all(len(labels) == 1 for labels in units.values())
        self.record("C1", outcome=outcome, reads=source.used, accounts=len(pool.labels),
                    canary=True, optional_switches="all_off", spread=True)
        self.record("C2", capped=[x for x in pool.labels if pool.account_state(x)[1] == "account_cap"],
                    no_split=True, ceiling=self.config.x_daily_post_budget)

    def first_restriction(self):
        self.next_day()
        self.set_config(x_account_daily_cap=1000)
        pool = self.pool()
        self.canary(pool)
        self.origin.restricted.add("acc_b")
        self.prefer(pool, "acc_b")
        out = self.unit(pool)
        assert out.result is not None and out.label != "acc_b" and out.restarts == 1, (out.reason, out.label, out.restarts)
        assert pool.account_state("acc_b") == ("locked", "endpoint_restricted")
        assert pool.health()["drift_streak"] == 0
        self.first_404_day = self.clock().date()

    def run(self):
        self.baseline()
        self.first_restriction()
