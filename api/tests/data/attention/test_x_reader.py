"""W8d1 AC41, AC46, AC49-AC55: X reader seam, fail-closed mapping, account pool, unit integrity, canary,
global budget, read accounting, parse-drop guard, curl fallback decision and the environment guard.

Fake readers and fake raw pages only; nothing from the X library is imported; no network. Injected clock.
"""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta, timezone

import pytest

from api.data import cache
from api.data.attention import pc_pace as pp
from api.data.attention import web_queries as wq
from api.data.attention import x_filters as xf
from api.data.attention import x_pool as xp
from api.data.attention import x_raw as xr
from api.data.attention import x_reader as xrd

T0 = datetime(2026, 10, 21, 10, 0, tzinfo=timezone.utc)
DAY = date(2026, 10, 20)
END = datetime(2026, 10, 21, tzinfo=timezone.utc)
SOL = xf.Coin("SOL", "Solana")
POLICY = xf.FilterPolicy()
QUERY = '"$SOL" lang:en -filter:replies -filter:retweets'


@pytest.fixture(autouse=True)
def _isolated(attention_cache):
    return attention_cache


def reset_state():
    """Forget every persisted pool and source state (a loop below runs several fresh setups in one test)."""
    for p in (cache.CACHE_ROOT / "attention" / "_pc_state").glob("*.json"):
        p.unlink()


class Clock:
    def __init__(self, now: datetime = T0):
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kw) -> None:
        self.now += timedelta(**kw)


def cfg(**over) -> wq.CollectorConfig:
    return wq.CollectorConfig(**{**wq.load().config.as_dict(), **over})


_ids = iter(range(1, 10**9))


def tweets(n: int, newest: datetime, step_min: float = 10, prefix: str = "Solana") -> list[xf.Tweet]:
    out = []
    for i in range(n):
        tid = next(_ids)
        u = xf.XUser(tid, datetime(2024, 1, 1, tzinfo=timezone.utc), 100, 100, "https://img/p.jpg", False)
        out.append(xf.Tweet(tid, newest - timedelta(minutes=step_min * i), f"{prefix} {tid}", u, "en", ("SOL",)))
    return out


def page(tws: list[xf.Tweet], *, broken: int = 0, retries: int = 0, remaining: int | None = 40) -> xrd.RawPage:
    return xrd.FakeXReader.page_of(tws, broken=broken, retries=retries, remaining=remaining)


def day_pages(n_pages: int = 2, per: int = 20, step_min: float = 10) -> list[xrd.RawPage]:
    """Newest first from just before the window end; 2 x 20 entries read reach N = 40 (capped)."""
    tws = tweets(n_pages * per, END - timedelta(minutes=1), step_min)
    return [page(tws[i * per:(i + 1) * per]) for i in range(n_pages)]


ACTIVE = xrd.PoolRow(active=True, error_msg=None, locks={}, last_used=None)


def reader(label: str, items=(), row: xrd.PoolRow = ACTIVE) -> xrd.FakeXReader:
    return xrd.FakeXReader(label, list(items), row)


def setup(labels=("acct_a", "acct_b"), clock=None, budget=800):
    clock = clock or Clock()
    pool = xp.XPool(list(labels), clock=clock)
    src = pp.PcSource("xsearch_web", configured_budget=budget, floor=40, adaptive=True, clock=clock)
    return clock, pool, src


def unit(pool, readers, src, config=None, fallback=None, symbol="SOL", day=DAY):
    return xp.run_unit(pool, readers, src, config or cfg(), symbol=symbol, day=day, query=QUERY, coin=SOL,
                       policy=POLICY, rng=random.Random(1), sleep=lambda s: None, fallback=fallback)


def pass_canary(pool):
    pool.set_canary_passed(note="test")


def inactive_row(msg: str | None) -> xrd.PoolRow:
    return xrd.PoolRow(active=False, error_msg=msg, locks={}, last_used=None)


# --- AC41 seam and pin data --------------------------------------------------------------------------------------

def test_fake_reader_satisfies_protocol_and_pin_is_data_only():
    r = reader("acct_a", day_pages(1))
    assert isinstance(r, xrd.XReader)
    assert xrd.TWSCRAPE_PINNED_COMMIT == "63f61a518e576ea5c132f1156c03dda0520d76c1"
    assert xrd.TWSCRAPE_PACKAGE == "twscrape" and xrd.TWSCRAPE_REPO == "https://github.com/vladkens/twscrape"
    assert xrd.CURL_CFFI_PIN == "0.16.3"
    got = r.search_raw(QUERY, {"product": "Latest"}, 0)
    assert len(got.entry_ids) == 20 and len(r.parse_tweets(got.body)) == 20
    assert r.calls == [(QUERY, {"product": "Latest"}, 0)]


# --- AC46 fail closed and the NoAccountError cause --------------------------------------------------------------

def test_none_short_empty_exception_is_missing_never_zero():
    cases = {
        "none_result": [None],
        "empty_page": [page([])],
        "short_result": [page(tweets(5, END - timedelta(minutes=1), 1))] * 3,  # page cap, < N_min read
        "failed": [xrd.ReaderFailure("api", status=500)],
    }
    for reason, items in cases.items():
        reset_state()
        _, pool, src = setup(("acct_a",))
        pass_canary(pool)
        out = unit(pool, {"acct_a": reader("acct_a", items)}, src)
        assert out.result is None and out.reason == reason, reason
        assert xr.read_x_rows("SOL") == []


def test_noaccounterror_cause_read_from_pool_row():
    now = T0
    assert xrd.no_account_cause(inactive_row("(88) Rate limit exceeded"), now) == ("inactive", "x_account_suspended")
    assert xrd.no_account_cause(inactive_row("(326) Authorization: Denied by access control"), now) == (
        "inactive", "x_account_suspended")
    assert xrd.no_account_cause(inactive_row("(32) Could not authenticate you"), now) == ("inactive", "x_login_required")
    assert xrd.no_account_cause(inactive_row(None), now) == ("inactive", "x_login_required")  # bare 403
    locked = xrd.PoolRow(True, None, {"SearchTimeline": now + timedelta(minutes=9)}, now)
    assert xrd.no_account_cause(locked, now) == ("locked", "rate_limited")
    stale = xrd.PoolRow(True, None, {"SearchTimeline": now - timedelta(minutes=1)}, now)
    assert xrd.no_account_cause(stale, now) == ("server_error", "failed")
    other_queue = xrd.PoolRow(True, "(130) Over capacity", {"UserByScreenName": now + timedelta(hours=1)}, now)
    assert xrd.no_account_cause(other_queue, now) == ("server_error", "failed")


def test_codes_88_326_32_403_pause_day_and_alert():
    for msg, alert in (("(88) Rate limit exceeded", "x_account_suspended"),
                       ("(326) Authorization: Denied by access control", "x_account_suspended"),
                       ("(32) Could not authenticate you", "x_login_required"), (None, "x_login_required")):
        reset_state()
        clock, pool, src = setup(("acct_a",))
        pass_canary(pool)
        r = reader("acct_a", [xrd.ReaderFailure("no_account")], inactive_row(msg))
        out = unit(pool, {"acct_a": r}, src)
        assert out.result is None and out.reason == "no_usable_account"
        assert pool.account_state("acct_a") == ("inactive", alert)
        assert pool.alerts() == [{"label": "acct_a", "reason": alert, "at": T0.isoformat()}]
        assert pool.pause_reason() == "no_usable_account"
        clock.advance(hours=13, minutes=59)
        assert pool.is_paused()
        clock.advance(minutes=1)  # 00:00 UTC next day: the day pause ends, the account stays inactive
        assert not pool.is_paused() and pool.select() is None


def test_cloudflare_block_flag_false_pauses_day_no_backend_switch():
    _, pool, src = setup()
    pass_canary(pool)
    calls = []
    a = reader("acct_a", [xrd.ReaderFailure("abort", text="Blocked by Cloudflare (403)")])
    out = unit(pool, {"acct_a": a, "acct_b": reader("acct_b", day_pages())}, src,
               fallback=lambda *args: calls.append(args))
    assert out.reason == "cloudflare_block" and pool.pause_reason() == "cloudflare_block"
    assert calls == [] and pool.health()["curl_uses"] == 0
    assert out.restarts == 0  # a block pauses the whole pool, never a rotation


def test_blocked_by_html_always_pauses_day_never_fallback():
    _, pool, src = setup()
    pass_canary(pool)
    calls = []
    a = reader("acct_a", [xrd.ReaderFailure("abort", text="Blocked by HTML")])
    out = unit(pool, {"acct_a": a, "acct_b": reader("acct_b")}, src, config=cfg(x_allow_curl_backend=True),
               fallback=lambda *args: calls.append(args))
    assert out.reason == "html_block" and pool.pause_reason() == "html_block" and calls == []


def test_curl_fallback_decision_table():
    d = xrd.fallback_decision
    assert d("cloudflare", allow_curl=True, retried=False) == "curl_retry"
    assert d("cloudflare", allow_curl=True, retried=True) == "pause_day"
    assert d("cloudflare", allow_curl=False, retried=False) == "pause_day"
    assert d("html", allow_curl=True, retried=False) == "pause_day"
    for kind in ("rate_limited", "x_login_required", "x_account_suspended", "no_account", "api", "other",
                 "gql_outdated", "xclid_parse", "not_found", "parse"):
        assert d(kind, allow_curl=True, retried=False) == "not_applicable", kind
    assert xrd.abort_kind("Blocked by Cloudflare") == "cloudflare"
    assert xrd.abort_kind("blocked by cloudflare") == "other"  # exact prefix only
    assert xrd.abort_kind("Blocked by HTML page") == "html"
    assert xrd.abort_kind("Repeated 404") == "other"
    assert xrd.abort_kind(None) == "other"
    failure = xrd.ReaderFailure("abort", text="Blocked by Cloudflare: " + "secret-body" * 3)
    assert "secret" not in str(failure) and "secret" not in repr(failure.__dict__)


def test_curl_fallback_flag_true_retries_once_then_pauses_and_logs():
    clock, pool, src = setup(("acct_a",))
    pass_canary(pool)
    pages_ = day_pages()
    calls = []

    def fallback(label, query, kv, page_no):
        calls.append((label, page_no))
        return pages_[0]

    a = reader("acct_a", [xrd.ReaderFailure("abort", text="Blocked by Cloudflare"), pages_[1]])
    out = unit(pool, {"acct_a": a}, src, config=cfg(x_allow_curl_backend=True), fallback=fallback)
    assert out.result is not None and out.label == "acct_a" and calls == [("acct_a", 0)]
    assert out.row["backend_events"] == [{"backend": "curl", "reason": "cloudflare_block", "outcome": "ok"}]
    assert pool.health()["curl_uses"] == 1 and pool.health()["curl_last_use"] == T0.isoformat()
    assert src.used == 40  # the reads through the fallback count against the global budget

    # Next unit: default backend first again; still blocked through the fallback pauses the day.
    clock.advance(minutes=10)
    a.items = [xrd.ReaderFailure("abort", text="Blocked by Cloudflare")]
    still = lambda *args: (_ for _ in ()).throw(xrd.ReaderFailure("abort", text="Blocked by Cloudflare"))
    out2 = unit(pool, {"acct_a": a}, src, config=cfg(x_allow_curl_backend=True), fallback=still, symbol="ETH")
    assert a.calls[-1][2] == 0  # the default reader was called first for the new unit
    assert out2.reason == "cloudflare_block" and pool.pause_reason() == "cloudflare_block"
    assert pool.health()["curl_uses"] == 2


def test_curl_never_for_rate_limit_login_or_ban_codes():
    _, pool, src = setup(("acct_a", "acct_b"))
    pass_canary(pool)
    calls = []
    a = reader("acct_a", [xrd.ReaderFailure("no_account")], inactive_row("(32) Could not authenticate you"))
    out = unit(pool, {"acct_a": a, "acct_b": reader("acct_b", day_pages())}, src,
               config=cfg(x_allow_curl_backend=True), fallback=lambda *args: calls.append(args))
    assert calls == [] and out.label == "acct_b" and out.restarts == 1


def test_three_parse_failures_set_layout_changed():
    clock, pool, src = setup(("acct_a",))
    pass_canary(pool)
    for i, kind in enumerate(("parse", "not_found", "xclid_parse")):
        out = unit(pool, {"acct_a": reader("acct_a", [xrd.ReaderFailure(kind)])}, src, symbol=f"C{i}")
        clock.advance(minutes=10)
        if i < 2:
            assert out.reason == "drift" and not pool.is_paused()
    assert out.reason == "layout_changed" and pool.stopped_reason() == "layout_changed"
    clock.advance(days=3)
    assert pool.is_paused()  # stays stopped until the owner re-pins and clears it
    pool.owner_clear_stop()
    assert not pool.is_paused()


def test_drift_streak_resets_on_a_clean_page():
    clock, pool, src = setup(("acct_a",))
    pass_canary(pool)
    for kind in ("gql_outdated", "parse"):
        unit(pool, {"acct_a": reader("acct_a", [xrd.ReaderFailure(kind)])}, src)
        clock.advance(minutes=10)
    assert unit(pool, {"acct_a": reader("acct_a", day_pages())}, src).result is not None
    clock.advance(minutes=10)
    out = unit(pool, {"acct_a": reader("acct_a", [xrd.ReaderFailure("parse")])}, src, symbol="ETH")
    assert out.reason == "drift" and pool.stopped_reason() is None


def test_canary_must_pass_before_units():
    clock, pool, src = setup()
    a, b = reader("acct_a", day_pages()), reader("acct_b")
    out = unit(pool, {"acct_a": a, "acct_b": b}, src)
    assert out.reason == "canary_pending" and a.calls == [] and src.used == 0
    tws = tweets(20, xp.canary_window(T0)[1] - timedelta(minutes=1), 2, "bitcoin")
    a.items, b.items = [page(tws)], [page(tws)]
    assert xp.run_daily_canary(pool, {"acct_a": a, "acct_b": b}, src, cfg(), rng=random.Random(1),
                               sleep=lambda s: None).passed
    assert src.used == 40  # canary reads count against the daily budget
    clock.advance(minutes=10)
    a.items = day_pages()
    assert unit(pool, {"acct_a": a, "acct_b": b}, src).result is not None
    clock.advance(days=1)
    assert unit(pool, {"acct_a": a, "acct_b": b}, src).reason == "canary_pending"


def test_canary_below_min_results_pauses_day_empty_results():
    _, pool, src = setup()
    tws = tweets(5, xp.canary_window(T0)[1] - timedelta(minutes=1), 2, "bitcoin")
    out = xp.run_daily_canary(pool, {"acct_a": reader("acct_a", [page(tws)]), "acct_b": reader("acct_b", [page(tws)])},
                              src, cfg(), rng=random.Random(1), sleep=lambda s: None)
    assert not out.passed and pool.pause_reason() == "empty_results"


# --- AC49 selection and ban handling -------------------------------------------------------------------------

def test_pool_selection_least_recently_used_ties_by_registration_order_not_alphabetical():
    clock, pool, _ = setup(("zeta", "alpha", "mid"))
    assert pool.select().label == "zeta"  # nobody used: registration order, not alphabetical
    pool.mark_used("zeta")
    clock.advance(minutes=5)
    assert pool.select().label == "alpha"
    pool.mark_used("alpha")
    clock.advance(minutes=5)
    assert pool.select().label == "mid"
    pool.mark_used("mid")
    clock.advance(minutes=5)
    assert pool.select().label == "zeta"  # least recently used


def test_pool_selection_deterministic_and_logged_by_label():
    picks = []
    for _ in range(2):
        reset_state()
        clock, pool, _src = setup(("acct_b", "acct_a"))
        seq = []
        for _i in range(4):
            sel = pool.select()
            seq.append(sel.label)
            pool.mark_used(sel.label)
            clock.advance(minutes=5)
        picks.append(seq)
        assert pool.log[0] == "x pool: selected acct_b (least recently used; tie by registration order)"
        assert all(line.startswith("x pool: selected acct_") for line in pool.log)
    assert picks[0] == picks[1] == ["acct_b", "acct_a", "acct_b", "acct_a"]


def test_our_pool_state_persisted_and_survives_restart():
    clock, pool, _ = setup()
    pool.mark_used("acct_a")
    pool.lock_for_day("acct_b")
    again = xp.XPool(["acct_a", "acct_b"], clock=clock)
    assert again.account_state("acct_b") == ("locked", "rate_limited")
    assert again.select().label == "acct_a"


def test_ban_code_marks_one_account_inactive_pool_continues():
    clock, pool, src = setup()
    pass_canary(pool)
    a = reader("acct_a", [xrd.ReaderFailure("no_account")], inactive_row("(326) Authorization: Denied"))
    b = reader("acct_b", day_pages() + day_pages())
    out = unit(pool, {"acct_a": a, "acct_b": b}, src)
    assert out.result is not None and out.label == "acct_b"
    assert pool.account_state("acct_a") == ("inactive", "x_account_suspended")
    assert pool.alerts()[0]["label"] == "acct_a" and not pool.is_paused()
    clock.advance(minutes=10)
    out2 = unit(pool, {"acct_a": a, "acct_b": b}, src, symbol="ETH")
    assert out2.label == "acct_b" and len(a.calls) == 1


def test_zero_active_accounts_pauses_day_units_missing_never_zero():
    _, pool, src = setup()
    pass_canary(pool)
    pool.mark_inactive("acct_a", "x_login_required")
    pool.mark_inactive("acct_b", "x_account_suspended")
    out = unit(pool, {"acct_a": reader("acct_a"), "acct_b": reader("acct_b")}, src)
    assert out.result is None and out.reason == "no_usable_account"
    assert pool.pause_reason() == "no_usable_account" and src.used == 0
    assert pool.health()["active"] == 0 and pool.health()["total"] == 2


def test_rate_limit_lock_ends_at_day_boundary_not_inactive():
    clock, pool, src = setup()
    pass_canary(pool)
    locked = xrd.PoolRow(True, None, {"SearchTimeline": T0 + timedelta(minutes=15)}, T0)
    a = reader("acct_a", [xrd.ReaderFailure("no_account")], locked)
    out = unit(pool, {"acct_a": a, "acct_b": reader("acct_b", day_pages())}, src)
    assert out.label == "acct_b" and out.restarts == 1
    assert pool.account_state("acct_a") == ("locked", "rate_limited") and pool.alerts() == []
    clock.advance(hours=1)  # the library's own lock is long gone; ours lasts the UTC day
    assert pool.account_state("acct_a")[0] == "locked"
    clock.now = datetime(2026, 10, 21, 23, 59, 59, tzinfo=timezone.utc)
    assert pool.account_state("acct_a")[0] == "locked"
    clock.now = datetime(2026, 10, 22, tzinfo=timezone.utc)
    assert pool.account_state("acct_a") == ("active", None)


def test_all_accounts_locked_pauses_day():
    _, pool, src = setup()
    pass_canary(pool)
    pool.lock_for_day("acct_a")
    pool.lock_for_day("acct_b")
    out = unit(pool, {"acct_a": reader("acct_a"), "acct_b": reader("acct_b")}, src)
    assert out.reason == "no_usable_account" and pool.pause_reason() == "no_usable_account"


# --- AC50 unit integrity -------------------------------------------------------------------------------------

def test_one_unit_one_account_end_to_end_label_in_evidence_no_cookies():
    _, pool, src = setup()
    pass_canary(pool)
    a, b = reader("acct_a", day_pages()), reader("acct_b", day_pages())
    out = unit(pool, {"acct_a": a, "acct_b": b}, src)
    assert out.label == "acct_a" and len(a.calls) == 2 and b.calls == []
    row = xr.read_x_rows("SOL")[0]
    assert (row["account"], row["attempts"], row["restarts"]) == ("acct_a", 1, 0)
    text = repr(row).lower()
    assert "auth_token" not in text and "ct0" not in text and "cookie" not in text


def test_ban_mid_unit_restarts_on_another_account_without_double_count():
    _, pool, src = setup()
    pass_canary(pool)
    first = day_pages()
    a = reader("acct_a", [first[0], xrd.ReaderFailure("no_account")], inactive_row("(32) Could not authenticate you"))
    b = reader("acct_b", day_pages())
    out = unit(pool, {"acct_a": a, "acct_b": b}, src)
    assert out.label == "acct_b" and (out.attempts, out.restarts) == (2, 1)
    row = xr.read_x_rows("SOL")[0]
    assert row["n_read"] == 40 and row["n_counted"] == 40  # aborted attempt's 20 tweets never merged
    assert row["account"] == "acct_b" and row["restarts"] == 1


def test_aborted_attempt_reads_count_against_global_budget():
    _, pool, src = setup()
    pass_canary(pool)
    first = day_pages()
    a = reader("acct_a", [first[0], xrd.ReaderFailure("no_account")], inactive_row(None))
    out = unit(pool, {"acct_a": a, "acct_b": reader("acct_b", day_pages())}, src)
    assert out.result is not None and src.used == 60 and out.reads == 60


def test_second_failure_gives_account_failed_missing():
    _, pool, src = setup(("acct_a", "acct_b", "acct_c"))
    pass_canary(pool)
    locked = xrd.PoolRow(True, None, {"SearchTimeline": T0 + timedelta(minutes=15)}, T0)
    a = reader("acct_a", [xrd.ReaderFailure("no_account")], locked)
    b = reader("acct_b", [xrd.ReaderFailure("no_account")], locked)
    c = reader("acct_c", day_pages())
    out = unit(pool, {"acct_a": a, "acct_b": b, "acct_c": c}, src)
    assert out.result is None and out.reason == "account_failed" and (out.attempts, out.restarts) == (2, 1)
    assert c.calls == [] and xr.read_x_rows("SOL") == []


# --- AC51 cross-account canary ---------------------------------------------------------------------------------

def _canary(pool, src, results: dict[str, list[xf.Tweet]], config=None):
    readers = {label: reader(label, [page(tws)]) for label, tws in results.items()}
    return xp.run_daily_canary(pool, readers, src, config or cfg(), rng=random.Random(1), sleep=lambda s: None)


def _hour_tweets(n: int, prefix: str = "bitcoin") -> list[xf.Tweet]:
    return tweets(n, xp.canary_window(T0)[1] - timedelta(seconds=30), 2, prefix)


def test_cross_account_canary_agree_passes():
    _, pool, src = setup()
    tws = _hour_tweets(20)
    out = _canary(pool, src, {"acct_a": tws, "acct_b": tws[:16] + _hour_tweets(2)})
    assert out.passed and out.suspects == [] and pool.canary_passed_today()
    assert xp.compare_canary({"a": set(range(20)), "b": set(range(5, 21))}, ["a", "b"], 0.25, 0.6) == ([], False)
    # Boundaries: exactly 25 percent apart agrees; overlap is measured on the SMALLER set (10 of 16 = 0.625).
    assert xp.compare_canary({"a": set(range(20)), "b": set(range(5, 20))}, ["a", "b"], 0.25, 0.6) == ([], False)
    assert xp.compare_canary({"a": set(range(20)), "b": set(range(10)) | set(range(100, 106))}, ["a", "b"],
                             0.25, 0.6) == ([], False)
    assert xp.compare_canary({"a": set(range(20)), "b": set(range(9)) | set(range(100, 107))}, ["a", "b"],
                             0.25, 0.6) == (["b"], False)


def test_cross_account_canary_disagree_flags_smaller_account_suspect():
    _, pool, src = setup()
    tws = _hour_tweets(20)
    out = _canary(pool, src, {"acct_a": tws, "acct_b": tws[:12]})  # 12 vs 20: 40 percent apart
    assert out.passed and out.suspects == ["acct_b"]
    assert pool.account_state("acct_b") == ("suspect", "x_account_suspect")
    assert {"label": "acct_b", "reason": "x_account_suspect", "at": T0.isoformat()} in pool.alerts()
    # Same counts but low overlap and no smaller side: inconclusive, the day pauses (fail closed).
    assert xp.compare_canary({"a": set(range(20)), "b": set(range(100, 120))}, ["a", "b"], 0.25, 0.6) == ([], True)
    # Equal-sized sets: overlap of the smaller set uses that size.
    assert xp.compare_canary({"a": set(range(10)), "b": set(range(4, 14))}, ["a", "b"], 0.25, 0.6) == ([], False)


def test_canary_majority_of_three_decides():
    _, pool, src = setup(("acct_a", "acct_b", "acct_c"))
    tws = _hour_tweets(20)
    out = _canary(pool, src, {"acct_a": tws, "acct_b": tws[:7], "acct_c": tws[1:]})
    assert out.suspects == ["acct_b"] and out.passed
    order = ["a", "b", "c"]
    assert xp.compare_canary({"a": set(range(20)), "b": set(range(20)), "c": set(range(20))}, order, .25, .6) == (
        [], False)
    assert xp.compare_canary({"a": set(range(20)), "b": set(range(50, 60)), "c": set(range(80, 83))}, order,
                             .25, .6) == ([], True)


def test_canary_inconclusive_pauses_day():
    _, pool, src = setup()
    out = _canary(pool, src, {"acct_a": _hour_tweets(20), "acct_b": _hour_tweets(20)})
    assert not out.passed and pool.pause_reason() == "canary_disagree" and out.suspects == []


def test_suspect_account_excluded_and_earlier_units_flagged_suspect_since():
    clock, pool, src = setup()
    pass_canary(pool)
    assert unit(pool, {"acct_a": reader("acct_a", day_pages()), "acct_b": reader("acct_b")}, src).label == "acct_a"
    clock.advance(days=1)
    tws = tweets(20, xp.canary_window(clock.now)[1] - timedelta(seconds=30), 2, "bitcoin")
    out = xp.run_daily_canary(pool, {"acct_a": reader("acct_a", [page(tws[:10])]), "acct_b": reader("acct_b", [page(tws)])},
                              src, cfg(), rng=random.Random(1), sleep=lambda s: None)
    assert out.suspects == ["acct_a"]
    assert xr.read_x_rows("SOL")[0]["suspect_since"] == clock.now.isoformat()
    for _ in range(3):
        assert pool.select().label == "acct_b"
        pool.mark_used("acct_b")
        clock.advance(minutes=5)
    pool.owner_clear("acct_a")
    assert pool.account_state("acct_a") == ("active", None)


def test_single_account_skips_comparison_and_health_says_so():
    _, pool, src = setup(("acct_a",))
    out = _canary(pool, src, {"acct_a": _hour_tweets(20)})
    assert out.passed and pool.health()["canary_note"] == "comparison skipped: single active account"


def test_canary_uses_two_least_recently_canaried_accounts():
    clock, pool, _ = setup(("acct_a", "acct_b", "acct_c", "acct_d"))
    assert pool.canary_accounts() == ["acct_a", "acct_b", "acct_c"]  # three or more: a majority of three
    pool.mark_canaried(["acct_a", "acct_b", "acct_c"])
    clock.advance(days=1)
    assert pool.canary_accounts() == ["acct_d", "acct_a", "acct_b"]
    reset_state()
    _, pool2, _ = setup(("acct_a", "acct_b"))
    assert pool2.canary_accounts() == ["acct_a", "acct_b"]


# --- AC52 global budget and spacing; no reset of library locks ---------------------------------------------------

def test_budget_and_spacing_global_across_pool():
    clock, pool, src = setup(budget=100)
    pass_canary(pool)
    readers = {"acct_a": reader("acct_a", day_pages() * 3), "acct_b": reader("acct_b", day_pages() * 3)}
    labels = []
    for i in range(3):
        out = unit(pool, readers, src, symbol=f"C{i}")
        labels.append(out.label)
        assert unit(pool, readers, src, symbol="ETH").reason == "too_early"  # spacing is global
        clock.advance(seconds=cfg().x_query_delay_min_s)
    # Two accounts together never read more than the one global budget: the third unit stops at 100.
    assert labels == ["acct_a", "acct_b", "acct_a"] and src.used == 100
    assert len(readers["acct_a"].calls) + len(readers["acct_b"].calls) == 5


def test_no_reset_locks_and_library_lock_never_cleared():
    _, pool, _ = setup()
    assert not hasattr(pool, "reset_locks")
    r = reader("acct_a")
    assert not hasattr(r, "reset_locks")


# --- AC54 read accounting and parse-drop guard ------------------------------------------------------------------

def test_read_accounting_from_search_raw_pages_and_entries_not_parsed_counts():
    _, pool, src = setup()
    pass_canary(pool)
    pages_ = day_pages()
    # Parsed count can differ from the entries (a conversation module holds two tweets): reads count entries.
    extra = tweets(1, END - timedelta(hours=8))
    big = xrd.RawPage(body={"entries": pages_[1].body["entries"] + [xrd.FakeXReader.entry(extra[0])]},
                      entry_ids=pages_[1].entry_ids, rate_limit_remaining=38, rate_limit_limit=50)
    out = unit(pool, {"acct_a": reader("acct_a", [pages_[0], big]), "acct_b": reader("acct_b")}, src)
    assert out.reads == 40 and src.used == 40
    row = xr.read_x_rows("SOL")[0]
    assert row["n_read"] == 40 and (row["rate_limit_remaining"], row["rate_limit_limit"]) == (38, 50)


def test_retries_counted_as_extra_pages_and_setup_overhead_recorded():
    _, pool, src = setup()
    pass_canary(pool)
    tws = tweets(40, END - timedelta(minutes=1))
    pages_ = [page(tws[:20], retries=2), page(tws[20:])]
    a = reader("acct_a", pages_)
    a.overhead_requests = 5
    out = unit(pool, {"acct_a": a, "acct_b": reader("acct_b")}, src)
    row = xr.read_x_rows("SOL")[0]
    assert out.pages == 4 and row["pages"] == 4 and row["overhead_requests"] == 5


def test_parse_drop_page_with_entries_and_zero_parsed_is_layout_changed():
    _, pool, src = setup()
    pass_canary(pool)
    tws = tweets(20, END - timedelta(minutes=1))
    out = unit(pool, {"acct_a": reader("acct_a", [page(tws, broken=20)]), "acct_b": reader("acct_b")}, src)
    assert out.reason == "layout_changed" and pool.stopped_reason() == "layout_changed"
    assert xr.read_pages("SOL", DAY)[0]["entries"] == 20  # the raw page is archived with the dropped entries
    assert xrd.parse_drop(entries=2, parsed=0, threshold=1.0)  # several entries, none parsed
    assert xrd.parse_drop(entries=2, parsed=0, threshold=0.2) and not xrd.parse_drop(entries=1, parsed=0,
                                                                                       threshold=1.0)


def test_parse_drop_rate_above_threshold_is_layout_changed():
    assert not xrd.parse_drop(entries=20, parsed=16, threshold=0.2)  # 0.2 is not above
    assert xrd.parse_drop(entries=20, parsed=15, threshold=0.2)
    assert not xrd.parse_drop(entries=20, parsed=21, threshold=0.2)
    assert not xrd.parse_drop(entries=0, parsed=0, threshold=0.2)
    _, pool, src = setup()
    pass_canary(pool)
    tws = tweets(40, END - timedelta(minutes=1))
    out = unit(pool, {"acct_a": reader("acct_a", [page(tws[:20], broken=3), page(tws[20:], broken=6)]),
                      "acct_b": reader("acct_b")}, src)
    assert out.reason == "layout_changed"  # page 1 drops 3 of 20 (0.15), page 2 drops 6 of 20 (0.3 > 0.2)
    assert xr.read_pages("SOL", DAY)[1]["entries"] == 20


# --- AC55 environment guard (pure decision over a dict) -----------------------------------------------------------

GOOD_ENV = {"TWS_TELEMETRY": "0", "DO_NOT_TRACK": "1", "TWS_LOG_LEVEL": "WARNING", "TWS_RAISE_WHEN_NO_ACCOUNT": "1",
            "PATH": "/usr/bin"}


def test_env_guard_refuses_start_for_each_variable():
    assert xrd.env_problems(GOOD_ENV) == []
    assert xrd.env_problems({**GOOD_ENV, "TWS_LOG_LEVEL": "error"}) == []
    bad = {
        "TWS_TELEMETRY": {**GOOD_ENV, "TWS_TELEMETRY": "1"},
        "DO_NOT_TRACK": {k: v for k, v in GOOD_ENV.items() if k != "DO_NOT_TRACK"},
        "TWS_LOG_LEVEL": {**GOOD_ENV, "TWS_LOG_LEVEL": "DEBUG"},
        "TWS_RAISE_WHEN_NO_ACCOUNT": {**GOOD_ENV, "TWS_RAISE_WHEN_NO_ACCOUNT": "0"},
        "TWS_PROXY": {**GOOD_ENV, "TWS_PROXY": "x"},
        "HTTP_PROXY": {**GOOD_ENV, "HTTP_PROXY": "x"},
        "HTTPS_PROXY": {**GOOD_ENV, "HTTPS_PROXY": "x"},
        "https_proxy": {**GOOD_ENV, "https_proxy": "x"},
        "TWS_HTTP_BACKEND": {**GOOD_ENV, "TWS_HTTP_BACKEND": "curl"},
    }
    for name, env in bad.items():
        assert xrd.env_problems(env) == [name], name
    assert xrd.env_problems({**GOOD_ENV, "TWS_HTTP_BACKEND": "curl"}, fallback_process=True) == []
    assert xrd.env_problems(GOOD_ENV, fallback_process=True) == ["TWS_HTTP_BACKEND"]
    assert xrd.env_problems({**GOOD_ENV, "TWS_HTTP_BACKEND": "httpx"}, fallback_process=True) == ["TWS_HTTP_BACKEND"]
    # Only names are reported, never values.
    assert not [p for p in xrd.env_problems({**GOOD_ENV, "TWS_PROXY": "secret"}) if "secret" in p]
