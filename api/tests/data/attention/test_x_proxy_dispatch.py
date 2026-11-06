"""Pure B2 normal/canary/fallback typed failures preserve charges and samples."""
import random

import pytest

from api.data.attention import x_filters, x_pool as pool_module, x_reader as reader_module
from api.tests.data.attention.test_x_pool import Clock, DAY, LABELS, SOL, cfg, day_pages, reader, source, unit
from api.tests.data.attention.test_x_reader import CANARY_TWS, page


@pytest.fixture(autouse=True)
def isolated(attention_cache):
    return attention_cache


def test_midunit_proxy_failure_discards_partial_sample_charges_and_replaces_whole_unit():
    clock = Clock()
    pool, src = pool_module.XPool(LABELS, clock=clock), source(clock)
    pool.set_canary_passed(labels=LABELS)
    first, replacement = day_pages(1), day_pages(2)
    failure = reader_module.ReaderFailure("proxy", proxy_reason="proxy_revision", charged_reads=7)
    outcome = unit(pool, {LABELS[0]: reader(LABELS[0], [*first, failure]),
                          LABELS[1]: reader(LABELS[1], replacement)}, src)
    assert outcome.result is not None and outcome.restarts == 1
    assert outcome.reads == 67 and pool.reads_today(LABELS[0]) == 27 and pool.reads_today(LABELS[1]) == 40
    assert pool._acct(LABELS[0])["proxy_health"] == "quarantined"
    assert pool._acct(LABELS[0])["proxy_reason"] == "proxy_revision"
    assert pool._acct(LABELS[0])["state"] == "active"
    assert not pool.is_paused() and not src.is_paused() and pool.stopped_reason() is None


def test_canary_proxy_failure_preserves_charges_and_does_not_become_account_or_day_failure():
    clock = Clock()
    pool, src = pool_module.XPool(LABELS, clock=clock), source(clock)
    failure = reader_module.ReaderFailure("proxy", proxy_reason="proxy_transport", charged_reads=7)
    outcome = pool_module.run_daily_canary(pool,
        {LABELS[0]: reader(LABELS[0], [failure]), LABELS[1]: reader(LABELS[1], [page(CANARY_TWS)])},
        src, cfg(), rng=random.Random(1), sleep=lambda _: None)
    assert outcome.passed
    assert pool.reads_today(LABELS[0]) == 7 and pool.reads_today(LABELS[1]) == 20
    assert pool._acct(LABELS[0])["state"] == "active"
    assert pool._acct(LABELS[0])["proxy_health"] == "quarantined"
    assert LABELS[0] not in pool.canary_labels() and LABELS[1] in pool.canary_labels()
    assert not pool.is_paused() and not src.is_paused()


def test_fallback_typed_proxy_failure_never_retries_direct_or_misclassifies():
    clock = Clock()
    pool, src = pool_module.XPool(LABELS, clock=clock), source(clock)
    pool.set_canary_passed(labels=LABELS)
    calls = []
    def fallback(label, query, kv, page):
        calls.append(label)
        raise reader_module.ReaderFailure("proxy", proxy_reason="proxy_exit", charged_reads=3)
    blocked = reader_module.ReaderFailure("abort", text=reader_module.CLOUDFLARE_PREFIX)
    outcome = pool_module.run_unit(pool,
        {LABELS[0]: reader(LABELS[0], [blocked]), LABELS[1]: reader(LABELS[1], day_pages(2))}, src,
        cfg(x_allow_curl_backend=True), symbol="SOL", day=DAY,
        query='"$SOL"', coin=SOL, policy=x_filters.FilterPolicy(),
        rng=random.Random(1), sleep=lambda _: None, fallback=fallback)
    assert calls == [LABELS[0]] and outcome.result is not None and outcome.restarts == 1
    assert pool.reads_today(LABELS[0]) == 3 and pool.reads_today(LABELS[1]) == 40
    assert pool._acct(LABELS[0])["proxy_reason"] == "proxy_exit"
    assert pool._acct(LABELS[0])["state"] == "active" and not pool.is_paused()
