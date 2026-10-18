"""Wikipedia title checker (T102): fake transport only, no network, no real sleeping."""
from __future__ import annotations

import io
import json
import re
from pathlib import Path

import httpx
import pytest

from api.data.attention import wikipedia
from api.scripts import check_wiki_titles as c

DATA = Path(wikipedia.__file__).parents[1]
CANDIDATES = DATA / "wiki_articles_candidates.json"
MAPPED = DATA / "wiki_articles.json"

GOOD = {"type": "standard", "description": "Layer 1 blockchain", "extract": "Sui is a decentralized network."}


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)


def _run(mapping, handler, sleeps=None):
    out = io.StringIO()
    sleeps = [] if sleeps is None else sleeps
    res = c.run(mapping, client=_client(handler), sleep=sleeps.append, out=out)
    return res, out.getvalue()


def test_pass_case():
    res, text = _run({"SUI": "Sui_(blockchain)"}, lambda r: httpx.Response(200, json=GOOD))
    assert res[0].verdict == "PASS"
    assert "SUI" in text and "PASS: 1" in text and "FAIL: 0" in text


def test_disambiguation_fails():
    body = {**GOOD, "type": "disambiguation"}
    res, _ = _run({"S": "S"}, lambda r: httpx.Response(200, json=body))
    assert res[0].verdict == "FAIL" and "disambiguation" in res[0].reason


def test_404_fails():
    res, _ = _run({"X": "Nope"}, lambda r: httpx.Response(404))
    assert res[0].verdict == "FAIL" and "404" in res[0].reason


def test_off_topic_200_fails():
    body = {"type": "standard", "description": "Species of bird", "extract": "A small bird found in Asia."}
    res, _ = _run({"X": "Bird"}, lambda r: httpx.Response(200, json=body))
    assert res[0].verdict == "FAIL" and "crypto" in res[0].reason


def test_redirect_followed():
    def h(r):
        if r.url.path.endswith("/Old"):
            return httpx.Response(302, headers={"location": "https://en.wikipedia.org/api/rest_v1/page/summary/New"})
        return httpx.Response(200, json=GOOD)
    res, _ = _run({"X": "Old"}, h)
    assert res[0].verdict == "PASS" and res[0].status == 200


def test_network_error_reported_not_raised():
    def h(r):
        raise httpx.ConnectError("boom secret-token")
    res, text = _run({"X": "A", "Y": "B"}, h)
    assert [r.verdict for r in res] == ["FAIL", "FAIL"]
    assert "ConnectError" in text and "secret" not in text


def test_json_block_only_pass_entries():
    def h(r):
        return httpx.Response(200, json=GOOD) if r.url.path.endswith("/Good") else httpx.Response(404)
    _, text = _run({"A": "Good", "B": "Bad"}, h)
    block = json.loads(text[text.index("{\n") if "{\n" in text else text.rindex("{"):])
    assert block == {"A": "Good"}


def test_sleep_injected_one_second_between_requests():
    sleeps: list[float] = []
    _run({"A": "A1", "B": "B1", "C": "C1"}, lambda r: httpx.Response(404), sleeps)
    assert sleeps == [1.0, 1.0]


def test_user_agent_is_fetcher_one():
    seen = []
    _run({"A": "A1"}, lambda r: seen.append(r.headers["user-agent"]) or httpx.Response(404))
    assert seen == [wikipedia.USER_AGENT]


def test_null_titles_are_skipped():
    calls = []
    res, _ = _run({"A": None}, lambda r: calls.append(1) or httpx.Response(404))
    assert not calls and res == []


def test_unreadable_file_exits_nonzero(tmp_path):
    assert c.main(["--file", str(tmp_path / "missing.json")]) != 0


def test_no_network_in_main_with_empty_file(tmp_path):
    f = tmp_path / "m.json"
    f.write_text("{}")
    assert c.main(["--file", str(f)]) == 0


# --- candidates file ---

def _cand() -> dict:
    return json.loads(CANDIDATES.read_text())


def test_candidates_shape():
    keys = [k for k, _ in json.loads(CANDIDATES.read_text(), object_pairs_hook=lambda p: p)]
    assert keys and len(keys) == len(set(keys))
    for sym, t in _cand().items():
        assert re.fullmatch(r"[A-Z0-9]+", sym)
        assert isinstance(t, str) and t and t == t.strip() and " " not in t
        assert not re.search(r"https?:|wikipedia\.org|/wiki/|[/?#%\\]", t)
        assert not t.startswith("_") and not t.endswith("_") and "__" not in t
    norm = [t.casefold() for t in _cand().values()]
    assert len(norm) == len(set(norm))


def test_candidates_no_ambiguous_bare_titles():
    from api.tests.data.attention.test_wiki_articles_shape import AMBIGUOUS
    assert {s: t for s, t in _cand().items() if t.casefold() in AMBIGUOUS} == {}


def test_candidates_do_not_overlap_mapped_symbols():
    mapped = {k for k, v in json.loads(MAPPED.read_text()).items() if v}
    mapped_titles = {v.casefold() for v in json.loads(MAPPED.read_text()).values() if v}
    assert not set(_cand()) & mapped
    assert not {t.casefold() for t in _cand().values()} & mapped_titles


def test_fetcher_does_not_reference_candidates():
    assert "candidates" not in Path(wikipedia.__file__).read_text()
    for p in Path(wikipedia.__file__).parent.glob("*.py"):
        assert "wiki_articles_candidates" not in p.read_text(), p
