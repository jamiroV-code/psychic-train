"""W8d1 AC41, AC46, AC49-AC55: X reader seam, fail-closed mapping, account pool, unit integrity, canary,
global budget, read accounting, parse-drop guard, curl fallback decision and the environment guard.

Fake readers and fake raw pages only; nothing from the X library is imported; no network. Injected clock.
"""
from __future__ import annotations

import json
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


def pass_canary(pool, labels=None):
    """Today's canary passed on `labels` (default: every configured account)."""
    pool.set_canary_passed(note="test", labels=pool.labels if labels is None else labels)


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
        "short_result": [page(tweets(5, END - timedelta(minutes=1 + 5 * i), 1)) for i in range(3)],  # page cap
        "window_not_reached": [page(tweets(20, END + timedelta(hours=2), 1))] * 3,  # all after the window end
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

    def cause(row, evidence=False):
        return xrd.no_account_cause(row, now, rate_limit_evidence=evidence)

    assert cause(inactive_row("(88) Rate limit exceeded")) == ("inactive", "x_account_suspended")
    assert cause(inactive_row("(326) Authorization: Denied by access control")) == ("inactive", "x_account_suspended")
    assert cause(inactive_row("(32) Could not authenticate you")) == ("inactive", "x_login_required")
    assert cause(inactive_row(None)) == ("inactive", "x_login_required")  # bare 403
    locked = xrd.PoolRow(True, None, {"SearchTimeline": now + timedelta(minutes=9)}, now)
    assert cause(locked, evidence=True) == ("locked", "rate_limited")  # our side saw the rate limit
    assert cause(locked) == ("waiting", "in_flight_lock")  # a bare library lock: at most 15 minutes, never a day
    coded = xrd.PoolRow(True, "(88) Rate limit exceeded", {"SearchTimeline": now + timedelta(minutes=9)}, now)
    assert cause(coded) == ("locked", "rate_limited")  # an active row carrying the rate-limit code is evidence
    longer = xrd.PoolRow(True, None, {"SearchTimeline": now + timedelta(minutes=30)}, now)
    assert cause(longer) == ("locked", "rate_limited")  # longer than an in-flight lock can be
    stale = xrd.PoolRow(True, None, {"SearchTimeline": now - timedelta(minutes=1)}, now)
    assert cause(stale) == ("server_error", "failed")
    other_queue = xrd.PoolRow(True, "(130) Over capacity", {"UserByScreenName": now + timedelta(hours=1)}, now)
    assert cause(other_queue) == ("server_error", "failed")


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


def test_blocked_by_html_flag_false_pauses_day_no_fallback():
    _, pool, src = setup()
    pass_canary(pool)
    calls = []
    a = reader("acct_a", [xrd.ReaderFailure("abort", text="Blocked by HTML")])
    out = unit(pool, {"acct_a": a, "acct_b": reader("acct_b")}, src,
               fallback=lambda *args: calls.append(args))
    assert out.reason == "html_block" and pool.pause_reason() == "html_block" and calls == []


def test_blocked_by_html_flag_true_retries_once_in_fallback():
    """T179 (owner, 24-10-26): an HTML block on the default backend also triggers the one fallback retry."""
    _, pool, src = setup(("acct_a",))
    pass_canary(pool)
    pages_ = day_pages()
    calls = []

    def fallback(label, query, kv, page_no):
        calls.append((label, page_no))
        return pages_[0]

    a = reader("acct_a", [xrd.ReaderFailure("abort", text="Blocked by HTML (403)"), pages_[1]])
    out = unit(pool, {"acct_a": a}, src, config=cfg(x_allow_curl_backend=True), fallback=fallback)
    assert out.result is not None and calls == [("acct_a", 0)]
    assert out.row["backend_events"] == [{"backend": "curl", "reason": "html_block", "outcome": "ok"}]
    assert pool.health()["curl_uses"] == 1


def test_blocked_by_html_still_blocked_in_fallback_pauses_day():
    _, pool, src = setup()
    pass_canary(pool)

    def still(*args):
        raise xrd.ReaderFailure("abort", text="Blocked by HTML")

    a = reader("acct_a", [xrd.ReaderFailure("abort", text="Blocked by HTML")])
    out = unit(pool, {"acct_a": a, "acct_b": reader("acct_b", day_pages())}, src,
               config=cfg(x_allow_curl_backend=True), fallback=still)
    assert out.reason == "html_block" and pool.pause_reason() == "html_block" and out.restarts == 0


def test_curl_fallback_decision_table():
    d = xrd.fallback_decision
    assert d("cloudflare", allow_curl=True, retried=False) == "curl_retry"
    assert d("cloudflare", allow_curl=True, retried=True) == "pause_day"
    assert d("cloudflare", allow_curl=False, retried=False) == "pause_day"
    assert d("html", allow_curl=True, retried=False) == "curl_retry"
    assert d("html", allow_curl=True, retried=True) == "pause_day"
    assert d("html", allow_curl=False, retried=False) == "pause_day"
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

    # Next unit: default backend first again; the day's one curl retry is spent, so the block pauses the day.
    clock.advance(minutes=10)
    calls.clear()
    a.items = [xrd.ReaderFailure("abort", text="Blocked by Cloudflare")]
    out2 = unit(pool, {"acct_a": a}, src, config=cfg(x_allow_curl_backend=True), fallback=fallback, symbol="ETH")
    assert a.calls[-1][2] == 0  # the default reader was called first for the new unit
    assert out2.reason == "cloudflare_block" and pool.pause_reason() == "cloudflare_block" and calls == []
    assert pool.health()["curl_uses"] == 1
    # The next UTC day has its own one retry.
    clock.now = datetime(2026, 10, 22, 10, 0, tzinfo=timezone.utc)
    pass_canary(pool)
    a.items = [xrd.ReaderFailure("abort", text="Blocked by Cloudflare"), day_pages()[1]]
    out3 = unit(pool, {"acct_a": a}, src, config=cfg(x_allow_curl_backend=True), fallback=fallback,
                symbol="ADA", day=date(2026, 10, 21))
    assert calls == [("acct_a", 0)] and out3.reason != "cloudflare_block" and pool.health()["curl_uses"] == 2


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
    a = reader("acct_a", [xrd.ReaderFailure("no_account", status=429)], locked)  # rate-limit evidence: HTTP 429
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
    a = reader("acct_a", [xrd.ReaderFailure("no_account", status=429)], locked)
    b = reader("acct_b", [xrd.ReaderFailure("no_account", status=429)], locked)
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


def test_canary_inconclusive_locks_those_accounts_for_the_day_pool_continues():
    """Planner default QA: the canaried accounts sit out the UTC day (not suspect); other accounts continue."""
    clock, pool, src = setup(("acct_a", "acct_b", "acct_c", "acct_d"))
    out = _canary(pool, src, {"acct_a": _hour_tweets(20), "acct_b": _hour_tweets(10), "acct_c": _hour_tweets(3)})
    assert out.passed and out.suspects == [] and out.reason == "canary_disagree"
    assert [pool.account_state(x)[0] for x in ("acct_a", "acct_b", "acct_c")] == ["locked"] * 3
    assert pool.account_state("acct_d") == ("active", None) and not pool.is_paused()
    assert pool.health()["canary_note"] == "inconclusive: acct_a, acct_b, acct_c sit out the day"
    assert pool.select().label == "acct_d"
    clock.now = datetime(2026, 10, 22, tzinfo=timezone.utc)
    assert pool.account_state("acct_a") == ("active", None)  # not suspect: back the next day


def test_canary_inconclusive_with_two_accounts_leaves_no_usable_account_and_pauses_day():
    _, pool, src = setup()
    out = _canary(pool, src, {"acct_a": _hour_tweets(20), "acct_b": _hour_tweets(20)})
    assert not out.passed and out.suspects == [] and pool.pause_reason() == "canary_disagree"
    assert pool.account_state("acct_a")[0] == pool.account_state("acct_b")[0] == "locked"
    assert pool.alerts() == []


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


# --- T187 review fixes (M2, M3) ---------------------------------------------------------------------------------

def _sparse(items):
    reset_state()
    _, pool, src = setup(("acct_a",))
    pass_canary(pool)
    return unit(pool, {"acct_a": reader("acct_a", items)}, src)


def test_sparse_coin_window_reached_on_first_page_is_exact_below_n_min():
    tws = tweets(3, END - timedelta(hours=2), 60) + tweets(1, END - timedelta(days=1, minutes=5))
    out = _sparse([page(tws)])
    assert out.reason == "window_start" and (out.result.value, out.result.capped) == (3.0, False)
    assert xr.read_x_rows("SOL")[0]["value"] == 3.0


def test_cursor_exhausted_exactly_at_window_start_is_exact():
    tws = tweets(4, END - timedelta(hours=6), 60)
    tws.append(xf.Tweet(next(_ids), END - timedelta(days=1), "Solana at the start", tws[0].user, "en", ("SOL",)))
    out = _sparse([page(tws), page([])])
    assert out.reason == "cursor_exhausted" and out.result.value == 5.0  # the 00:00 tweet is inside the window
    row = xr.read_x_rows("SOL")[0]
    assert row["stop"] == "cursor_exhausted" and row["pages"] == 2


def test_empty_or_none_first_page_with_canary_is_an_exact_zero():
    for first in ([page([])], [None]):
        out = _sparse(first)
        assert out.reason == "cursor_exhausted" and out.result.value == 0.0 and not out.result.capped
        assert xr.read_x_rows("SOL")[0]["value"] == 0.0


def test_canary_window_is_the_last_hour_of_the_previous_utc_day():
    start, end = xp.canary_window(T0)
    assert end == datetime(2026, 10, 21, tzinfo=timezone.utc) and end - start == timedelta(hours=1)
    assert xp.canary_window(datetime(2026, 10, 21, 23, 59, tzinfo=timezone.utc)) == (start, end)


def test_canary_query_both_syntaxes_cover_the_fixed_past_hour():
    start, end = xp.canary_window(T0)
    assert xp.canary_query(cfg(), start, end) == (
        f"bitcoin since_time:{int(start.timestamp())} until_time:{int(end.timestamp())}")
    assert xp.canary_query(cfg(x_window_syntax="date"), start, end) == "bitcoin since:2026-10-20 until:2026-10-21"


def test_canary_with_date_syntax_passes_on_the_last_hour_tweets():
    _, pool, src = setup()
    tws = tweets(20, xp.canary_window(T0)[1] - timedelta(seconds=30), 2, "bitcoin")
    readers = {x: reader(x, [page(tws)]) for x in ("acct_a", "acct_b")}
    out = xp.run_daily_canary(pool, readers, src, cfg(x_window_syntax="date"), rng=random.Random(1),
                              sleep=lambda s: None)
    assert out.passed and readers["acct_a"].calls[0][0] == "bitcoin since:2026-10-20 until:2026-10-21"


# --- T190 review fixes (B-1, M-A, L1-L6) -------------------------------------------------------------------------

def _run(items, *, canaried=("acct_a",), labels=("acct_a",), config=None, fallback=None, names=()):
    reset_state()
    _, pool, src = setup(labels)
    pass_canary(pool, list(canaried))
    readers = {x: reader(x, items if x == labels[0] else ()) for x in labels}
    readers[labels[0]].account_names = tuple(names)
    return unit(pool, readers, src, config=config, fallback=fallback), pool, readers


def test_full_page_then_none_is_a_stalled_cursor_capped_never_exact():
    tws = tweets(20, END - timedelta(minutes=1), 0.5)  # 20 entries over 10 minutes
    for tail in (None, page([])):
        out, _, _ = _run([page(tws), tail])
        assert out.reason == "cursor_stalled" and out.result.capped and out.result.n == 20
        span = max((END - tws[-1].date).total_seconds() / 3600, 0.25)
        assert out.result.value == pytest.approx(24 * 20 / span) and out.result.value > 20
        row = xr.read_x_rows("SOL")[0]
        assert row["stop"] == "cursor_stalled" and row["value"] == pytest.approx(out.result.value)


def test_full_page_then_none_below_n_min_is_missing_cursor_stalled():
    tws = tweets(20, END - timedelta(minutes=1), 0.5)
    out, _, _ = _run([page(tws), None], config=cfg(x_sample_min=30, x_sample_n=40))
    assert out.result is None and out.reason == "cursor_stalled" and xr.read_x_rows("SOL") == []


def test_short_last_page_then_none_is_exhausted_and_exact():
    out, _, _ = _run([page(tweets(19, END - timedelta(minutes=1), 30)), None])
    assert out.reason == "cursor_exhausted" and (out.result.value, out.result.capped) == (19.0, False)
    out, _, _ = _run([page(tweets(3, END - timedelta(hours=1), 60)), None])
    assert out.reason == "cursor_exhausted" and out.result.value == 3.0 and out.row["value"] == 3.0


def test_full_page_then_repeated_ids_is_a_stalled_cursor_without_double_count():
    tws = tweets(20, END - timedelta(minutes=1), 0.5)
    out, _, _ = _run([page(tws), page(tws), None])
    assert out.reason == "cursor_stalled" and out.result.n == 20 and out.reads == 40  # read twice, counted once
    row = xr.read_x_rows("SOL")[0]
    assert (row["n_counted"], row["n_read"], row["stop"]) == (20, 20, "cursor_stalled")  # the re-parse agrees


def test_exact_count_from_exhausted_cursor_needs_the_account_in_todays_canary():
    for items in ([page(tweets(3, END - timedelta(hours=1), 60)), None], [None], [page([])]):
        out, _, _ = _run(items, canaried=())
        assert out.result is None and out.reason == "account_not_canaried"
        assert xr.read_x_rows("SOL") == []
    # The unit runs on acct_a; only acct_b passed the canary (acct_a carried on after an inconclusive canary).
    out, _, _ = _run([page(tweets(3, END - timedelta(hours=1), 60)), None], canaried=("acct_b",),
                     labels=("acct_a", "acct_b"))
    assert out.label == "acct_a" and out.reason == "account_not_canaried"
    # Every value needs it (planner, T190): a window start and a capped sample from that account are missing too.
    tws = tweets(3, END - timedelta(hours=2), 60) + tweets(1, END - timedelta(days=1, minutes=5))
    out, _, _ = _run([page(tws)], canaried=())
    assert out.result is None and out.reason == "account_not_canaried"
    out, _, _ = _run(day_pages(), canaried=())
    assert out.result is None and out.reason == "account_not_canaried" and xr.read_x_rows("SOL") == []
    out, _, _ = _run(day_pages(), canaried=("acct_a",))
    assert out.result.capped and out.row["canary_ok"] is True


def test_canary_records_the_labels_that_passed():
    clock, pool, src = setup(("acct_a", "acct_b"))
    tws = _hour_tweets(20)
    assert _canary(pool, src, {"acct_a": tws, "acct_b": tws}).passed
    assert pool.canary_labels() == ["acct_a", "acct_b"]
    assert xp.XPool(["acct_a", "acct_b"], clock=clock).canary_labels() == ["acct_a", "acct_b"]  # persisted
    clock.advance(days=1)
    assert pool.canary_labels() == []  # yesterday's canary is no evidence today
    clock.advance(days=-1)
    reset_state()
    _, pool, src = setup(("acct_a", "acct_b"))
    out = _canary(pool, src, {"acct_a": tws, "acct_b": tws[:12]})
    assert out.suspects == ["acct_b"] and pool.canary_labels() == ["acct_a"]
    reset_state()
    _, pool, src = setup(("acct_a", "acct_b", "acct_c", "acct_d"))
    out = _canary(pool, src, {"acct_a": _hour_tweets(20), "acct_b": _hour_tweets(10), "acct_c": _hour_tweets(3)})
    assert out.reason == "canary_disagree" and pool.canary_labels() == []  # acct_d continues, not canaried
    clock = pool.clock
    clock.advance(days=1)
    assert pool.canary_labels() == []  # yesterday's canary is no evidence today


def test_one_curl_retry_per_unit_then_the_next_block_pauses_the_day():
    tws = tweets(40, END - timedelta(minutes=1), 10)
    calls = []

    def fallback(label, query, kv, page_no):
        calls.append(page_no)
        return page(tws[:20])

    items = [xrd.ReaderFailure("abort", text="Blocked by Cloudflare"),
             xrd.ReaderFailure("abort", text="Blocked by HTML"), page(tws[20:])]
    out, pool, _ = _run(items, config=cfg(x_allow_curl_backend=True), fallback=fallback)
    assert calls == [0] and out.result is None and out.reason == "html_block"
    assert pool.pause_reason() == "html_block" and pool.health()["curl_uses"] == 1


CANARY_TWS = _hour_tweets(20)


def _block_canary(fallback, allow):
    reset_state()
    _, pool, src = setup(("acct_a", "acct_b"))
    tws = CANARY_TWS
    readers = {"acct_a": reader("acct_a", [xrd.ReaderFailure("abort", text="Blocked by Cloudflare")]),
               "acct_b": reader("acct_b", [page(tws)])}
    out = xp.run_daily_canary(pool, readers, src, cfg(x_allow_curl_backend=allow), rng=random.Random(1),
                              sleep=lambda s: None, fallback=fallback)
    return out, pool


def test_canary_block_goes_through_the_same_fallback_rule():
    calls = []

    def ok(label, query, kv, page_no):
        calls.append(label)
        return page(CANARY_TWS)

    out, pool = _block_canary(ok, True)
    assert out.passed and calls == ["acct_a"] and pool.health()["curl_uses"] == 1
    assert pool.canary_labels() == ["acct_a", "acct_b"]

    def still(*args):
        calls.append("still")
        raise xrd.ReaderFailure("abort", text="Blocked by Cloudflare")

    out, pool = _block_canary(still, True)
    assert not out.passed and out.reason == "cloudflare_block" and pool.pause_reason() == "cloudflare_block"
    calls.clear()
    out, pool = _block_canary(ok, False)
    assert out.reason == "cloudflare_block" and calls == [] and pool.health()["curl_uses"] == 0


def test_parse_drop_rate_only_from_ten_entries_zero_parsed_rule_kept():
    assert xrd.PARSE_DROP_RATE_MIN_ENTRIES == 10
    assert not xrd.parse_drop(entries=5, parsed=4, threshold=0.2)  # 0.2 rate on a small page: not a stop
    assert not xrd.parse_drop(entries=9, parsed=6, threshold=0.2)
    assert xrd.parse_drop(entries=10, parsed=7, threshold=0.2)
    assert xrd.parse_drop(entries=3, parsed=0, threshold=0.2) and xrd.parse_drop(entries=9, parsed=0, threshold=0.9)
    assert xrd.small_page_drop(entries=5, parsed=4) and not xrd.small_page_drop(entries=5, parsed=5)
    assert not xrd.small_page_drop(entries=10, parsed=9) and not xrd.small_page_drop(entries=5, parsed=0)


def test_small_page_drop_counts_toward_layout_changed_instead_of_stopping():
    reset_state()
    clock, pool, src = setup(("acct_a",))
    pass_canary(pool)
    for i in range(3):
        tws = tweets(5, END - timedelta(hours=1), 30)
        out = unit(pool, {"acct_a": reader("acct_a", [page(tws, broken=1)])}, src, symbol=f"C{i}")
        clock.advance(minutes=10)
        if i < 2:
            assert out.reason == "drift" and out.result is None and pool.stopped_reason() is None
    assert out.reason == "layout_changed" and pool.stopped_reason() == "layout_changed"


def test_account_screen_name_and_id_scrubbed_from_archived_pages():
    tws = tweets(3, END - timedelta(hours=1), 60, prefix="RealHandle said hi to @realhandle id 4455667788")
    out, _, _ = _run([page(tws), None], names=("RealHandle", "4455667788"))
    assert out.result is not None
    raw = str(xr.read_pages("SOL", DAY))
    assert "realhandle" not in raw.casefold() and "4455667788" not in raw and "acct_a" in raw


def test_pool_pauses_only_when_no_usable_account_remains():
    reset_state()
    clock, pool, src = setup(("acct_a", "acct_b"))
    pass_canary(pool)
    pool.mark_inactive("acct_a", "x_login_required")
    assert pool.usable() == ["acct_b"]
    out = unit(pool, {"acct_a": reader("acct_a"), "acct_b": reader("acct_b", day_pages())}, src)
    assert out.label == "acct_b" and out.result is not None and not pool.is_paused()  # 1 usable: continues
    pool.mark_inactive("acct_b", "x_account_suspended")
    clock.advance(minutes=10)
    out = unit(pool, {"acct_a": reader("acct_a"), "acct_b": reader("acct_b")}, src, symbol="ETH")
    assert out.reason == "no_usable_account" and pool.pause_reason() == "no_usable_account"  # 0 usable: pause


def test_unit_takes_the_oldest_read_from_raw_entry_times():
    tws = tweets(40, END - timedelta(minutes=1), 5)
    older = END - timedelta(hours=10)  # a raw entry the parser could not read (its time is exposed raw)
    p2 = page(tws[20:])
    p2 = xrd.RawPage(p2.body, p2.entry_ids, 40, 50, 0, p2.entry_times + (older,))
    out, _, _ = _run([page(tws[:20]), p2])
    assert out.reason == "sample" and out.result.span_hours == pytest.approx(10.0)
    assert out.row["span_hours"] == pytest.approx(10.0)


def test_pool_state_from_before_canary_labels_loads_with_no_account_canaried():
    clock, pool, _ = setup()
    pass_canary(pool)
    state = json.loads(pool.path.read_text())
    del state["canary_labels"]
    pool.path.write_text(json.dumps(state))
    again = xp.XPool(["acct_a", "acct_b"], clock=clock)
    assert again.canary_passed_today() and again.canary_labels() == []


def test_one_curl_retry_per_utc_day_pool_wide_canary_then_unit():
    """Rule 19 (planner, T190): one curl retry per UTC day for the whole pool, canary and units together."""
    calls = []

    def ok(label, query, kv, page_no):
        calls.append(label)
        return page(CANARY_TWS)

    out, pool = _block_canary(ok, True)
    assert out.passed and calls == ["acct_a"]
    pool.clock.advance(minutes=10)
    src = pp.PcSource("xsearch_web", configured_budget=800, floor=40, adaptive=True, clock=pool.clock)
    a = reader("acct_a", [xrd.ReaderFailure("abort", text="Blocked by HTML")])
    got = unit(pool, {"acct_a": a, "acct_b": reader("acct_b")}, src, config=cfg(x_allow_curl_backend=True),
               fallback=ok)
    assert got.reason == "html_block" and pool.pause_reason() == "html_block" and calls == ["acct_a"]
    assert pool.health()["curl_uses"] == 1


# --- unclean stop: the library's in-flight lock is not a rate limit (restart test 30-10-26) ----------------------

NEXT_MIDNIGHT = datetime(2026, 10, 22, tzinfo=timezone.utc)


def bare_lock(until: datetime) -> xrd.PoolRow:
    """What a killed process leaves in the account file: active, no error, the 15-minute in-flight search lock."""
    return xrd.PoolRow(True, None, {"SearchTimeline": until}, T0)


@pytest.fixture
def no_day_lock(monkeypatch):
    calls = []
    real = xp.XPool.lock_for_day

    def spy(self, label):
        calls.append(label)
        real(self, label)

    monkeypatch.setattr(xp.XPool, "lock_for_day", spy)
    return calls


def test_bare_library_lock_does_not_day_lock_account(no_day_lock):
    clock, pool, src = setup()
    pass_canary(pool)
    row = bare_lock(T0 + timedelta(minutes=15))
    a = reader("acct_a", [xrd.ReaderFailure("no_account")], row)
    out = unit(pool, {"acct_a": a, "acct_b": reader("acct_b", day_pages())}, src)
    assert out.result is not None and out.label == "acct_b"
    assert no_day_lock == [] and pool.alerts() == [] and not pool.is_paused()
    assert pool.account_state("acct_a") == ("locked", "in_flight_lock")
    assert a.row is row and row.locks == {"SearchTimeline": T0 + timedelta(minutes=15)}  # library file untouched
    clock.now = T0 + timedelta(minutes=15, seconds=xp.LOCK_MARGIN_S - 1)
    assert pool.account_state("acct_a")[0] == "locked"
    clock.now = T0 + timedelta(minutes=15, seconds=xp.LOCK_MARGIN_S)  # the lock's own end, not 00:00 UTC
    assert pool.account_state("acct_a") == ("active", None)
    assert xp.XPool(["acct_a", "acct_b"], clock=clock).account_state("acct_a") == ("active", None)


def test_bare_lock_unit_waits_for_lock_end_and_resumes(no_day_lock):
    clock, pool, src = setup(("acct_a",))
    pass_canary(pool)
    a = reader("acct_a", [xrd.ReaderFailure("no_account")], bare_lock(T0 + timedelta(minutes=12)))
    out = unit(pool, {"acct_a": a}, src)
    assert out.result is None and out.reason == "in_flight_lock"  # not failed, not account_failed
    assert no_day_lock == [] and pool.pause_reason() == "in_flight_lock"
    end = T0 + timedelta(minutes=12, seconds=xp.LOCK_MARGIN_S)
    assert pool.resume_at() == end and src.used == 0
    clock.now = end - timedelta(seconds=1)
    assert pool.is_paused() and unit(pool, {"acct_a": a}, src).reason == "paused" and len(a.calls) == 1
    clock.now = end
    a.row, a.items = ACTIVE, day_pages()  # the library's lock expired by itself
    again = unit(pool, {"acct_a": a}, src)
    assert again.result is not None and again.label == "acct_a" and not pool.is_paused()
    assert len(xr.read_x_rows("SOL")) == 1 and src.used == 40


@pytest.mark.parametrize("evidence", ["code_88", "http_429", "remaining_0", "remaining_persisted"])
def test_real_rate_limit_evidence_still_day_locks_account(evidence):
    clock, pool, src = setup()
    pass_canary(pool)
    lock = {"SearchTimeline": T0 + timedelta(minutes=12)}
    row = xrd.PoolRow(True, "(88) Rate limit exceeded" if evidence == "code_88" else None, lock, T0)
    fail = xrd.ReaderFailure("no_account", status=429 if evidence == "http_429" else None)
    items = [fail]
    if evidence == "remaining_0":
        items = [page(tweets(20, END - timedelta(minutes=1)), remaining=0), fail]
    if evidence == "remaining_persisted":
        # An earlier unit on acct_a read the window down to its last request, then the process restarted.
        first = unit(pool, {"acct_a": reader("acct_a", [day_pages()[0], page(tweets(20, END - timedelta(hours=4)),
                                                                           remaining=1)])}, src, symbol="ETH")
        assert first.label == "acct_a" and first.result is not None
        clock.advance(minutes=5)
        pool = xp.XPool(["acct_a", "acct_b"], clock=clock)
        pool.mark_used("acct_b")
        clock.advance(minutes=1)
    a = reader("acct_a", items, row)
    out = unit(pool, {"acct_a": a, "acct_b": reader("acct_b", day_pages())}, src)
    assert out.label == "acct_b" and out.restarts == 1 and out.result is not None
    assert pool.account_state("acct_a") == ("locked", "rate_limited")
    clock.advance(minutes=30)  # far past the library's lock: ours lasts the UTC day
    assert pool.account_state("acct_a") == ("locked", "rate_limited")
    clock.now = NEXT_MIDNIGHT
    assert pool.account_state("acct_a") == ("active", None)


def test_failover_uses_unlocked_account_when_other_has_bare_lock(no_day_lock):
    clock, pool, src = setup()
    pass_canary(pool)
    a = reader("acct_a", [xrd.ReaderFailure("no_account")], bare_lock(T0 + timedelta(minutes=15)))
    b = reader("acct_b", day_pages() + day_pages())
    out = unit(pool, {"acct_a": a, "acct_b": b}, src)
    assert out.label == "acct_b" and (out.attempts, out.restarts) == (2, 1) and out.result is not None
    clock.advance(minutes=10)
    out2 = unit(pool, {"acct_a": a, "acct_b": b}, src, symbol="ETH")
    assert out2.label == "acct_b" and out2.restarts == 0 and len(a.calls) == 1  # acct_a still waits
    clock.advance(minutes=6)  # past the lock end and margin: acct_a is usable again, least recently used
    assert pool.usable() == ["acct_a", "acct_b"] and pool.select().label == "acct_a"
    assert no_day_lock == [] and not pool.is_paused()


def test_both_accounts_bare_locked_pass_retries_after_lock_end_not_next_day(no_day_lock):
    clock, pool, src = setup()
    pass_canary(pool)
    a = reader("acct_a", [xrd.ReaderFailure("no_account")], bare_lock(T0 + timedelta(minutes=10)))
    b = reader("acct_b", [xrd.ReaderFailure("no_account")], bare_lock(T0 + timedelta(minutes=14)))
    out = unit(pool, {"acct_a": a, "acct_b": b}, src)
    assert out.result is None and out.reason == "in_flight_lock" and out.reason != "account_failed"
    assert no_day_lock == [] and pool.pause_reason() == "in_flight_lock"
    end = T0 + timedelta(minutes=10, seconds=xp.LOCK_MARGIN_S)  # the earliest lock end, not 00:00 UTC
    assert pool.resume_at() == end and pool.health()["pause_until"] == end.isoformat()
    clock.now = end
    assert not pool.is_paused() and pool.usable() == ["acct_a"]


def test_canary_on_bare_locked_accounts_waits_for_lock_end(no_day_lock):
    clock, pool, src = setup()
    readers = {x: reader(x, [xrd.ReaderFailure("no_account")], bare_lock(T0 + timedelta(minutes=9)))
               for x in ("acct_a", "acct_b")}
    out = xp.run_daily_canary(pool, readers, src, cfg(), rng=random.Random(1), sleep=lambda s: None)
    assert not out.passed and out.reason == "in_flight_lock" and not pool.canary_passed_today()
    assert no_day_lock == [] and pool.resume_at() == T0 + timedelta(minutes=9, seconds=xp.LOCK_MARGIN_S)


def test_attempt_stamped_before_each_request():
    clock, pool, src = setup(("acct_a",))
    pass_canary(pool)
    seen = []

    class Killed(BaseException):
        pass

    class Cut(xrd.FakeXReader):
        def search_raw(self, query, kv, page_no):
            seen.append(src.last_unit_at())
            raise Killed

    with pytest.raises(Killed):
        unit(pool, {"acct_a": Cut("acct_a")}, src)
    assert seen == [T0]  # stamped before the request went out, so a kill still counts for the spacing
