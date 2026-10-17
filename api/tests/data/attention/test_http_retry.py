"""Retry, pacing, redaction and diagnostics for the attention fetchers (mock HTTP only)."""
import httpx

from api.data.attention import coingecko_attention as cg
from api.data.attention import http_retry, wikipedia
from api.scripts import refresh_attention
from api.tests.data.attention.conftest import TODAY, chart_payload, wiki_payload


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def _no_pace(monkeypatch):
    monkeypatch.setattr(cg, "PACER", http_retry.Pacer(0))
    monkeypatch.setattr(wikipedia, "PACER", http_retry.Pacer(0))


def test_429_then_200_retries_and_succeeds(monkeypatch):
    _no_pace(monkeypatch)
    calls = []

    def h(r):
        calls.append(1)
        return httpx.Response(429, headers={"Retry-After": "7"}) if len(calls) == 1 \
            else httpx.Response(200, json=chart_payload(100, include_today=False))
    sleeps = []
    s = cg.fetch_series("BTC", "bitcoin", client=_client(h), today=TODAY, sleep=sleeps.append)
    assert s.state == "ok" and len(calls) == 2
    assert 7 <= sleeps[0] < 9  # Retry-After honoured, plus jitter


def test_persistent_429_is_capped_after_three_retries(monkeypatch):
    _no_pace(monkeypatch)
    calls = []

    def h(r):
        calls.append(1)
        return httpx.Response(429)
    s = cg.fetch_series("BTC", "bitcoin", client=_client(h), today=TODAY, sleep=lambda x: None)
    assert s.state == "capped" and s.reason == "HTTP 429" and len(calls) == 4


def test_backoff_is_exponential_with_jitter(monkeypatch):
    _no_pace(monkeypatch)
    sleeps = []
    cg.fetch_series("BTC", "bitcoin", client=_client(lambda r: httpx.Response(429)), today=TODAY,
                    sleep=sleeps.append)
    assert len(sleeps) == 3 and sleeps[0] < sleeps[1] < sleeps[2]
    assert sleeps[0] >= cg.BACKOFF_BASE_SECONDS


def test_pacer_spaces_calls():
    now = [100.0]
    sleeps = []
    p = http_retry.Pacer(6.0, clock=lambda: now[0])
    p.wait(sleeps.append)
    now[0] += 2
    p.wait(sleeps.append)
    assert sleeps == [4.0]


def test_coingecko_default_pace_is_at_most_one_call_per_six_seconds():
    assert cg.MIN_INTERVAL_SECONDS >= 6.0


def test_wikipedia_sends_identifying_user_agent_and_retries_429(monkeypatch):
    _no_pace(monkeypatch)
    seen = []

    def h(r):
        seen.append(r.headers["user-agent"])
        return httpx.Response(429) if len(seen) == 1 else httpx.Response(200, json=wiki_payload(100))
    s = wikipedia.fetch_series("BTC", "Bitcoin", client=_client(h), today=TODAY, sleep=lambda x: None)
    assert s.state == "ok"
    assert "github.com" in seen[0] and "psychic-train" in seen[0]


def test_redact_hides_keys_tokens_ips_urls_and_truncates():
    raw = ("boom https://api.x.com/v3?x_cg_demo_api_key=ABC123 key=SECRET1234 Bearer abcDEF123456 "
           "from 10.1.2.3 tok AAAAAAAAAAAAAAAAAAAAAAAAAAAA café " + "z" * 300)
    out = http_retry.redact(raw)
    for bad in ("ABC123", "SECRET1234", "abcDEF123456", "10.1.2.3", "AAAAAAAAAAAAAAAA", "api.x.com", "é"):
        assert bad not in out
    assert len(out) <= 120 and out.isascii()


def test_describe_exc_has_class_status_and_redacted_message():
    req = httpx.Request("GET", "https://api.coingecko.com/x?key=abc")
    exc = httpx.HTTPStatusError("429 for https://api.coingecko.com/x?key=abc", request=req,
                                response=httpx.Response(429, request=req))
    out = http_retry.describe_exc(exc)
    assert out.startswith("HTTPStatusError") and "HTTP 429" in out and "key=abc" not in out


def test_outcome_counts_explain_the_gap():
    from api.data.attention.types import SourceSeries as S
    series = [S("w", "A", [], "ok"), S("w", "B", [], "no-article", "no article mapped"),
              S("w", "C", [], "capped", "HTTP 429"), S("w", "D", [], "unavailable", "HTTP 503"),
              S("w", "E", [], "insufficient-history", "5 days"), S("w", "F", [], "unavailable", "ConnectError"),
              S("w", "G", [], "capped", "HTTP 429")]
    assert refresh_attention.outcome_summary(series) == (
        "ok 1, no-article 1, rate-limited 2, http-error(503) 1, insufficient-history 1, other 1")


def test_main_prints_outcome_counts(tmp_path, monkeypatch, capsys):
    _no_pace(monkeypatch)
    monkeypatch.setattr(refresh_attention.store, "write_series", lambda s, today=None: 0)
    refresh_attention.main(["--sources", "wikipedia", "--symbols", "BTC,ETH"],
                           client=_client(lambda r: httpx.Response(429)), today=TODAY, sleep=lambda x: None)
    out = capsys.readouterr().out
    assert "wikipedia: 0/2 ok" in out and "rate-limited 2" in out


def test_universe_failure_prints_status_reason(monkeypatch, capsys):
    _no_pace(monkeypatch)
    rc = refresh_attention.main(["--sources", "universe"], client=_client(lambda r: httpx.Response(429)),
                                today=TODAY, sleep=lambda x: None)
    err = capsys.readouterr().err
    assert rc == 1 and "universe: error RuntimeError" in err and "HTTP 429" in err


def test_categories_failure_prints_status_reason_without_url_or_key(monkeypatch, capsys):
    _no_pace(monkeypatch)
    rc = refresh_attention.main(["--sources", "categories"], client=_client(lambda r: httpx.Response(403)),
                                today=TODAY, sleep=lambda x: None)
    err = capsys.readouterr().err
    assert rc == 1 and "categories: error RuntimeError" in err and "HTTP 403" in err
    assert "http" not in err.replace("HTTP", "")


def test_failure_message_from_exception_is_redacted(monkeypatch, capsys):
    def boom(*a, **k):
        raise RuntimeError("bad key=SECRET99 at 192.168.0.1")
    monkeypatch.setitem(refresh_attention.RUNNERS, "universe", boom)
    refresh_attention.main(["--sources", "universe"], client=_client(lambda r: httpx.Response(200)),
                           today=TODAY, sleep=lambda x: None)
    err = capsys.readouterr().err
    assert "SECRET99" not in err and "192.168.0.1" not in err and "RuntimeError" in err


def test_rate_limit_circuit_skips_rest_without_requests(monkeypatch):
    _no_pace(monkeypatch)
    calls = []

    def h(r):
        calls.append(1)
        return httpx.Response(429)
    monkeypatch.setattr(refresh_attention, "CIRCUIT_BREAKER_AFTER", 2)
    syms = [f"S{i}" for i in range(6)]
    arts = {s: s for s in syms}
    monkeypatch.setattr(refresh_attention.json, "loads", lambda t: arts)
    out = refresh_attention._run_wikipedia(syms, _client(h), TODAY, lambda x: None)
    assert [s.state for s in out] == ["capped"] * 6
    assert len(calls) == 2 * 4  # two series x (1 + 3 retries); the rest skipped
