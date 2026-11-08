"""C10: the PRIMARY Reddit browser method over the spawned fake browser, three simulated UTC days.

The real `LiveStream` (gate -> poll -> record -> commit), `reddit_browser` method, `RedditRoutes`, `BrowserSessions`,
host, relay and CDP client run unmodified against `browser_fake_main`, whose scripted XHR bodies follow the synthetic
surface proposed by the real `surface_tool` from the S-OpsProbe synthetic captures. Probe records are written through
the real `probe_owner` record writer (synthetic recorded records, as the plan's world specifies).
"""
from __future__ import annotations

import dataclasses
import json
import random
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from api.analytics.attention import daily_report, discovery_history
from api.data import attention_pc_live as live, attention_pc_refresh as apr, cache
from api.data.attention import reddit_accounts as ra
from api.data.attention import reddit_browser as rb
from api.data.attention import reddit_core as rc
from api.data.attention import reddit_gql as rg
from api.data.attention import reddit_items
from api.data.attention import reddit_live as rl
from api.data.attention import reddit_surface as rs
from api.data.attention import store
from api.data.attention.types import SourceSeries
from api.scripts import probe_owner as po
from api.scripts import surface_tool as st
from api.tests.cycle import browser as cb
from api.tests.data.attention import reddit_gql_fake as fk
from api.tests.scripts import reddit_probe_fixtures as fx

HOST = fx.HOST
SUBS = ("bitcoin", "ethereum", "solana", "dogecoin")
ALL = (*SUBS, rc.CANARY_SUBREDDIT)
LABELS = ("rd_a", "rd_b", "rd_c")
SALT = b"CycleSaltCycleSaltCycleSalt01234"
AUTHOR = "rdcycleauthor"
STEP = timedelta(hours=4)
PER_PAGE = 12
SESSION = [{"name": "reddit_session", "value": cb.tbs.MARKER + "r", "expires": cb.tbs.NOW + 20 * cb.tbs.DAY},
           {"name": "loid", "value": cb.tbs.MARKER + "l", "expires": cb.tbs.NOW + 300 * cb.tbs.DAY}]


def key(sub):
    return sub[:2].lower()


def post(sub, created, text):
    n = int(created.timestamp()) // 60
    return {"kind": "t3", "data": {
        "name": f"t3_{key(sub)}{n}p", "id": f"{key(sub)}{n}p", "subreddit": sub, "created_utc": created.timestamp(),
        "author": f"{AUTHOR}{n % 4}", "selftext": f"{fx.SECRET_MARK} {text}", "is_truncated": False,
        "num_comments": 2, "score": 1}}


def thread(p):
    parent, created = p["data"]["name"], p["data"]["created_utc"]
    comments = [{"kind": "t1", "data": {"name": f"t1_c{parent[3:]}{i}", "parent_id": parent,
                                        "subreddit": p["data"]["subreddit"], "created_utc": created + 60 * i,
                                        "author": f"{AUTHOR}c{i}", "body": f"{fx.SECRET_MARK} comment {i}",
                                        "is_truncated": False}} for i in (1, 2)]
    return [{"kind": "Listing", "data": {"after": None, "children": [p]}},
            {"kind": "Listing", "data": {"after": None, "children": [
                *comments, {"kind": "more", "data": {"count": 4, "children": ["abc"]}}]}}]


class RedditWorld:
    def __init__(self, world):
        self.w = world
        q = world.queries
        terms = [s for s in world.coins if s not in q.ambiguous["reddit_web"]]
        self.mentioned = dict(zip(ALL, terms[:5]))
        self.z1, self.z2 = terms[5], terms[6]
        self.names = {s: q.coins[s]["name"] for s in terms}
        self.posts = {}  # (sub, name) -> post, every post ever listed (thread pages are served for all of them)

    # --- synthetic surface, records, pages ---------------------------------------------------------------------
    def surface(self):
        p = st.propose("browser", fx.bootstrap_captures(SUBS), subreddits=SUBS)
        assert p.ok, p.reasons
        raw = {**p.section, "sha256": rs.section_sha256(p.section)}
        path = self.w.root / "private" / "surface.json"
        path.write_text(json.dumps({"sections": {"browser": raw}}), encoding="utf-8")
        self.section = rs.load_section("browser", raw)
        return path

    def record(self, mode, *, section="browser", sha=None):
        day = self.w.clock().date()
        po.write_record(cache.CACHE_ROOT, po.make_record(
            probe_id="PR2" if section == "browser" else "PR1", mode=mode, date_utc=day.isoformat(),
            commit="a" * 40, egress_class="direct", outcome="pass", section=section,
            section_sha256=sha or self.section.sha256, surface_revision=self.section.revision,
            counts=dict.fromkeys(po.COUNTS, 0), reason_codes=[], limits_hit=[]))

    def listing_pages(self, now, oldest, blocked=()):
        pages = {}
        top = now.replace(minute=5, second=0, microsecond=0)
        top -= timedelta(hours=top.hour % 4)
        for sub in ALL:
            created, docs = top, []
            while created >= oldest - STEP:
                text = f"{self.names[self.mentioned[sub]]} discussion"
                p = post(sub, created, text)
                self.posts[(sub, p["data"]["name"])] = p
                docs.append(p)
                created -= STEP
            chunks = [docs[i:i + PER_PAGE] for i in range(0, len(docs), PER_PAGE)]
            caps, url = [], f"{HOST}/svc/r/{sub}/new.json?limit=12"
            for i, chunk in enumerate(chunks):
                after = chunk[-1]["data"]["name"] if i + 1 < len(chunks) else None
                body = {"kind": "Listing", "data": {"after": after, "dist": len(chunk), "children": chunk}}
                if sub in blocked:
                    caps.append({"url": f"{HOST}/blocked", "body": json.dumps({"blocked": True})})
                else:
                    caps.append({"url": url, "body": json.dumps(body)})
                url = f"{HOST}/svc/r/{sub}/new.json?limit=12&after={after}"
            pages[rb.listing_url(sub)] = {"body": "{}", "xhr": caps[:1], "scrolls": [[c] for c in caps[1:]]}
        for (sub, name), p in self.posts.items():
            pages[rb.thread_url(sub, name)] = {"body": "{}", "xhr": [
                {"url": f"{HOST}/svc/r/{sub}/comments/{name[3:]}.json", "body": json.dumps(thread(p))}]}
        return pages

    def script(self, now, *, blocked=()):
        floor = datetime.combine(now.date() - timedelta(days=1), datetime.min.time(), tzinfo=UTC)
        self.fake.write(cookies=SESSION, pages=self.listing_pages(now, floor, blocked))

    # --- method / stream ---------------------------------------------------------------------------------------
    def configure(self, surface):
        self.w.set_config(reddit_live_methods=("browser",), reddit_surface_path=str(surface),
                          reddit_stream_subreddits=SUBS, reddit_live_probe_max_age_days=7,
                          reddit_browser_accounts=tuple({"label": x, "profile": x} for x in LABELS),
                          reddit_browser_account_rest_days=0, reddit_browser_account_daily_cap=200,
                          reddit_browser_daily_minutes=90, reddit_browser_daily_navigation_cap=400,
                          reddit_live_polls_per_day=24, reddit_live_threads_per_poll=100,
                          reddit_live_canary_min_items=1, browser_path=str(cb.BINARY),
                          browser_profiles_dir=str(self.fake.root / "profiles"))

    def method(self, cfg=None):
        cfg = cfg or self.w.config
        routes = rb.RedditRoutes(cfg, wall=self.w.clock)
        sessions = rb.BrowserSessions(cfg, host=self.fake.host, routes=routes, sleep=lambda s: None,
                                      wall=lambda: self.w.clock().timestamp())
        deps = SimpleNamespace(clock=self.w.clock, reddit_routes=routes, reddit_sessions=sessions,
                               hasher=reddit_items.AuthorHasher(SALT), queries=lambda: self.w.queries)
        return rb.make_method(cfg, deps)

    def stream(self):
        self.live = live.LiveStream(self.w.worker, rb.STORE, random.Random(19), self.method())
        return self.live

    def at(self, day, hour, minute=0):
        target = datetime.combine(day, datetime.min.time(), tzinfo=UTC) + timedelta(hours=hour, minutes=minute)
        assert target >= self.w.clock()
        self.w.clock.sleep((target - self.w.clock()).total_seconds())

    def seed_history(self, day):
        for sym, n in ((self.z1, 7), (self.z2, 3)):
            pts = [(day - timedelta(days=2 + i), 4.0) for i in range(n)]
            store.write_series(SourceSeries(rb.STORE, sym, pts, "ok", ""), today=day)

    def pool(self):
        return self.live.method.routes.refresh()

    # --- C10 ---------------------------------------------------------------------------------------------------
    def run(self):
        w, observed = self.w, {}
        self.fake = cb.FakeBrowser(w.root / "reddit_browser")
        surface = self.surface()
        self.configure(surface)
        for x in LABELS[:2]:
            ra.write_ready(x, w.clock() - timedelta(days=1), labels=LABELS)
        d1 = w.clock().date()
        self.seed_history(d1)
        stream = self.stream()
        launches = len(self.fake.launches)
        assert stream.run_pass() == "needs_probe"
        self.record("bootstrap")
        assert stream.run_pass() == "needs_probe" and len(self.fake.launches) == launches
        observed["gate"] = {"no_record": "needs_probe", "bootstrap_only": "needs_probe", "reads": 0}
        self.record("verify")
        bad = dataclasses.replace(w.config, reddit_surface_path=str(self.html_surface()))
        assert self.method(bad).gate_state(w.clock()) == "unsupported_format"
        observed["unsupported_format"] = "gate stops with unsupported_format, nothing read"

        self.at(d1, 23)
        self.script(w.clock())
        assert stream.run_pass() == "polled", (stream.method.gate_state(w.clock()), [
            (x, self.pool().account_state(x)) for x in LABELS], ra.read_ready())
        first = stream.method.last_account
        pool = self.pool()
        lanes = rl.read_lanes(rb.STORE, d1 - timedelta(days=1), d1)
        assert first == "rd_a" and pool.account_state("rd_c")[0] != "active", (first, stream.method._refusal,
            stream.method._busy_until, [(x, pool.account_state(x), pool._acct(x)) for x in LABELS], [
            (lane.subreddit, lane.kind, lane.stop_reason, lane.items_seen) for lane in lanes])

        d2 = d1 + timedelta(days=1)
        self.at(d2, 0, 30)
        self.script(w.clock())
        assert stream.run_pass() == "polled"
        assert stream.method.last_account == "rd_b"
        doc = rl.read_completeness(rb.STORE, d1)
        assert doc and doc["settled"], doc and {k: doc[k] for k in ("posts_coverage", "comments_coverage", "canary_ok")}
        coins = doc["coins"]
        stored = [s for s in self.mentioned.values() if coins[s]["reason"] == "fetched"]
        assert stored and coins[self.z1]["reason"] == "fetched" and coins[self.z1]["value"] == 0.0, coins[self.z1]
        assert coins[self.z2]["reason"] == "zero_unverified", coins[self.z2]
        first_value = dict(store.read_points(rb.STORE, stored[0]))[d1]
        extra = rc.LiveItem("t3_zzlate", "post", "bitcoin", datetime.combine(d1, datetime.min.time(), tzinfo=UTC)
                            + timedelta(hours=12), reddit_items.AuthorHasher(SALT)("late"), (stored[0],))
        rc.add_items(rb.STORE, [extra])
        rl.commit_day(rb.STORE, d1, w.queries, now=w.clock(), subreddits=SUBS)
        assert dict(store.read_points(rb.STORE, stored[0]))[d1] == first_value
        observed["day1"] = {"settled": True, "accounts": [first, "rd_b"], "one_account_per_poll": True,
                            "fetched": len(stored), "z1": "true zero stored (7 positive days)",
                            "z2": "zero_unverified (3 positive days)", "first_write_wins": True,
                            "rd_c": "/".join(str(v) for v in pool.account_state("rd_c"))}

        self.at(d2, 23)
        self.script(w.clock(), blocked=("ethereum",))
        jar = self.fake.jar("rd_a")
        saved = jar.read_text()
        jar.write_text(json.dumps([c for c in json.loads(saved) if c["name"] != "reddit_session"]))
        w.set_config(reddit_browser_account_daily_cap=self.pool().reads_today("rd_b") + 3)
        stream = self.stream()
        assert stream.run_pass() == "polled"
        pool = self.pool()
        assert pool.account_state("rd_a") == ("paused", "reddit_login_required"), pool.account_state("rd_a")
        assert stream.method.last_account == "rd_b"
        stops = {(lane.subreddit, lane.kind): lane.stop_reason for lane in rl.read_lanes(rb.STORE, d2, d2)
                 if lane.poll_id == w.clock().isoformat()}
        assert "cap" in stops.values(), stops
        observed["login_wall"] = {"rd_a": "paused/reddit_login_required", "retried_once_on": "rd_b",
                                  "needs_owner": "owner relogin required (reddit_login_required)"}
        observed["caps"] = {"rd_b_capped_lanes": sorted({k[0] for k, v in stops.items() if v == "cap"})}
        jar.write_text(saved)
        pool.record_session("rd_a", "logged_in")  # what the owner's `browser_session --interactive` records
        assert pool.account_state("rd_a") == ("active", None)
        observed["owner_relogin"] = "rd_a active again"

        d3 = d2 + timedelta(days=1)
        self.at(d3, 0, 30)
        w.set_config(reddit_browser_account_daily_cap=200)
        self.script(w.clock(), blocked=("ethereum",))
        stream = self.stream()
        assert stream.run_pass() == "polled"
        lanes = [lane for lane in rl.read_lanes(rb.STORE, d2, d3) if lane.poll_id == w.clock().isoformat()]
        assert {lane.stop_reason for lane in lanes if lane.subreddit == "ethereum" and lane.kind == "posts"} == {
            "empty_shell"}, (
            stream.method.last_account, [(lane.subreddit, lane.kind, lane.stop_reason, lane.poll_id) for lane in
                                         rl.read_lanes(rb.STORE, d2, d3)][-12:], w.clock().isoformat())
        doc2 = rl.read_completeness(rb.STORE, d2)
        assert doc2 and not doc2["settled"] and set(doc2["missing"]) <= {"lane_incomplete", "ambiguous"}, doc2 and (
            doc2["missing"], doc2["settled"])
        assert doc2["fetched"] == 0 and all(v["value"] is None for v in doc2["coins"].values())
        observed["day2"] = {"block_page": "empty_shell (error, not zero)", "commit": "lane_incomplete missing",
                            "values_written": 0}
        self.report_rev1 = daily_report.rebuild(d2, now=w.clock())  # C12: the report as of the first commit
        self.at(d3, 23)
        self.script(w.clock())
        assert stream.run_pass() == "polled"
        self.report_rev2 = daily_report.rebuild(d2, now=w.clock())  # C12: late Reddit evidence for D2
        observed["day3"] = {"poll": stream.method.last_account, "accounts_in_operation": 1}
        self.d1, self.d2 = d1, d2
        observed["secrets"] = self.no_text()
        observed["not_exercised"] = [
            "routes are the all-null direct configuration: per-account proxy routes for rd_* are not admitted "
            "inside this scenario (C8 covers B2 admission/quarantine and the relay proxy mode)",
            "comment threads have fixed comment counts (growth-triggered re-opens are unit-tested only)",
            "canary minimum lowered to 1 item and polls_per_day 24 for the synthetic 4-hour post cadence"]
        w.record("C10", **observed)

    def html_surface(self):
        raw = json.loads((self.w.root / "private" / "surface.json").read_text())["sections"]["browser"]
        raw = {**raw, "body_format": "html"}
        path = self.w.root / "private" / "surface_html.json"
        path.write_text(json.dumps({"sections": {"browser": raw}}), encoding="utf-8")
        return path

    def no_text(self):
        planted = [fx.SECRET_MARK, AUTHOR, cb.tbs.MARKER]
        hits = [p.name for p in cache.CACHE_ROOT.rglob("*") if p.is_file()
                and any(s.encode() in p.read_bytes() for s in planted)]
        assert hits == [], hits
        return "no post text, username or session cookie in any cache file"

    # --- C11 ---------------------------------------------------------------------------------------------------
    def gql_surface(self, revision=1):
        doc = json.loads((self.w.root / "private" / "surface.json").read_text())
        raw = fk.section_raw(revision=revision)
        doc["sections"]["gql_anon"] = {**raw, "sha256": rs.section_sha256(raw)}
        if revision != 1:  # a republished surface: both sections change, every verify record stops matching
            browser = {k: v for k, v in doc["sections"]["browser"].items() if k != "sha256"}
            browser["revision"] += 1
            doc["sections"]["browser"] = {**browser, "sha256": rs.section_sha256(browser)}
        path = self.w.root / "private" / f"surface_gql{revision}.json"
        path.write_text(json.dumps(doc), encoding="utf-8")
        return path, rs.load_section("gql_anon", doc["sections"]["gql_anon"])

    def gql_record(self, section, day):
        po.write_record(cache.CACHE_ROOT, po.make_record(
            probe_id="PR1", mode="verify", date_utc=day.isoformat(), commit="a" * 40, egress_class="direct",
            outcome="pass", section="gql_anon", section_sha256=section.sha256, surface_revision=section.revision,
            counts=dict.fromkeys(po.COUNTS, 0), reason_codes=[], limits_hit=[]))

    def gql_stream(self):
        deps = SimpleNamespace(clock=self.w.clock, hasher=reddit_items.AuthorHasher(SALT),
                               queries=lambda: self.w.queries)
        method = rg.make_method(self.w.config, deps)  # the production transport over the loopback TLS origin
        return live.LiveStream(self.w.worker, rg.STORE, random.Random(19), method)

    def gql_world(self, now):
        g = self.w.origin.gql
        g.now = now
        base = now - timedelta(hours=30)
        g.posts = [(f"t3_g{i}", sub, base + timedelta(hours=i), f"{AUTHOR}g{i % 3}",
                    f"{self.names[self.mentioned[sub]]} {fx.SECRET_MARK}", "body")
                   for i in range(30) for sub in ("solana", rc.CANARY_SUBREDDIT)]
        g.comments = []

    def run_c11(self):
        w, observed = self.w, {}
        d4 = self.d1 + timedelta(days=3)
        self.at(d4, 1)
        feed = w.worker.streams.get(apr.REDDIT_SOURCE)
        if feed is not None:
            before = len(w.origin.requests)
            outcome = feed.run_pass(stop_at=w.clock() + timedelta(hours=6))
            rss = [r for r in w.origin.requests[before:] if r["path"].endswith(".rss")]
            assert rss and all(r["at"] >= "2026-11-13" for r in rss), (outcome, len(rss))
            late = [(s, d, v) for s in w.coins for d, v in store.read_points(apr.REDDIT_SOURCE, s)
                    if d >= datetime(2026, 11, 13).date()]
            assert late == [], late
            observed["feeds"] = {"outcome": outcome, "rss_requests_blocked": len(rss), "values_or_zeros_after": 0}
        else:
            observed["feeds"] = "feed stream not configured on this PC (pc_sources): not exercised"

        stale_path, section = self.gql_surface()
        w.set_config(reddit_live_methods=("browser", "gql_anon"), reddit_surface_path=str(stale_path),
                     reddit_live_gql_daily_request_cap=600)
        gql = self.gql_stream()
        assert gql.method.gate_state(w.clock()) == "needs_probe"
        self.gql_record(section, w.clock().date() - timedelta(days=9))
        assert gql.method.gate_state(w.clock()) == "needs_probe"
        moved, _ = self.gql_surface(revision=2)
        w.set_config(reddit_surface_path=str(moved))
        self.gql_record(section, w.clock().date())
        assert self.gql_stream().method.gate_state(w.clock()) == "needs_probe"  # hash/revision mismatch
        observed["gql_refusals"] = {"no_record": "needs_probe", "stale": "needs_probe", "hash_mismatch": "needs_probe"}

        refused_day = w.clock().date()
        browser = self.stream()
        assert browser.method.gate_state(w.clock()) == "needs_probe" and self.gql_stream().run_pass() == "needs_probe"
        assert browser.run_pass() == "needs_probe"
        for st_ in (rb.STORE, rg.STORE):
            assert rl.read_completeness(st_, refused_day) is None
            assert not [d for sym in w.coins for d, _ in store.read_points(st_, sym) if d == refused_day]
        observed["all_live_refused"] = "no live value or zero for the day (missing, not zero)"

        w.set_config(reddit_surface_path=str(stale_path))
        self.gql_record(section, w.clock().date())
        gql = self.gql_stream()
        browser_points = {s: store.read_points(rb.STORE, s) for s in w.coins}
        self.gql_world(w.clock())
        assert gql.run_pass() == "polled", gql.method.gate_state(w.clock())
        self.at(d4 + timedelta(days=1), 0, 30)
        self.gql_world(w.clock())
        assert gql.run_pass() == "polled"
        doc = rl.read_completeness(rg.STORE, d4)
        assert doc and doc["method"] == "reddit_live_gql_v1", doc
        assert {s: store.read_points(rb.STORE, s) for s in w.coins} == browser_points  # never merged
        assert [r for r in w.origin.requests if r["host"] == "gql-fed.reddit.com"]
        observed["gql"] = {"method": doc["method"], "settled": doc["settled"], "fetched": doc["fetched"],
                           "browser_store_untouched": True, "over_loopback_tls": True}

        observed["selection"] = self.selection(datetime(2026, 11, 12).date())  # a window the feeds still served
        observed["not_exercised"] = [
            "selection is checked through daily_report.selected_methods (the real pick_source_impl over the real "
            "discovery_history series), not a full build_discovery run"]
        w.record("C11", **observed)

    def selection(self, day):
        live_coin, feed_coin = self.w.coins[12], self.w.coins[13]
        for source, sym in ((rb.STORE, live_coin), (apr.REDDIT_SOURCE, feed_coin)):
            pts = [(day - timedelta(days=130 - i), 1.0 + 0.02 * i) for i in range(130)]
            path = store.store_path(source, sym)
            if path.exists():
                path.unlink()
            store.write_series(SourceSeries(source, sym, pts, "ok", ""), today=day)
        discovery_history.clear_cache()
        probes = self.w.root / "private" / "probe_records.json"  # the feed's recorded probe admission (synthetic)
        probes.write_text(json.dumps({apr.REDDIT_SOURCE: {"verdict": "synthetic"}}), encoding="utf-8")
        got = daily_report.selected_methods(day, {"reddit": [live_coin, feed_coin]}, probe_path=probes)["reddit"]
        assert got == {live_coin: rb.STORE, feed_coin: apr.REDDIT_SOURCE}, got
        return {"live_seeded_coin": rb.STORE, "feed_only_coin": apr.REDDIT_SOURCE, "mixed": False}
