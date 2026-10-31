"""W8d2 AC41, AC46, AC47, AC49-AC55: the twscrape wrapper behind the W8d1 `XReader`.

A FAKE `twscrape` module is injected into `sys.modules` (the real library is not installed in CI); no network,
no subprocess (the curl fallback child is an injected callable), fake file systems through `tmp_path` and injected
stat results. Injected clock.
"""
from __future__ import annotations

import json
import os
import random
import stat
import sys
import types
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from api.data import cache
from api.data.attention import pc_pace as pp
from api.data.attention import twscrape_reader as tr
from api.data.attention import web_queries as wq
from api.data.attention import x_filters as xf
from api.data.attention import x_pool as xp
from api.data.attention import x_reader as xr
from api.scripts import probe_pc_sources as probe

PIN = xr.TWSCRAPE_PINNED_COMMIT
T0 = datetime(2026, 10, 27, 10, 0, tzinfo=UTC)
DAY = date(2026, 10, 26)
SECRET = "auth_token=PLANTEDc00k1e; ct0=PLANTEDcsrf"
GOOD_ENV = {"TWS_TELEMETRY": "0", "DO_NOT_TRACK": "1", "TWS_LOG_LEVEL": "WARNING", "TWS_RAISE_WHEN_NO_ACCOUNT": "1"}
QUERY = '("$SOL" OR "Solana") lang:en -filter:replies -filter:retweets since_time:1761436800 until_time:1761523200'


@pytest.fixture(autouse=True)
def _isolated(attention_cache):
    return attention_cache


# --- the fake library ---------------------------------------------------------------------------------------------

class NoAccountError(Exception):
    pass


class AbortReqError(Exception):
    pass


class GqlFeaturesOutdatedError(AbortReqError):
    pass


class ApiError(AbortReqError):
    def __init__(self, msg, errors=None):
        super().__init__(msg)
        self.errors = errors or []


class XClIdParseError(Exception):
    pass


class FakeResponse:
    def __init__(self, body, headers=None):
        self._body, self.headers = body, dict(headers or {})

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


def snowflake(ts: datetime, seq: int = 0) -> int:
    return ((int(ts.timestamp() * 1000) - 1288834974657) << 22) + seq


def lib_tweet(tid: int, *, cashtags=("SOL",), views=100, rt=None, reply=None, image="https://img/p.jpg"):
    user = types.SimpleNamespace(id=tid % 997 + 1, created=datetime(2020, 1, 1, tzinfo=UTC),
                                 followersCount=50, statusesCount=500, profileImageUrl=image, protected=False)
    date_ = datetime.fromtimestamp(((tid >> 22) + 1288834974657) / 1000, tz=UTC)
    return types.SimpleNamespace(id=tid, date=date_, rawContent=f"Solana up {tid}", user=user, lang="en",
                                 cashtags=list(cashtags), retweetedTweet=rt, inReplyToTweetId=reply, likeCount=3,
                                 replyCount=1, quoteCount=0, retweetCount=2, viewCount=views)


def page_body(ids, *, cursor="CURSOR-NEXT"):
    entries = [{"entryId": f"tweet-{i}", "content": {"tweet_id": i}} for i in ids]
    if cursor:
        entries.append({"entryId": "cursor-bottom-1", "content": {"cursorType": "Bottom", "value": cursor}})
    return {"data": {"search_by_raw_query": {"search_timeline": {"timeline": {"instructions": [
        {"type": "TimelineAddEntries", "entries": entries}]}}}}}


class FakePool:
    def __init__(self, lib, db):
        self.lib, self.db = lib, db

    async def add_account_cookies(self, username, cookies):
        self.lib.calls.append(("add_account_cookies", self.db, username))
        Path(self.db).write_text("accounts", encoding="utf-8")

    async def get(self, username):
        self.lib.calls.append(("get", self.db, username))
        row = self.lib.rows.get(username)
        if row is None:
            raise ValueError(f"Account {username} not found")
        return row


class FakeAPI:
    def __init__(self, lib, pool=None, debug=False, proxy=None, raise_when_no_account=False, wait_timeout=None):
        self.lib = lib
        lib.apis.append({"db": pool, "debug": debug, "proxy": proxy, "raise_when_no_account": raise_when_no_account,
                         "wait_timeout": wait_timeout})
        self.pool = FakePool(lib, pool)
        self.db = pool

    async def search_raw(self, q, limit=-1, kv=None):
        self.lib.calls.append(("search_raw", self.db, q, limit, dict(kv or {})))
        script = self.lib.scripts.setdefault(self.db, [])
        while script:
            item = script.pop(0)
            if isinstance(item, BaseException):
                raise item
            yield item


def make_lib():
    lib = types.ModuleType("twscrape")
    lib.calls, lib.apis, lib.rows, lib.scripts, lib.tweets = [], [], {}, {}, {}
    lib.API = lambda pool=None, **kw: FakeAPI(lib, pool, **kw)
    lib.NoAccountError, lib.AbortReqError, lib.ApiError = NoAccountError, AbortReqError, ApiError
    lib.GqlFeaturesOutdatedError, lib.XClIdParseError = GqlFeaturesOutdatedError, XClIdParseError
    models = types.ModuleType("twscrape.models")

    def parse_tweets(rep, limit=-1):
        body = rep if isinstance(rep, dict) else rep.json()
        ids = [e["content"]["tweet_id"] for e in
               body["data"]["search_by_raw_query"]["search_timeline"]["timeline"]["instructions"][0]["entries"]
               if e["entryId"].startswith("tweet-")]
        for i in ids:
            if i in lib.tweets:
                yield lib.tweets[i]
            elif i not in lib.dropped:
                yield lib_tweet(i)

    lib.dropped = set()
    models.parse_tweets = parse_tweets
    lib.models = models
    return lib


@pytest.fixture
def lib(monkeypatch):
    fake = make_lib()
    monkeypatch.setitem(sys.modules, "twscrape", fake)
    monkeypatch.setitem(sys.modules, "twscrape.models", fake.models)
    return fake


def dist(commit=PIN, version="0.20.1", name="twscrape", url="https://github.com/vladkens/twscrape"):
    direct = json.dumps({"url": url, "vcs_info": {"vcs": "git", "commit_id": commit, "requested_revision": commit}})
    return tr.DistInfo(name=name, version=version, direct_url=direct, wheel=None)


def curl_dist(tag="cp310-abi3-manylinux2014_x86_64", version="0.16.3", name="curl_cffi"):
    return tr.DistInfo(name=name, version=version, direct_url=None,
                       wheel=f"Wheel-Version: 1.0\nRoot-Is-Purelib: false\nTag: cp310-abi3-manylinux_2_17_x86_64\nTag: {tag}\n")


def lookup(tw=None, curl=None):
    found = {"twscrape": tw if tw is not None else dist(), "curl_cffi": curl}
    return lambda name: found.get(name)


def accounts(tmp_path: Path, labels=("acct1", "acct2")) -> Path:
    d = tmp_path / "xpool"
    d.mkdir(mode=0o700, parents=True)
    os.chmod(d, 0o700)
    for label in labels:
        f = d / f"{label}.db"
        f.write_text("accounts", encoding="utf-8")
        os.chmod(f, 0o600)
    return d


def cfg(accounts_dir: Path | str = "", labels=("acct1", "acct2"), **over) -> wq.CollectorConfig:
    base = {**wq.load().config.as_dict(), "x_accounts_db_path": str(accounts_dir), "x_accounts": tuple(labels)}
    return wq.CollectorConfig(**{**base, **over})


def start(tmp_path, lib_, *, env=None, config=None, dist_lookup=None, platform="manylinux_x86_64", **kw):
    d = accounts(tmp_path)
    config = config or cfg(d)
    return tr.start(config, env=GOOD_ENV if env is None else env, repo_root=tmp_path / "repo",
                    dist_lookup=dist_lookup or lookup(), load=tr.load_library, platform=platform,
                    dump_roots=[tmp_path / "tmp"], **kw), d


def row(active=True, error=None, locks=None, last_used=None):
    return types.SimpleNamespace(active=active, error_msg=error, locks=locks or {}, last_used=last_used)


class Clock:
    def __init__(self, now=T0):
        self.now = now

    def __call__(self):
        return self.now


# --- AC41: install, pin, raising switches -------------------------------------------------------------------------

def test_installed_commit_id_must_equal_pinned_sha_and_version_string_is_not_a_guard(tmp_path, lib):
    assert tr.identity_problem(dist(), PIN) is None
    # The version string matches but the commit does not: refused.
    assert tr.identity_problem(dist(commit="0" * 40), PIN) == "commit_mismatch"
    assert tr.identity_problem(dist(commit=PIN[:7]), PIN) == "commit_mismatch"
    # A different version string with the pinned commit is accepted: the version is a label only.
    assert tr.identity_problem(dist(version="9.9.9"), PIN) is None
    no_direct = tr.DistInfo(name="twscrape", version="0.20.1", direct_url=None, wheel=None)
    assert tr.identity_problem(no_direct, PIN) == "commit_mismatch"
    assert tr.identity_problem(dist(url="https://github.com/someone/twscrape"), PIN) == "commit_mismatch"
    assert tr.identity_problem(None, PIN) == "not_installed"
    with pytest.raises(tr.XStartRefused) as e:
        start(tmp_path, lib, dist_lookup=lookup(tw=dist(commit="1" * 40)))
    assert e.value.reasons == ["commit_mismatch"]
    # A config edit alone never moves the pin: the configured commit must equal the code's pin.
    with pytest.raises(tr.XStartRefused) as e:
        start(tmp_path / "b", lib, config=cfg(accounts(tmp_path / "c"), x_pinned_commit="1" * 40))
    assert e.value.reasons == ["pin_mismatch"]
    assert lib.apis == []


def test_reader_options_wait_timeout_zero_raise_when_no_account_true_and_env_switch(tmp_path, lib):
    s, _ = start(tmp_path, lib)
    assert [a["raise_when_no_account"] for a in lib.apis] == [True, True]
    assert [a["wait_timeout"] for a in lib.apis] == [0, 0]
    env = dict(GOOD_ENV)
    del env["TWS_RAISE_WHEN_NO_ACCOUNT"]
    with pytest.raises(tr.XStartRefused) as e:
        start(tmp_path / "b", lib, env=env)
    assert e.value.reasons == ["env:TWS_RAISE_WHEN_NO_ACCOUNT"]
    assert tr.service_env({}, private_tmp=tmp_path)["TWS_RAISE_WHEN_NO_ACCOUNT"] == "1"
    s.close()


def test_one_sqlite_file_and_one_api_per_account(tmp_path, lib):
    s, d = start(tmp_path, lib)
    assert sorted(s.readers) == ["acct1", "acct2"]
    assert [a["db"] for a in lib.apis] == [str(d / "acct1.db"), str(d / "acct2.db")]
    assert all(Path(a["db"]).is_absolute() for a in lib.apis)
    assert len({id(r._api) for r in s.readers.values()}) == 2
    assert all(isinstance(r, xr.XReader) for r in s.readers.values())
    s.close()


def test_telemetry_env_set_to_zero(tmp_path):
    env = tr.service_env({"PATH": "/bin", "TWS_TELEMETRY": "1"}, private_tmp=tmp_path)
    assert env["TWS_TELEMETRY"] == "0" and env["DO_NOT_TRACK"] == "1" and env["TWS_LOG_LEVEL"] == "WARNING"
    assert env["PATH"] == "/bin" and env["TMPDIR"] == str(tmp_path)
    assert tr.env_guard(env) == []


def test_env_guard_refuses_start_for_each_wrong_variable(tmp_path, lib, monkeypatch):
    monkeypatch.setattr(tr, "_LOADED", {})
    wrong = [("TWS_TELEMETRY", "1"), ("DO_NOT_TRACK", "0"), ("TWS_LOG_LEVEL", "DEBUG"), ("TWS_LOG_LEVEL", "INFO"),
             ("TWS_RAISE_WHEN_NO_ACCOUNT", "0"), ("TWS_PROXY", "socks5://h"), ("HTTP_PROXY", "http://h"),
             ("HTTPS_PROXY", "http://h"), ("https_proxy", "http://h"), ("ALL_PROXY", "http://h"),
             ("TWS_HTTP_BACKEND", "curl"), ("TWS_HTTP_BACKEND", "httpx")]
    for i, (name, value) in enumerate(wrong):
        with pytest.raises(tr.XStartRefused) as e:
            start(tmp_path / str(i), lib, env={**GOOD_ENV, name: value})
        assert e.value.reasons == [f"env:{name}"], name
        assert value not in str(e.value)
    assert lib.apis == [] and "twscrape" not in tr._LOADED
    # The fallback process needs the curl backend and nothing else.
    assert tr.env_guard({**GOOD_ENV, "TWS_HTTP_BACKEND": "curl"}, fallback=True) == []
    assert tr.env_guard(GOOD_ENV, fallback=True) == ["TWS_HTTP_BACKEND"]
    child = tr.service_env({"HTTPS_PROXY": "http://h", "TWS_HTTP_BACKEND": "httpx"}, private_tmp=tmp_path,
                           fallback=True)
    assert child["TWS_HTTP_BACKEND"] == "curl" and "HTTPS_PROXY" not in child


def test_private_tmpdir_and_twscrape_dump_cleaner(tmp_path, lib):
    root = tmp_path / "tmp"
    (root / "twscrape").mkdir(parents=True)
    (root / "twscrape" / "twscrape_parse_error_1.txt").write_text("raw tweet json", encoding="utf-8")
    (root / "twscrape-1761500000").mkdir()
    (root / "twscrape-1761500000" / "dump.txt").write_text("headers", encoding="utf-8")
    (root / "other.txt").write_text("keep", encoding="utf-8")
    assert tr.clean_dumps([root, tmp_path / "absent"]) == 2
    assert sorted(p.name for p in root.iterdir()) == ["other.txt"]
    (root / "twscrape").mkdir()
    s, _ = start(tmp_path, lib)
    assert not (root / "twscrape").exists()  # start cleans
    s.close()
    assert tr.service_env({}, private_tmp=tmp_path / "priv")["TMP"] == str(tmp_path / "priv")


def test_wrapper_refuses_proxy_and_ua_override_and_curl_unless_flag_and_block(tmp_path, lib):
    s, _ = start(tmp_path, lib)
    assert all(a["proxy"] is None and a["debug"] is False for a in lib.apis)
    for kw in ({"proxy": "http://h"}, {"user_agent": "Mozilla"}, {"debug": True}):
        with pytest.raises(TypeError):
            tr.TwscrapeReader("acct1", tmp_path / "x.db", tr.load_library(), max_entries=60, **kw)
    assert s.fallback is None and "curl_fallback_off:flag_false" in s.notes
    with pytest.raises(tr.XStartRefused):
        start(tmp_path / "b", lib, env={**GOOD_ENV, "TWS_HTTP_BACKEND": "curl"})
    s.close()


def test_curl_backend_off_by_default_flag_false(tmp_path, lib):
    assert wq.X_DEFAULTS["x_allow_curl_backend"] is False
    assert wq.load().config.x_allow_curl_backend is False
    s, _ = start(tmp_path, lib, curl_record=tr.install_record("manylinux_x86_64", tr.lock_text()),
                 dist_lookup=lookup(curl=curl_dist()))
    assert s.fallback is None and s.curl_status == "flag_false"
    s.close()


def test_no_ua_override_or_proxy_with_curl(tmp_path):
    env = tr.service_env({"HTTP_PROXY": "http://h", "TWS_PROXY": "x", "http_proxy": "y", "USER_AGENT": "Mozilla/5"},
                         private_tmp=tmp_path, fallback=True)
    assert not set(env) & set(xr.PROXY_VARS)
    assert env["TWS_HTTP_BACKEND"] == "curl"
    req = tr.fallback_request("acct1", Path("/srv/x/acct1.db"), QUERY, {"product": "Latest"}, cursor=None)
    assert set(req) == {"label", "db", "query", "kv"} and set(req["kv"]) == {"product"}
    with pytest.raises(ValueError):
        tr.fallback_request("acct1", Path("/srv/x/acct1.db"), QUERY, {"product": "Latest", "proxy": "h"}, cursor=None)


# --- AC46: exceptions to reasons ----------------------------------------------------------------------------------

def test_api_error_abort_req_no_account_mapped_to_reasons(lib):
    lib_ = tr.load_library()
    cases = [(NoAccountError("No account available for queue SearchTimeline"), "no_account", None),
             (ApiError("(88) Rate limit exceeded"), "api", None),
             (GqlFeaturesOutdatedError("Update GQL_FEATURES"), "gql_outdated", None),
             (XClIdParseError("X web scripts not found"), "xclid_parse", None),
             (AbortReqError("Failed to get XClIdGen. See: issue"), "not_found", None),
             (AbortReqError("Blocked by Cloudflare: 403 - abc"), "abort", "cloudflare"),
             (AbortReqError("Blocked by HTML: 429 - abc"), "abort", "html"),
             (AbortReqError("something else"), "abort", "other"),
             (RuntimeError("transport " + SECRET), "api", None)]
    for exc, kind, abort in cases:
        f = tr.map_exception(exc, lib_)
        assert (f.kind, f.abort) == (kind, abort), exc
        assert SECRET not in str(f) and "Cloudflare:" not in str(f)
    assert tr.map_exception(AbortReqError("Blocked by Cloudflare: 403 - r"), lib_).status == 403


def test_noaccounterror_cause_read_from_pool_row_inactive_locked_active_error(tmp_path, lib):
    s, _ = start(tmp_path, lib)
    r = s.readers["acct1"]
    later = T0 + timedelta(minutes=10)
    lib.rows["acct1"] = row(active=False, error="(326) Authorization: Denied by access control")
    assert xr.no_account_cause(r.pool_row(), T0, rate_limit_evidence=False) == ("inactive", "x_account_suspended")
    lib.rows["acct1"] = row(active=False, error="(32) Could not authenticate you")
    assert xr.no_account_cause(r.pool_row(), T0, rate_limit_evidence=False) == ("inactive", "x_login_required")
    lib.rows["acct1"] = row(active=True, locks={"SearchTimeline": later.replace(tzinfo=None)})
    assert xr.no_account_cause(r.pool_row(), T0, rate_limit_evidence=True) == ("locked", "rate_limited")
    assert xr.no_account_cause(r.pool_row(), T0, rate_limit_evidence=False) == ("waiting", "in_flight_lock")
    lib.rows["acct1"] = row(active=True, error="server")
    assert xr.no_account_cause(r.pool_row(), T0, rate_limit_evidence=False) == ("server_error", "failed")
    del lib.rows["acct1"]
    assert r.pool_row() == xr.PoolRow(False, None)
    assert ("get", r._api.db, "acct1") in lib.calls
    s.close()


def source(config, clock):
    return pp.PcSource("xsearch_web", configured_budget=config.x_daily_post_budget, floor=40, adaptive=True,
                       clock=clock)


def _unit(s, config, *, symbol="SOL", fallback=None, clock=None):
    clock = clock or Clock()
    pool = xp.XPool(list(config.x_accounts), clock=clock)
    pool.set_canary_passed(labels=list(config.x_accounts))
    src = source(config, clock)
    out = xp.run_unit(pool, s.readers, src, config, symbol=symbol, coin=xf.Coin("SOL", "Solana"), day=DAY,
                      query=QUERY, policy=xf.FilterPolicy.from_config(config), rng=random.Random(1),
                      sleep=lambda _s: None, fallback=fallback)
    return out, pool


def test_ban_codes_pause_rest_of_day_and_set_persisted_alert(tmp_path, lib):
    s, d = start(tmp_path, lib)
    config = cfg(d)
    for label in ("acct1", "acct2"):
        lib.scripts[str(d / f"{label}.db")] = [NoAccountError("x")]
        lib.rows[label] = row(active=False, error="(88) Rate limit exceeded")
    clock = Clock()
    first, pool = _unit(s, config, clock=clock)
    assert first.reason == "account_failed" and not pool.is_paused()  # both banned inside one unit's restarts
    clock.now += timedelta(seconds=config.x_query_delay_max_s + 1)
    out, pool = _unit(s, config, clock=clock)
    assert out.result is None and pool.is_paused() and pool.pause_reason() == "no_usable_account"
    assert [a["reason"] for a in pool.alerts()] == ["x_account_suspended", "x_account_suspended"]
    assert xp.XPool(["acct1", "acct2"], clock=Clock()).alerts() == pool.alerts()  # persisted
    s.close()


def test_cloudflare_html_block_pauses_day(tmp_path, lib):
    for i, text in enumerate(("Blocked by Cloudflare: 403 - r", "Blocked by HTML: 403 - r")):
        s, d = start(tmp_path / str(i), lib)
        lib.scripts[str(d / "acct1.db")] = [AbortReqError(text)]
        out, pool = _unit(s, cfg(d))
        assert out.result is None and pool.pause_reason() == ("cloudflare_block", "html_block")[i]
        s.close()
        for p in (cache.CACHE_ROOT / "attention" / "_pc_state").glob("*.json"):
            p.unlink()


def test_html_block_without_flag_pauses_day(tmp_path, lib):
    s, d = start(tmp_path, lib)
    calls = []
    lib.scripts[str(d / "acct1.db")] = [AbortReqError("Blocked by HTML: 400 - r")]
    out, pool = _unit(s, cfg(d, x_allow_curl_backend=False), fallback=lambda *a: calls.append(a))
    assert calls == [] and pool.pause_reason() == "html_block" and out.result is None
    s.close()


def test_all_accounts_bare_locked_wait_for_lock_end_not_day(tmp_path, lib):
    """A killed process leaves the library's in-flight lock (now + 15 min) with no rate-limit evidence on our
    side: the pool waits for the earliest lock end, never for 00:00 UTC (restart test 30-10-26)."""
    s, d = start(tmp_path, lib)
    for label in ("acct1", "acct2"):
        lib.scripts[str(d / f"{label}.db")] = [NoAccountError("x")]
        lib.rows[label] = row(active=True, locks={"SearchTimeline": T0 + timedelta(minutes=14)})
    clock, config = Clock(), cfg(d)
    out, pool = _unit(s, config, clock=clock)
    end = T0 + timedelta(minutes=14, seconds=xp.LOCK_MARGIN_S)
    assert out.result is None and out.reason == "in_flight_lock" and pool.pause_reason() == "in_flight_lock"
    assert pool.resume_at() == end
    assert [pool.account_state(x) for x in ("acct1", "acct2")] == [("locked", "in_flight_lock")] * 2
    assert not [c for c in lib.calls if "reset" in c[0] or "unlock" in c[0] or "lock_until" in c[0]]
    clock.now = end
    assert not pool.is_paused() and pool.usable() == ["acct1", "acct2"]
    s.close()


def test_start_does_not_call_reset_locks_and_keeps_our_utc_day_locks_across_restart(tmp_path, lib):
    s, d = start(tmp_path, lib)
    pool = xp.XPool(["acct1", "acct2"], clock=Clock())
    pool.lock_for_day("acct1")
    s.close()
    s2 = tr.start(cfg(d), env=GOOD_ENV, repo_root=tmp_path / "repo", dist_lookup=lookup(), load=tr.load_library,
                  platform="manylinux_x86_64", dump_roots=[tmp_path / "tmp"])
    assert xp.XPool(["acct1", "acct2"], clock=Clock()).account_state("acct1") == ("locked", "rate_limited")
    assert not [c for c in lib.calls if "reset" in c[0] or "login" in c[0]]
    s2.close()


# --- reading pages ------------------------------------------------------------------------------------------------

def test_search_raw_pages_entries_headers_cursor_and_snowflake_times(tmp_path, lib):
    s, d = start(tmp_path, lib)
    base = datetime(2026, 10, 26, 23, 0, tzinfo=UTC)
    ids1 = [snowflake(base - timedelta(minutes=i)) for i in range(20)]
    ids2 = [snowflake(base - timedelta(minutes=30 + i)) for i in range(5)]
    lib.scripts[str(d / "acct1.db")] = [
        FakeResponse(page_body(ids1, cursor="C1"), {"x-rate-limit-remaining": "49", "x-rate-limit-limit": "50"}),
        FakeResponse(page_body(ids2, cursor=None), {"x-rate-limit-remaining": "46", "x-rate-limit-limit": "50"})]
    r = s.readers["acct1"]
    p0 = r.search_raw(QUERY, {"product": "Latest"}, 0)
    assert p0.entry_ids == tuple(f"tweet-{i}" for i in ids1)
    assert (p0.rate_limit_remaining, p0.rate_limit_limit, p0.retries) == (49, 50, 0)
    assert p0.entry_times[0] == base and r.cursor == "C1"
    assert tr.entry_time(f"tweet-{snowflake(base) + (999 << 22)}") == base  # whole seconds, like created_at
    assert tr.entry_time("tweet-abc") is None
    p1 = r.search_raw(QUERY, {"product": "Latest"}, 1)
    assert p1.retries == 2  # remaining fell by 3 for one page: two hidden requests (retries or empty pages)
    assert r.search_raw(QUERY, {"product": "Latest"}, 2) is None
    first = next(c for c in lib.calls if c[0] == "search_raw")
    assert first[2] == QUERY and first[3] == 60 and first[4] == {"product": "Latest"}
    assert r.overhead_requests == tr.SETUP_REQUESTS_ESTIMATE
    with pytest.raises(ValueError):
        r.search_raw(QUERY, {"product": "Latest"}, 5)
    tweets = r.parse_tweets(p0.body)
    assert len(tweets) == 20 and isinstance(tweets[0], xf.Tweet) and tweets[0].cashtags == ("SOL",)
    assert tweets[0].views == 100 and tweets[0].user.followers == 50
    s.close()


def test_epoch_window_query_is_explicit_start_end(tmp_path):
    start_, end_ = datetime(2026, 10, 26, tzinfo=UTC), datetime(2026, 10, 27, tzinfo=UTC)
    q = tr.window_query('("$SOL" OR "Solana")', start=start_, end=end_, lang="en")
    assert q.endswith(f"since_time:{int(start_.timestamp())} until_time:{int(end_.timestamp())}")
    from api.data.attention import x_window
    assert q == x_window.build_query('("$SOL" OR "Solana")', DAY, syntax="since_time", lang="en")
    six = tr.window_query("bitcoin", start=start_, end=start_ + timedelta(hours=6), lang="")
    assert "until_time:" + str(int((start_ + timedelta(hours=6)).timestamp())) in six
    with pytest.raises(ValueError):
        tr.window_query("bitcoin", start=end_, end=start_, lang="en")
    assert wq.load().config.x_window_syntax == "since_time"  # P-X9: the epoch form is the one X honours


def test_read_accounting_uses_search_raw_entries_and_parse_drop_stops(tmp_path, lib):
    s, d = start(tmp_path, lib)
    base = datetime(2026, 10, 26, 23, 0, tzinfo=UTC)
    ids = [snowflake(base - timedelta(minutes=i)) for i in range(20)]
    lib.dropped = set(ids[:10])
    lib.scripts[str(d / "acct1.db")] = [FakeResponse(page_body(ids), {"x-rate-limit-remaining": "40"})]
    out, pool = _unit(s, cfg(d))
    assert out.result is None and pool.stopped_reason() == "layout_changed"
    assert out.reads == 20  # raw entries read, not the 10 parsed
    s.close()


def test_one_unit_end_to_end_records_label_commit_and_no_cookies(tmp_path, lib):
    s, d = start(tmp_path, lib)
    base = datetime(2026, 10, 26, 22, 0, tzinfo=UTC)
    ids = [snowflake(base - timedelta(minutes=i * 70)) for i in range(15)] + [snowflake(base - timedelta(days=1))]
    body = page_body(ids, cursor=None)
    body["auth_token"] = SECRET
    lib.scripts[str(d / "acct1.db")] = [FakeResponse(body, {"x-rate-limit-remaining": "40", "set-cookie": SECRET})]
    out, _pool = _unit(s, cfg(d))
    assert out.result is not None and out.row["account"] == "acct1" and out.row["reader_commit"] == PIN
    raw = list((cache.CACHE_ROOT / "attention" / "xsearch_raw").rglob("*.json.gz"))
    assert raw and all(b"PLANTED" not in __import__("gzip").decompress(p.read_bytes()) for p in raw)
    s.close()


# --- AC53: the curl fallback --------------------------------------------------------------------------------------

def record():
    return tr.install_record("manylinux_x86_64", tr.lock_text())


def curl_start(tmp_path, lib, child, **over):
    d = accounts(tmp_path)
    config = cfg(d, x_allow_curl_backend=True, **over)
    s = tr.start(config, env=GOOD_ENV, repo_root=tmp_path / "repo", dist_lookup=lookup(curl=curl_dist()),
                 load=tr.load_library, platform="manylinux_x86_64", dump_roots=[tmp_path / "tmp"],
                 curl_record=record(), run_child=child)
    return s, d, config


class Child:
    """The fallback process stand-in: records what it was started with and answers one scripted reply."""

    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []

    def __call__(self, request, env):
        self.calls.append((request, env))
        return self.replies.pop(0)


def ok_reply(ids, cursor=None):
    return {"status": "ok", "body": page_body(ids, cursor=cursor), "remaining": 30, "limit": 50}


def test_curl_fallback_runs_in_separate_process_with_backend_env_only_there(tmp_path, lib, monkeypatch):
    base = datetime(2026, 10, 26, 22, 0, tzinfo=UTC)
    ids = [snowflake(base - timedelta(minutes=i * 70)) for i in range(15)] + [snowflake(base - timedelta(days=1))]
    child = Child(ok_reply(ids))
    monkeypatch.delenv("TWS_HTTP_BACKEND", raising=False)
    s, d, config = curl_start(tmp_path, lib, child)
    lib.scripts[str(d / "acct1.db")] = [AbortReqError("Blocked by Cloudflare: 403 - r")]
    out, _pool = _unit(s, config, fallback=s.fallback)
    assert out.result is not None and len(child.calls) == 1
    request, env = child.calls[0]
    assert env["TWS_HTTP_BACKEND"] == "curl" and tr.env_guard(env, fallback=True) == []
    assert request["db"] == str(d / "acct1.db") and request["label"] == "acct1" and request["query"] == QUERY
    assert "TWS_HTTP_BACKEND" not in os.environ  # the main process keeps the default backend
    assert "curl_cffi" not in sys.modules
    s.close()


def test_blocked_by_cloudflare_and_blocked_by_html_both_trigger_fallback_with_flag_on(tmp_path, lib):
    base = datetime(2026, 10, 26, 22, 0, tzinfo=UTC)
    ids = [snowflake(base - timedelta(minutes=i * 70)) for i in range(15)] + [snowflake(base - timedelta(days=1))]
    for i, text in enumerate(("Blocked by Cloudflare: 403 - r", "Blocked by HTML: 400 - r")):
        child = Child(ok_reply(ids))
        s, d, config = curl_start(tmp_path / str(i), lib, child)
        lib.scripts[str(d / "acct1.db")] = [AbortReqError(text)]
        out, _pool = _unit(s, config, fallback=s.fallback)
        assert len(child.calls) == 1 and out.result is not None, text
        assert out.row["backend_events"][0]["reason"] == ("cloudflare_block", "html_block")[i]
        s.close()
        for p in (cache.CACHE_ROOT / "attention").rglob("*.json*"):
            p.unlink()


def test_cloudflare_block_flag_true_retries_once_with_curl_then_pauses_day_if_still_blocked(tmp_path, lib):
    child = Child({"status": "fail", "kind": "abort", "abort": "cloudflare"})
    s, d, config = curl_start(tmp_path, lib, child)
    lib.scripts[str(d / "acct1.db")] = [AbortReqError("Blocked by Cloudflare: 403 - r")]
    out, pool = _unit(s, config, fallback=s.fallback)
    assert len(child.calls) == 1 and pool.pause_reason() == "cloudflare_block" and out.result is None
    assert pool.curl_used_today() and pool.health()["curl_uses"] == 1
    s.close()


def test_curl_used_only_after_cloudflare_block_never_for_other_codes(tmp_path, lib):
    for i, exc in enumerate((NoAccountError("x"), ApiError("(88) Rate limit exceeded"), AbortReqError("other"),
                             GqlFeaturesOutdatedError("g"), XClIdParseError("p"))):
        child = Child()
        s, d, config = curl_start(tmp_path / str(i), lib, child)
        lib.scripts[str(d / "acct1.db")] = [exc]
        lib.rows["acct1"] = row(active=False, error="(32) Could not authenticate you")
        _unit(s, config, fallback=s.fallback)
        assert child.calls == [], exc
        s.close()
        for p in (cache.CACHE_ROOT / "attention").rglob("*.json*"):
            p.unlink()


def test_curl_use_logged_in_evidence_and_health(tmp_path, lib):
    base = datetime(2026, 10, 26, 22, 0, tzinfo=UTC)
    ids = [snowflake(base - timedelta(minutes=i * 70)) for i in range(15)] + [snowflake(base - timedelta(days=1))]
    s, d, config = curl_start(tmp_path, lib, Child(ok_reply(ids)))
    lib.scripts[str(d / "acct1.db")] = [AbortReqError("Blocked by HTML: 400 - r")]
    out, _pool = _unit(s, config, fallback=s.fallback)
    assert out.row["backend_events"] == [{"backend": "curl", "reason": "html_block", "outcome": "ok"}]
    h = tr.reader_status(config, env=GOOD_ENV, now=T0, dist_lookup=lookup(curl=curl_dist()),
                         platform="manylinux_x86_64", curl_record=record(), repo_root=tmp_path / "repo")
    assert h["curl_uses"] == 1 and h["curl_last_use"] == T0.isoformat() and h["curl_fallback"] == "ok"
    s.close()


def test_next_unit_tries_default_backend_first(tmp_path, lib):
    base = datetime(2026, 10, 26, 22, 0, tzinfo=UTC)
    ids = [snowflake(base - timedelta(minutes=i * 70)) for i in range(15)] + [snowflake(base - timedelta(days=1))]
    child = Child(ok_reply(ids))
    s, d, config = curl_start(tmp_path, lib, child)
    lib.scripts[str(d / "acct1.db")] = [AbortReqError("Blocked by HTML: 400 - r")]
    clock = Clock()
    _unit(s, config, fallback=s.fallback, clock=clock)
    clock.now += timedelta(seconds=config.x_query_delay_max_s + 1)
    lib.scripts[str(d / "acct2.db")] = [FakeResponse(page_body(ids, cursor=None), {"x-rate-limit-remaining": "40"})]
    out, _pool = _unit(s, config, symbol="ETH", fallback=s.fallback, clock=clock)
    assert len(child.calls) == 1 and out.row["backend_events"] == []
    assert [c[1] for c in lib.calls if c[0] == "search_raw"][-1] == str(d / "acct2.db")
    s.close()


def test_curl_reads_count_against_budget(tmp_path, lib):
    base = datetime(2026, 10, 26, 22, 0, tzinfo=UTC)
    ids = [snowflake(base - timedelta(minutes=i * 70)) for i in range(15)] + [snowflake(base - timedelta(days=1))]
    s, d, config = curl_start(tmp_path, lib, Child(ok_reply(ids)))
    lib.scripts[str(d / "acct1.db")] = [AbortReqError("Blocked by HTML: 400 - r")]
    out, _pool = _unit(s, config, fallback=s.fallback)
    assert out.reads == 16
    assert source(config, Clock()).used == 16
    s.close()


def test_fallback_continues_from_cursor_of_previous_page(tmp_path, lib):
    base = datetime(2026, 10, 26, 23, 50, tzinfo=UTC)
    ids1 = [snowflake(base - timedelta(minutes=i)) for i in range(20)]
    child = Child(ok_reply([snowflake(base - timedelta(minutes=30 + i)) for i in range(5)]))
    s, d, config = curl_start(tmp_path, lib, child)
    lib.scripts[str(d / "acct1.db")] = [FakeResponse(page_body(ids1, cursor="C1"), {"x-rate-limit-remaining": "40"}),
                                        AbortReqError("Blocked by HTML: 400 - r")]
    _unit(s, config, fallback=s.fallback)
    assert child.calls[0][0]["kv"] == {"product": "Latest", "cursor": "C1"}
    s.close()


def test_installer_picks_wheel_by_platform_and_records_hash():
    lock = tr.lock_text()
    for key, (wheel, sha) in tr.CURL_WHEELS.items():
        rec = tr.install_record(key, lock)
        assert rec == {"package": "curl_cffi", "version": "0.16.3", "platform": key, "wheel": wheel, "sha256": sha}
    assert tr.platform_key("win32", "AMD64", "") == "win_amd64"
    assert tr.platform_key("linux", "x86_64", "glibc") == "manylinux_x86_64"
    assert tr.platform_key("linux", "x86_64", "musl") == "musllinux_x86_64"
    bad = lock.replace(tr.CURL_WHEELS["win_amd64"][1], "0" * 64)
    with pytest.raises(tr.CurlUnavailable) as e:
        tr.install_record("win_amd64", bad)
    assert str(e.value) == "CurlUnavailable lock_hash_mismatch"
    tr.write_install_record(record())
    assert tr.read_install_record() == record()


def test_startup_verifies_installed_wheel_hash_against_matching_entry():
    rec = record()
    assert tr.curl_status(rec, "manylinux_x86_64", curl_dist()) == "ok"
    assert tr.curl_status({**rec, "sha256": "0" * 64}, "manylinux_x86_64", curl_dist()) == "hash_mismatch"
    assert tr.curl_status(rec, "win_amd64", curl_dist()) == "record_platform_mismatch"
    assert tr.curl_status(None, "manylinux_x86_64", curl_dist()) == "record_missing"
    assert tr.curl_status(rec, "manylinux_x86_64", None) == "not_installed"
    assert tr.curl_status(rec, "manylinux_x86_64", curl_dist(version="0.17.0b1")) == "version_mismatch"
    assert tr.curl_status(rec, "manylinux_x86_64", curl_dist(name="curl-cffi2")) == "name_mismatch"
    assert tr.curl_status(rec, "manylinux_x86_64", curl_dist(tag="cp310-abi3-win_amd64")) == "wheel_tag_mismatch"


def test_unknown_platform_or_architecture_refused_fallback_off_and_health_says_so(tmp_path, lib):
    for args in (("darwin", "arm64", ""), ("linux", "aarch64", "glibc"), ("win32", "ARM64", ""),
                 ("linux", "x86_64", "")):
        assert tr.platform_key(*args) is None, args
    assert tr.platform_key("linux", "x86_64", "glibc", free_threaded=True) is None
    assert tr.curl_status(record(), None, curl_dist()) == "unknown_platform"
    with pytest.raises(tr.CurlUnavailable):
        tr.install_record(None, tr.lock_text())
    child = Child()
    d = accounts(tmp_path)
    config = cfg(d, x_allow_curl_backend=True)
    s = tr.start(config, env=GOOD_ENV, repo_root=tmp_path / "repo", dist_lookup=lookup(curl=curl_dist()),
                 load=tr.load_library, platform=None, dump_roots=[], curl_record=record(), run_child=child)
    assert s.fallback is None and "curl_fallback_off:unknown_platform" in s.notes
    h = tr.reader_status(config, env=GOOD_ENV, now=T0, dist_lookup=lookup(curl=curl_dist()), platform=None,
                         curl_record=record(), repo_root=tmp_path / "repo")
    assert h["curl_fallback"] == "unknown_platform"
    s.close()


# --- AC47, AC52: accounts files and health ------------------------------------------------------------------------

def test_pool_size_within_configured_bounds_and_unknown_label_refused(tmp_path, lib):
    d = accounts(tmp_path, labels=("acct1", "acct2", "acct3"))
    common = {"repo_root": tmp_path / "repo"}
    assert tr.accounts_problems(cfg(d, labels=("acct1", "acct2", "acct3")), **common) == []
    assert tr.accounts_problems(cfg(d, labels=()), **common) == ["pool_size"]
    assert tr.accounts_problems(cfg(d, labels=("acct1", "acct2", "acct3"), x_pool_max=2), **common) == ["pool_size"]
    assert tr.accounts_problems(cfg(d, labels=("acct1", "acct2")), **common) == ["unknown_account_file"]
    (d / "acct3.db").unlink()
    assert tr.accounts_problems(cfg(d, labels=("acct1", "acct2", "acct4")), **common) == ["missing_account_file"]
    with pytest.raises(tr.XStartRefused) as e:
        tr.start(cfg(d, labels=("acct1",)), env=GOOD_ENV, dist_lookup=lookup(), load=tr.load_library,
                 platform=None, dump_roots=[], **common)
    assert e.value.reasons == ["unknown_account_file"]
    with pytest.raises(ValueError):
        wq.validate_config({**wq.load().config.as_dict(), "x_accounts": ["acct1", "acct1"]})
    with pytest.raises(ValueError):
        wq.validate_config({**wq.load().config.as_dict(), "x_accounts": ["Acct One"]})
    with pytest.raises(ValueError):
        wq.validate_config({**wq.load().config.as_dict(), "x_accounts": ["a", "b", "c", "d"]})


def test_accounts_db_path_outside_repo_required(tmp_path):
    repo = tmp_path / "repo"
    inside = repo / "secrets"
    inside.mkdir(parents=True)
    (inside / "acct1.db").write_text("x", encoding="utf-8")
    os.chmod(inside, 0o700)
    os.chmod(inside / "acct1.db", 0o600)
    assert tr.accounts_problems(cfg(inside, labels=("acct1",)), repo_root=repo) == ["accounts_path_in_repo"]
    assert tr.accounts_problems(cfg("", labels=("acct1",)), repo_root=repo) == ["accounts_path_unset"]
    assert tr.accounts_problems(cfg("relative/xpool", labels=("acct1",)), repo_root=repo) == [
        "accounts_path_not_absolute"]
    assert tr.accounts_problems(cfg(tmp_path / "absent", labels=("acct1",)), repo_root=repo) == [
        "accounts_path_missing"]
    assert wq.load().config.x_accounts_db_path == ""


@pytest.mark.skipif(os.name != "posix", reason="POSIX mode bits")
def test_accounts_db_permissions_checked_fake_fs(tmp_path):
    d = accounts(tmp_path, labels=("acct1",))
    config, repo = cfg(d, labels=("acct1",)), tmp_path / "repo"
    assert tr.accounts_problems(config, repo_root=repo) == []
    os.chmod(d / "acct1.db", 0o644)
    assert tr.accounts_problems(config, repo_root=repo) == ["permissions"]
    os.chmod(d / "acct1.db", 0o600)
    os.chmod(d, 0o755)
    assert tr.accounts_problems(config, repo_root=repo) == ["permissions"]
    os.chmod(d, 0o700)
    real = os.stat

    def other_owner(p, *a, **kw):
        st = real(p, *a, **kw)
        return os.stat_result((st.st_mode, st.st_ino, st.st_dev, st.st_nlink, st.st_uid + 1) + tuple(st)[5:])

    assert tr.accounts_problems(config, repo_root=repo, stat_fn=other_owner) == ["permissions"]
    # Windows: mode bits say nothing about the ACL; the check is reported as not done, never as passed.
    assert tr.accounts_problems(config, repo_root=repo, posix=False) == []
    assert tr.permission_note(posix=False) == "windows_acl_not_checked"
    assert tr.permission_note(posix=True) is None
    assert stat.S_IMODE(os.stat(d).st_mode) == 0o700


def test_cookie_refresh_is_add_account_cookies_upsert(tmp_path, lib):
    d = accounts(tmp_path, labels=("acct1",))
    config = cfg(d, labels=("acct1", "acct2"))
    tr.refresh_cookies("acct2", SECRET, config=config, env=GOOD_ENV, now=T0, repo_root=tmp_path / "repo")
    assert ("add_account_cookies", str(d / "acct2.db"), "acct2") in lib.calls
    assert lib.apis[-1]["raise_when_no_account"] is True and lib.apis[-1]["wait_timeout"] == 0
    if os.name == "posix":
        assert stat.S_IMODE(os.stat(d / "acct2.db").st_mode) == 0o600
    assert tr.cookie_ages(config, now=T0 + timedelta(days=3)) == {"acct1": None, "acct2": 3}
    with pytest.raises(ValueError):
        tr.refresh_cookies("acct9", SECRET, config=config, env=GOOD_ENV, now=T0, repo_root=tmp_path / "repo")
    with pytest.raises(tr.XStartRefused):
        tr.refresh_cookies("acct1", SECRET, config=config, env={**GOOD_ENV, "TWS_TELEMETRY": "1"}, now=T0,
                           repo_root=tmp_path / "repo")
    assert SECRET not in (d / "cookie_ages.json").read_text(encoding="utf-8")


def test_cookie_age_in_days_in_health(tmp_path, lib):
    d = accounts(tmp_path)
    config = cfg(d)
    tr.refresh_cookies("acct1", SECRET, config=config, env=GOOD_ENV, now=T0 - timedelta(days=5),
                       repo_root=tmp_path / "repo")
    h = tr.reader_status(config, env=GOOD_ENV, now=T0, dist_lookup=lookup(), platform="manylinux_x86_64",
                         curl_record=None, repo_root=tmp_path / "repo")
    ages = {a["label"]: a["cookie_age_days"] for a in h["accounts"]}
    assert ages == {"acct1": 5, "acct2": None}


def test_health_active_over_total_with_label_last_used_state_cookie_age_no_secrets(tmp_path, lib, capsys):
    d = accounts(tmp_path)
    config = cfg(d)
    pool = xp.XPool(["acct1", "acct2"], clock=Clock())
    pool.mark_used("acct1")
    pool.mark_inactive("acct2", "x_login_required")
    h = tr.reader_status(config, env={**GOOD_ENV, "HTTPS_PROXY": SECRET}, now=T0, dist_lookup=lookup(),
                         platform="manylinux_x86_64", curl_record=None, repo_root=tmp_path / "repo")
    assert (h["active"], h["total"]) == (1, 2)
    assert h["accounts"][0] == {"label": "acct1", "state": "active", "reason": None, "last_used": T0.isoformat(),
                                "cookie_age_days": None}
    assert h["accounts"][1]["state"] == "inactive" and h["accounts"][1]["reason"] == "x_login_required"
    assert h["commit_match"] is True and h["env_ok"] is False and h["env_bad"] == ["HTTPS_PROXY"]
    assert h["accounts_path"] == "ok" and h["curl_fallback"] == "flag_false"
    assert SECRET not in json.dumps(h)
    lines = tr.status_lines(h)
    assert lines[0].startswith("xreader accounts_active=1 accounts_total=2 commit_match=true env_ok=false")
    assert all(SECRET not in ln and str(d) not in ln for ln in lines)
    planted = {**h, "accounts_path": str(d), "accounts": [{**h["accounts"][0], "reason": SECRET}]}
    assert "accounts_path=redacted" in tr.status_lines(planted)[0]
    assert "reason=redacted" in tr.status_lines(planted)[1]


def test_reader_status_probe_mode_prints_counts_labels_states_only(tmp_path, lib, monkeypatch, capsys):
    d = accounts(tmp_path)
    monkeypatch.setattr(probe, "_reader_status_config", lambda: cfg(d))
    for k, v in GOOD_ENV.items():
        monkeypatch.setenv(k, v)
    for k in [*xr.PROXY_VARS, "TWS_HTTP_BACKEND"]:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("X_SECRET_PLANT", SECRET)
    monkeypatch.setattr(tr, "find_dist", lookup())
    assert probe.main(["--source", "xsearch", "--reader-status"]) == 0
    out = capsys.readouterr().out
    assert "xreader accounts_active=2 accounts_total=2 commit_match=true env_ok=true" in out
    assert "account label=acct1 state=active" in out
    assert SECRET not in out and str(d) not in out and "PLANTED" not in out
    assert probe.main(["--source", "x", "--symbol", "SOL"]) == 2  # the other modes stay unbuilt


def test_daily_cross_account_canary_runs_on_two_accounts(tmp_path, lib):
    s, d = start(tmp_path, lib)
    config = cfg(d)
    start_, _end = xp.canary_window(T0)
    ids = [snowflake(start_ + timedelta(minutes=2 * i + 1)) for i in range(20)]
    for label in ("acct1", "acct2"):
        lib.scripts[str(d / f"{label}.db")] = [FakeResponse(page_body(ids), {"x-rate-limit-remaining": "40"})]
    pool = xp.XPool(["acct1", "acct2"], clock=Clock())
    src = source(config, Clock())
    out = xp.run_daily_canary(pool, s.readers, src, config, rng=random.Random(1), sleep=lambda _s: None)
    assert out.passed and sorted(pool.canary_labels()) == ["acct1", "acct2"]
    dbs = [c[1] for c in lib.calls if c[0] == "search_raw"]
    assert dbs == [str(d / "acct1.db"), str(d / "acct2.db")]
    s.close()


def test_logs_class_and_status_only_planted_secrets(tmp_path, lib, capsys):
    s, d = start(tmp_path, lib)
    lib.scripts[str(d / "acct1.db")] = [RuntimeError(SECRET)]
    with pytest.raises(xr.ReaderFailure) as e:
        s.readers["acct1"].search_raw(QUERY, {"product": "Latest"}, 0)
    assert SECRET not in str(e.value) and e.value.__cause__ is None and e.value.__context__ is None
    with pytest.raises(tr.RefreshFailed) as e2:
        lib.API = lambda pool=None, **kw: (_ for _ in ()).throw(RuntimeError(SECRET))
        tr.refresh_cookies("acct1", SECRET, config=cfg(d), env=GOOD_ENV, now=T0, repo_root=tmp_path / "repo")
    assert str(e2.value) == "RefreshFailed RuntimeError" and e2.value.__cause__ is None
    reply = tr.child_reply_for(xr.ReaderFailure("abort", text="Blocked by Cloudflare: 403 - " + SECRET))
    assert reply == {"status": "fail", "kind": "abort", "abort": "cloudflare"}
    out = capsys.readouterr()
    assert SECRET not in out.out + out.err
    s.close()


def test_to_tweet_keeps_missing_counts_as_none_never_zero():
    t = lib_tweet(1849000000000000000)
    for obj, name in ((t.user, "followersCount"), (t.user, "statusesCount"), (t, "likeCount"), (t, "replyCount"),
                      (t, "quoteCount"), (t, "retweetCount"), (t, "viewCount")):
        setattr(obj, name, None)
    out = tr.to_tweet(t)
    assert (out.user.followers, out.user.statuses) == (None, None)
    assert (out.like, out.reply, out.quote, out.retweet, out.views) == (None, None, None, None, None)
    # A present zero stays zero.
    z = lib_tweet(1849000000000000000)
    z.user.followersCount, z.likeCount = 0, 0
    assert (tr.to_tweet(z).user.followers, tr.to_tweet(z).like) == (0, 0)
