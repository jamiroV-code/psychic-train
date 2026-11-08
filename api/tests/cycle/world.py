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
from api.data.attention import daily_facts, x_behaviour, x_behaviour_report, x_filters, x_pool, x_queryids, x_window
from api.tests.cycle import browser as cb
from api.tests.cycle import closing, reddit, relay
from api.tests.cycle.services import AUTH, CSRF, NEW_AUTH, Clock, Origin


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
        import sys
        module = sys.modules["twscrape.api"]  # the bound query ID is a process global: restored on exit
        self.patch.setattr(module, "OP_SearchTimeline", module.OP_SearchTimeline)
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

    def prefer(self, pool, label, then=None):
        # Drive the real LRU selection using real usage timestamps, not a replacement selector.
        self.clock.sleep(600)
        if then is not None:
            pool.mark_used(then)
            self.clock.sleep(1)
        for other in pool.labels:
            if other not in (label, then):
                pool.mark_used(other)

    def unit(self, pool, symbol="SOL"):
        self.clock.sleep(self.config.x_query_delay_min_s + 1)  # the real pace minimum between units
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
        self.clock.sleep(self.config.x_query_delay_min_s + 1)
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
        """C4 day 1 (simulated UTC day 2): acc_b 404s on a valid ID; the unit reruns once on another account."""
        self.next_day()
        self.set_config(x_account_daily_cap=1000)
        pool = self.pool()
        self.canary(pool)
        self.origin.restricted.add("acc_b")
        self.prefer(pool, "acc_b")
        drift = pool.health()["drift_streak"]
        out = self.unit(pool)
        assert out.result is not None and out.label != "acc_b" and out.restarts == 1, (out.reason, out.label, out.restarts)
        assert pool.account_state("acc_b") == ("locked", "endpoint_restricted")
        assert pool.health()["drift_streak"] == drift
        self.c4 = {"day1": {"state": list(pool.account_state("acc_b")), "rerun_on": out.label,
                            "restarts": out.restarts, "units_counted": 1, "drift_streak": drift}}

    def suspension(self):
        """C5: acc_c answers (64); deactivated, the coin-day fails over once and is counted once."""
        pool = self.pool()
        self.origin.suspended.add("acc_c")
        self.prefer(pool, "acc_c")
        source = self.source()
        before_used = source.used
        out = self.unit(pool, self.coins[1])
        source = self.source()
        assert out.result is not None and out.label not in ("acc_c", "acc_b"), (out.reason, out.label)
        assert pool.account_state("acc_c")[1] == "x_account_suspended", pool.account_state("acc_c")
        assert out.restarts == 1, out.restarts
        assert source.used - before_used == out.reads, (source.used - before_used, out.reads)
        self.record("C5", state=list(pool.account_state("acc_c")), failover_to=out.label, restarts=out.restarts,
                    reads_charged_once=out.reads)

    def query_state(self):
        return x_queryids.load(x_queryids.state_path(cache.CACHE_ROOT))

    def rotation_adopted(self):
        """C3 (mid day 2): the server rotates the ID; 404 on two accounts -> isolation -> candidate -> forced
        evaluation passes on selectable accounts -> adopted; no DRIFT_STOP; the next read carries the new ID."""
        self.set_config(x_queryid_mode="auto")
        pool = self.pool()
        pinned = x_queryids.PINNED["SearchTimeline"]
        self.new_query_id = "CycleRotatedQueryId0A"
        self.origin.query_id = self.new_query_id
        bound = self.start.query_boundary(self.config, pool, cache.CACHE_ROOT, self.clock())
        candidate = self.query_state()["operations"]["SearchTimeline"]["candidate"]
        assert bound == pinned and candidate and candidate["id"] == self.new_query_id, (bound, candidate)
        mark = len(self.origin.requests)
        out = self.unit(pool, self.coins[2])
        state = self.query_state()
        op = state["operations"]["SearchTimeline"]
        assert x_queryids.active_id(state) == self.new_query_id, (out.reason, op, state["evidence"])
        assert op["active"]["source"] == "bundle" and op["candidate"] is None
        assert not pool.stopped_reason() and pool.health()["drift_streak"] == 0, out.reason
        four04 = {r["label"] for r in self.origin.requests[mark:] if r.get("query_id") == pinned and r.get("symbol")}
        assert len(four04) == 2, four04
        after = self.unit(pool, self.coins[2])
        assert after.result is not None, after.reason
        assert self.origin.requests[-1].get("query_id") == self.new_query_id
        self.c3 = {"isolation_accounts": len(four04), "candidate_from_bundle": True, "first_unit": out.reason,
                   "adopted": {"evidence": [e["result"] for e in state["evidence"]], "active_source": "bundle",
                               "drift_streak": 0, "stopped": None, "next_read_query_id": "rotated"},
                   "child_query_id": {"direct_off_path": "rotated ID observed on the wire after adoption"}}

    def open_day3(self):
        """Day 3 opens: the bundle already advertises a newer ID while the server still accepts the adopted one."""
        self.next_day(minutes=180)
        pool = self.pool()
        self.third_query_id = "CycleRotatedQueryId0B"
        self.origin.bundle_id = self.third_query_id
        self.start.query_boundary(self.config, pool, cache.CACHE_ROOT, self.clock())
        assert self.query_state()["operations"]["SearchTimeline"]["candidate"]["id"] == self.third_query_id
        self.canary(pool)

    def rotation_inconclusive(self):
        """C3 (day 3): after the server switches, the forced evaluation is inconclusive (too few results) and
        nothing is adopted."""
        pool = self.pool()
        self.origin.query_id = self.third_query_id
        self.origin.inconclusive.update(self.labels)
        before = len(self.query_state()["evidence"])
        out = self.unit(pool, self.coins[3])
        self.origin.inconclusive.clear()
        self.origin.query_id, self.origin.bundle_id = self.new_query_id, None
        state = self.query_state()
        verdicts = [e["result"] for e in state["evidence"][before:]]
        assert out.result is None and x_queryids.active_id(state) == self.new_query_id, (out.reason, verdicts)
        assert verdicts and set(verdicts) == {"inconclusive"}, verdicts
        assert not pool.stopped_reason()
        self.c3["inconclusive"] = {"unit_reason": out.reason, "verdicts": verdicts, "active": "unchanged"}
        self.c3["not_exercised"] = [
            "routed B2 child envelope query_id: the cycle runs the all-null direct configuration, so no routed "
            "child is spawned here (routed envelope v2 is covered by test_x_proxy_spawn only)"]
        self.record("C3", **self.c3)

    def second_restriction(self):
        """C4 day 2 (simulated UTC day 3): a second restricted event on a different day locks acc_b 24 h."""
        pool = self.pool()
        self.prefer(pool, "acc_b")
        drift = pool.health()["drift_streak"]
        out = self.unit(pool, self.coins[1])
        assert out.result is not None and out.label != "acc_b" and out.restarts == 1, (out.reason, out.label)
        assert pool.account_state("acc_b") == ("locked", "endpoint_404"), pool.account_state("acc_b")
        assert pool.health()["drift_streak"] == drift
        self.c4["day2"] = {"state": list(pool.account_state("acc_b")), "rerun_on": out.label,
                           "restarts": out.restarts, "drift_streak": drift}
        self.record("C4", **self.c4)

    def register_rested(self):
        """C7 (day 2): acc_e registers with a one-day rest; unused while resting; the owner marks it ready."""
        label = "acc_e"
        api = self.lib.API(str(self.private / f"{label}.db"))
        asyncio.run(api.pool.add_account_cookies(label, f"auth_token={AUTH[label]}; ct0={CSRF}"))
        self.set_config(x_accounts=self.labels, x_account_rest_days=1)
        self.start._rebuild(label, self.config)  # the real reader eviction/rebuild used by reconcile
        pool = self.pool()
        assert pool.account_state(label) == ("locked", "resting"), pool.account_state(label)
        out = self.unit(pool, self.coins[4])
        assert out.result is not None and out.label != label, (out.reason, out.label)
        x_pool.write_ready(self.config.x_accounts_db_path, label, self.clock(), labels=self.labels)
        assert pool.account_state(label) == ("locked", "resting")  # ready only from the next UTC day
        assert not [r for r in self.origin.requests if r["label"] == label]
        self.c7 = {"registered_day": str(self.clock().date()), "state_day_registered": "locked/resting",
                   "requests_while_resting": 0, "ready_marked": True}

    def joined(self):
        """C7 (day 3): rest over and ready from an earlier day -> active and part of the day's canary."""
        pool = self.pool()
        assert pool.account_state("acc_e") == ("active", None), pool.account_state("acc_e")
        assert "acc_e" in pool.canary_labels(), pool.canary_labels()
        self.record("C7", **self.c7, state_next_day="active", in_canary=True)

    def harvest(self):
        """C6 (day 3): acc_a's session expires -> x_login_required -> automatic harvest via the spawned fake browser
        through the real host/relay/CDP -> single ct0 -> canary -> reactivated, next real read uses the new cookie."""
        if not cb.WINDOWS:
            raise AssertionError("C6 needs the native job-object host (Windows only)")
        pool = self.pool()
        self.origin.expired.add("acc_a")
        self.prefer(pool, "acc_a", then="acc_e")
        out = self.unit(pool, self.coins[5])
        assert out.result is not None and out.label != "acc_a", (out.reason, out.label)
        assert pool.account_state("acc_a") == ("inactive", "x_login_required"), pool.account_state("acc_a")
        self.admission = cb.admit_by_selftest()
        browsers = self.root / "browser"
        fakes = {"acc_a": cb.FakeBrowser(browsers / "x_in", cookies=cb.x_jar(NEW_AUTH, cb.NEW_CSRF)),
                 "acc_d": cb.FakeBrowser(browsers / "x_out", cookies=cb.x_jar(NEW_AUTH, cb.NEW_CSRF)[1:],
                                         pages=cb.LOGGED_OUT)}
        self.set_config(x_cookie_harvest_enabled=True, browser_path=str(cb.BINARY),
                        browser_profiles_dir=str(browsers / "profiles"),
                        x_account_profiles={x: x for x in self.labels})
        pool = self.pool()
        launches = []
        check = cb.x_check(self.start.runtime, pool, fakes, launches)
        first = self.start.harvest(self.config, pool, self.clock(), check=check)
        assert first == {"acc_a": "ok"}, first
        assert pool.account_state("acc_a") == ("active", None), pool.account_state("acc_a")
        assert not pool.canary_passed_today() or "acc_a" not in pool.canary_labels()
        self.canary(pool)
        assert "acc_a" in pool.canary_labels()
        self.prefer(pool, "acc_a")
        after = self.unit(pool, self.coins[5])
        assert after.result is not None and after.label == "acc_a", (after.reason, after.label)
        renewed = [r for r in self.origin.requests if r["renewed"]]
        assert renewed and all(r["ct0_count"] == 1 for r in renewed)
        second = tr.harvest_account("acc_a", config=self.config, pool=pool, check=check,
                                    upsert=lambda *a, **k: (_ for _ in ()).throw(AssertionError("upsert")))
        assert second == ("failed", "daily_check_used"), second
        due = pool.harvest_due({**tr.cookie_ages(self.config, now=self.clock()), "acc_d": 30}, enabled=True,
                               refresh_age_days=7)
        assert "acc_d" in due, due
        logged_out = tr.harvest_account("acc_d", config=self.set_age(), pool=pool, check=check,
                                        upsert=lambda *a, **k: (_ for _ in ()).throw(AssertionError("upsert")))
        assert logged_out[0] == "needs_owner", logged_out
        assert pool.harvest_due({"acc_d": 30}, enabled=True, refresh_age_days=7) == []
        suspended = tr.harvest_account("acc_c", config=self.config, pool=pool, check=check, upsert=None)
        assert suspended == ("failed", "account_suspended")
        assert pool.account_state("acc_c")[1] == "x_account_suspended"
        assert launches == ["acc_a", "acc_a", "acc_d"], launches
        self.record("C6", login_required=True, harvest="ok", single_ct0=True, canary_after=True,
                    next_read_renewed_cookie=True, second_same_day=second[1], age_trigger_due=["acc_d"],
                    logged_out=f"{logged_out[0]}/{logged_out[1]}", suspended_revived=False,
                    browser="spawned fake over real host/relay/CDP", admission_by_real_selftest=self.admission,
                    logged_out_account_paused=list(pool.account_state("acc_d")))

    B3_OFF = dict(x_quiet_hours_enabled=False, x_mixed_traffic_enabled=False, x_variation_enabled=False,
                  x_adaptive_cooldown_enabled=False, x_warmup_enabled=False)

    def outputs(self):
        """Every non-facts, non-state cache file (coin values, raw pages, rows) with its size and mtime."""
        return {str(p): (p.stat().st_size, p.stat().st_mtime_ns) for p in self.cache.rglob("*")
                if p.is_file() and "_facts" not in p.parts and "_pc_state" not in p.parts}

    def provenance(self):
        rows = [e["switches"] for e in daily_facts.read_events(self.clock().date()) if e["kind"] == "switch_provenance"]
        return [sorted(k for k in x_behaviour_report.MEASURES if row.get(k)) for row in rows]

    def b3(self):
        """C9 (day 3): each B3 measure alone over the real pool/reader, then all together; facts carry the switch
        provenance; the analyzer is run over SEEDED earlier days (7 per arm for warm-up, 3 for mixed traffic)."""
        observed = {}
        quiet_label = "acc_e"
        hour = self.clock().hour
        window = {"timezone": "UTC", "start": f"{hour:02d}:00", "end": f"{(hour + 2) % 24:02d}:00"}
        self.set_config(**{**self.B3_OFF, "x_quiet_hours_enabled": True}, x_account_quiet_hours={quiet_label: window})
        pool = self.pool()
        assert pool.account_state(quiet_label) == ("locked", "quiet_hours"), pool.account_state(quiet_label)
        reason, end = pool.b3_hold(quiet_label)
        self.prefer(pool, quiet_label)
        out = self.unit(pool, self.coins[6])
        assert out.result is not None and out.label != quiet_label, (out.reason, out.label)
        observed["quiet_hours"] = {"deferred": quiet_label != out.label, "hold": reason,
                                   "hold_ends_after_now": end > self.clock()}

        self.set_config(**{**self.B3_OFF, "x_mixed_traffic_enabled": True}, x_mixed_targets=("solana",))
        pool = self.pool()
        before, source = self.outputs(), self.source()
        used = source.used
        op = x_pool.run_mixed(pool, self.start.readers, source, self.config, units_since_last=20, stale=set())
        charged = self.source().used - used
        mixed_requests = [r for r in self.origin.requests if r["path"].endswith("/UserByScreenName")]
        assert op == "user_by_login" and charged >= x_behaviour.MIXED_RESERVE and mixed_requests, (op, charged)
        assert self.outputs() == before  # an ordinary call writes no coin value, raw page or row
        observed["mixed_traffic"] = {"op": op, "charged": charged, "coin_writes": 0}

        self.set_config(**{**self.B3_OFF, "x_variation_enabled": True})
        pool = self.pool()
        out = self.unit(pool, self.coins[7])
        size = x_behaviour.variation(out.label, self.clock().date(), page_cap=20, enabled=True)
        sent = [r.get("count") for r in self.origin.requests if r.get("symbol") == self.coins[7]][-1]
        assert out.result is not None and sent == size.page_size, (out.reason, sent, size)
        assert 1.0 <= size.pause_multiplier <= 1.2
        observed["variation"] = {"page_size": sent, "pause_multiplier_bounded": True}

        self.set_config(**{**self.B3_OFF, "x_adaptive_cooldown_enabled": True})
        pool = self.pool()
        hot = "acc_e"
        self.origin.near_limit.add(hot)
        self.prefer(pool, hot)
        first = self.unit(pool, self.coins[8])
        self.origin.near_limit.clear()
        assert first.label == hot and pool.account_state(hot) == ("locked", "behaviour_cooldown"), \
            (first.label, pool.account_state(hot))
        self.prefer(pool, hot)
        handed = self.unit(pool, self.coins[9])
        assert handed.result is not None and handed.label != hot, (handed.reason, handed.label)
        observed["adaptive_cooldown"] = {"cooled": hot, "next_unit_on_other_account": True}

        self.set_config(**{**self.B3_OFF, "x_warmup_enabled": True})
        pool = self.pool()
        pool.begin_pass()
        cap = pool.effective_cap("acc_e")
        assert cap is not None and cap < self.config.x_account_daily_cap and pool.effective_cap("acc_a") == \
            self.config.x_account_daily_cap, cap
        warm = self.unit(pool, self.coins[11])
        assert warm.result is not None, warm.reason
        observed["warmup"] = {"rested_account_cap": cap, "grandfathered_cap": self.config.x_account_daily_cap,
                              "stage": pool.health()["accounts"][self.labels.index("acc_e")]["behaviour"]
                              ["warmup_stage"]}

        self.set_config(x_quiet_hours_enabled=True, x_mixed_traffic_enabled=True, x_variation_enabled=True,
                        x_adaptive_cooldown_enabled=True, x_warmup_enabled=True)
        pool = self.pool()
        out = self.unit(pool, self.coins[10])
        assert out.result is not None, out.reason
        assert all("behaviour" in a for a in pool.health()["accounts"])
        observed["together"] = {"unit": "stored", "behaviour_status": True}
        self.set_config(**self.B3_OFF)

        arms = self.provenance()
        for measure in x_behaviour_report.MEASURES:
            assert [measure] in arms, (measure, arms)
        assert sorted(x_behaviour_report.MEASURES) in arms
        observed["facts_switch_provenance"] = "each measure alone and all five recorded"
        observed["analyzer"] = self.analyzer()
        self.record("C9", **observed)

    def analyzer(self):
        from api.tests.data.attention import test_x_behaviour_report as seeds
        first = datetime(2026, 10, 1).date()
        for i in range(7):
            seeds._seed_day(first + timedelta(days=i), seeds._sw(), locks=2)
            seeds._seed_day(first + timedelta(days=7 + i), seeds._sw("x_warmup_enabled"))
        for i in range(3):
            seeds._seed_day(first + timedelta(days=14 + i), seeds._sw("x_mixed_traffic_enabled"), mixed_reads=20)
        report = x_behaviour_report.analyze(first, first + timedelta(days=16))
        again = x_behaviour_report.analyze(first, first + timedelta(days=16))
        rows = {r["measure"]: r["decision"] for r in report["rows"]}
        assert report == again
        assert rows["x_warmup_enabled"] in ("keep", "remove") and rows["x_mixed_traffic_enabled"] == "inconclusive"
        return {"seeded_days": {"baseline": 7, "x_warmup_enabled": 7, "x_mixed_traffic_enabled": 3},
                "x_warmup_enabled": rows["x_warmup_enabled"], "x_mixed_traffic_enabled": "inconclusive",
                "deterministic": True}

    def set_age(self):
        self.set_config(x_cookie_refresh_age_days=7)
        return self.config

    def steps(self, nested=False, logs=()):
        """(scenario, action) in cycle order; a scenario that spans several actions is named by its first."""
        before = closing.repo_changes()
        return [("C1", self.baseline), ("C4", self.first_restriction), ("C5", self.suspension),
                ("C7", self.register_rested), ("C3", self.rotation_adopted), ("C3", self.open_day3),
                ("C7", self.joined), ("C4", self.second_restriction), ("C3", self.rotation_inconclusive),
                ("C6", self.harvest), ("C9", self.b3), ("C8", lambda: self.record("C8", **relay.run(self))),
                ("C10", self.reddit_primary), ("C11", lambda: self.reddit.run_c11()),
                ("C12", lambda: closing.c12(self)), ("C13", lambda: closing.c13(self, nested)),
                ("C14", lambda: closing.c14(self, before, list(logs)))]

    def reddit_primary(self):
        self.reddit = reddit.RedditWorld(self)
        self.reddit.run()

    def run(self, nested=False, logs=()):
        for scenario, action in self.steps(nested, logs):
            self.current = scenario
            action()
