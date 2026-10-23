"""Trends keyword checker (T100a): fake TrendReq only, no network, no real sleeping."""
from __future__ import annotations

import hashlib
import io
import json
import sys
from datetime import datetime, timezone

import pytest

from api.data.attention import trends_keywords as k
from api.scripts import check_trends_keywords as c
from api.tests.trends_fixtures import (
    FORBIDDEN_IN_OUTPUT,
    SECRET,
    FakeTrendReq,
    block_network,
    candidate,
    factory,
    forbidden,
    too_many,
    tree_snapshot,
)

NOW = lambda: datetime(2026, 10, 21, 9, 0, tzinfo=timezone.utc)
LINK_TOPIC = candidate("/m/0link1", "Chainlink", "Cryptocurrency")


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    block_network(monkeypatch)


def _run(mapping, client, sleeps=None):
    out = io.StringIO()
    sleeps = [] if sleeps is None else sleeps
    res = c.run(mapping, client=client, sleep=sleeps.append, out=out, now=NOW)
    return res, out.getvalue()


def _block(text: str) -> dict:
    start = text.index(c.PASTE_HEADER) + len(c.PASTE_HEADER)
    end = text.index(c.DECISION_HEADER)
    return json.loads(text[start:end])


def test_pass_single_crypto_candidate():
    client = FakeTrendReq({"Chainlink": [LINK_TOPIC, candidate("/m/0chain", "Chain link", "Topic")]})
    res, text = _run({"LINK": "Chainlink"}, client)
    assert res[0].verdict == "PASS" and res[0].proposed["mid"] == "/m/0link1"
    assert 'LINK | Chainlink | 2 candidates | proposed /m/0link1 "Chainlink" (Cryptocurrency) | PASS' in text
    assert "PASS: 1 AMBIGUOUS: 0 FAIL: 0 NOT-RUN: 0" in text


def test_ambiguous_several_crypto_candidates():
    client = FakeTrendReq({"Sui": [candidate("/g/11sui", "Sui", "Blockchain"), candidate("/g/11suit", "Sui", "Token")]})
    res, text = _run({"SUI": "Sui"}, client)
    assert res[0].verdict == "AMBIGUOUS" and res[0].proposed is None
    assert "/g/11sui" in text and "/g/11suit" in text
    assert _block(text) == {}


def test_ambiguous_candidates_but_none_crypto_typed():
    client = FakeTrendReq({"Near": [candidate("/m/0near", "Near", "Word")]})
    res, text = _run({"NEAR": "Near"}, client)
    assert res[0].verdict == "AMBIGUOUS"
    assert '/m/0near "Near" (Word)' in text


def test_fail_no_candidates_reports_term_fallback():
    res, text = _run({"KAS": "Kaspa", "WEIRD": "a,b"}, FakeTrendReq())
    assert [r.verdict for r in res] == ["FAIL", "FAIL"]
    assert "falls back to term" in text.split("WEIRD")[0]
    assert "needs a human" in text


def test_candidate_without_valid_mid_is_not_proposed():
    client = FakeTrendReq({"Aave": [candidate("m/0aave", "Aave", "Cryptocurrency"), {"title": "Aave", "type": "Token"},
                                    candidate("/m/0aave", "", "Cryptocurrency"), "junk"]})
    res, text = _run({"AAVE": "Aave"}, client)
    assert res[0].verdict == "FAIL" and res[0].proposed is None
    assert "AAVE | Aave | 0 candidates" in text


def test_duplicate_proposed_topic_is_not_pasted():
    client = FakeTrendReq({"Chainlink": [LINK_TOPIC]})
    res, text = _run({"LINK": "Chainlink", "LNK": "Chainlink"}, client)
    assert [r.verdict for r in res] == ["AMBIGUOUS", "AMBIGUOUS"]
    assert _block(text) == {}


def test_sleep_is_at_least_two_seconds_between_calls():
    sleeps: list[float] = []
    client = FakeTrendReq()
    _run({"A": "Aaa", "B": "Bbb", "C": "Ccc"}, client, sleeps)
    assert len(sleeps) == 2 and all(s >= 2.0 for s in sleeps)
    assert c.INTERVAL_SECONDS >= 2.0
    sleeps.clear()
    _run({"A": "Aaa"}, FakeTrendReq(), sleeps)
    assert sleeps == []


def test_three_consecutive_429_stop_the_run():
    names = {f"S{i}": f"Name{i}" for i in range(6)}
    client = FakeTrendReq({"Name0": [candidate("/m/0n0", "Name0", "Token")], **{f"Name{i}": too_many() for i in range(1, 6)}})
    res, text = _run(names, client)
    assert client.suggestion_calls == ["Name0", "Name1", "Name2", "Name3"]
    assert [r.verdict for r in res] == ["PASS", "FAIL", "FAIL", "FAIL", "NOT-RUN", "NOT-RUN"]
    assert text.count("NOT-RUN (stopped after 3 consecutive HTTP 429)") == 2
    assert "NOT-RUN: 2" in text


def test_429_streak_resets_after_a_success():
    script = {"N1": too_many(), "N2": too_many(), "N3": [LINK_TOPIC], "N4": too_many(), "N5": too_many(), "N6": []}
    client = FakeTrendReq(script)
    res, _ = _run({f"S{i}": f"N{i}" for i in range(1, 7)}, client)
    assert len(client.suggestion_calls) == 6
    assert "NOT-RUN" not in [r.verdict for r in res]


def test_other_failure_prints_class_only_no_secret():
    client = FakeTrendReq({"Kaspa": forbidden(), "Monero": too_many(), "Zcash": ConnectionError("boom " + "x")})
    _, text = _run({"KAS": "Kaspa", "XMR": "Monero", "ZEC": "Zcash"}, client)
    assert "ResponseError(HTTP 403)" in text and "TooManyRequestsError(HTTP 429)" in text and "ConnectionError" in text
    for bad in FORBIDDEN_IN_OUTPUT + ("boom", "403 tok", "code 429"):
        assert bad not in text


def test_paste_ready_block_is_valid_and_only_pass_entries():
    client = FakeTrendReq({"Chainlink": [LINK_TOPIC], "Aave": [candidate("/m/0aave", "Aave", "Decentralized finance protocol")],
                           "Near": [candidate("/m/0near", "Near", "Word")]})
    _, text = _run({"LINK": "Chainlink", "AAVE": "Aave", "NEAR": "Near", "KAS": "Kaspa"}, client)
    block = _block(text)
    assert block == {
        "LINK": {"topic": "/m/0link1", "label": "Chainlink", "note": "checker PASS 21-10-26"},
        "AAVE": {"topic": "/m/0aave", "label": "Aave", "note": "checker PASS 21-10-26"},
    }
    seed = json.loads(k.KEYWORDS_PATH.read_text(encoding="utf-8"))
    merged = {**seed, **block}
    placed = set(k.load().entries)
    out = k.validate(merged, placed)
    assert out["entries"]["LINK"]["topic"] == "/m/0link1"
    decision = text.split(c.DECISION_HEADER)[1]
    assert "NEAR" in decision and "KAS" in decision and "LINK" not in decision


def test_writes_no_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data_dir = k.KEYWORDS_PATH.parent
    before = tree_snapshot(data_dir)
    sha = hashlib.sha256(k.KEYWORDS_PATH.read_bytes()).hexdigest()
    client = FakeTrendReq({"Chainlink": [LINK_TOPIC]})
    assert c.main(["--symbols", "LINK,AAVE"], trendreq_factory=factory(client), sleep=lambda s: None, now=NOW) == 0
    assert tree_snapshot(data_dir) == before
    assert hashlib.sha256(k.KEYWORDS_PATH.read_bytes()).hexdigest() == sha
    assert list(tmp_path.iterdir()) == []


def test_unreadable_or_non_object_file_exits_2_and_empty_map_exits_0(tmp_path, capsys):
    fac = factory(FakeTrendReq())
    assert c.main(["--file", str(tmp_path / "nope.json")], trendreq_factory=fac, sleep=lambda s: None) == 2
    (tmp_path / "list.json").write_text("[1, 2]", encoding="utf-8")
    assert c.main(["--file", str(tmp_path / "list.json")], trendreq_factory=fac, sleep=lambda s: None) == 2
    (tmp_path / "bad.json").write_text("{nope", encoding="utf-8")
    assert c.main(["--file", str(tmp_path / "bad.json")], trendreq_factory=fac, sleep=lambda s: None) == 2
    err = capsys.readouterr().err
    assert "nope" not in err.replace("nope.json", "")  # class only, no file content
    (tmp_path / "empty.json").write_text("{}", encoding="utf-8")
    assert c.main(["--file", str(tmp_path / "empty.json")], trendreq_factory=fac, sleep=lambda s: None) == 0
    assert "PASS: 0 AMBIGUOUS: 0 FAIL: 0 NOT-RUN: 0" in capsys.readouterr().out
    assert c.main(["--symbols", "lower"], trendreq_factory=fac, sleep=lambda s: None) == 2


def test_default_map_comes_from_keyword_file_labels():
    client = FakeTrendReq()
    assert c.main([], trendreq_factory=factory(client), sleep=lambda s: None, now=NOW) == 0
    m = k.load()
    assert client.suggestion_calls == [e["label"] for e in m.entries.values()]
    assert m.anchor["label"] not in client.suggestion_calls
    client2 = FakeTrendReq()
    assert c.main(["--symbols", "SOL,ATOM"], trendreq_factory=factory(client2), sleep=lambda s: None) == 0
    assert client2.suggestion_calls == ["Solana", m.entries["ATOM"]["label"]]


def test_pytrends_missing_exits_3_and_prints_the_command(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "pytrends", None)
    monkeypatch.setitem(sys.modules, "pytrends.request", None)
    assert c.main(["--symbols", "SOL"], sleep=lambda s: None) == 3
    err = capsys.readouterr().err
    assert "uv run --project api --with pytrends python -m api.scripts.check_trends_keywords" in err


def test_single_crypto_candidate_not_passed_for_ticker_label_or_title_mismatch():
    client = FakeTrendReq({"RAIN": [candidate("/g/11rain", "Rain", "Cryptocurrency")],
                           "Kaspa": [candidate("/g/11kas", "Kaspa Network", "Cryptocurrency")],
                           "Monero": [candidate("/m/0xmr", "Some other coin", "Cryptocurrency")]})
    res, text = _run({"RAIN": "RAIN", "KAS": "Kaspa", "XMR": "Monero"}, client)
    assert [r.verdict for r in res] == ["AMBIGUOUS", "PASS", "AMBIGUOUS"]
    assert "label is only the ticker" in text and "title does not contain the name" in text
    assert set(_block(text)) == {"KAS"}


def test_virtual_currency_type_counts_as_crypto():
    assert "virtual currency" in c.CRYPTO_TYPE_WORDS
    res, _ = _run({"ZEC": "Zcash"}, FakeTrendReq({"Zcash": [candidate("/m/0zec", "Zcash", "Virtual currency")]}))
    assert res[0].verdict == "PASS"


def test_client_start_failure_exits_1_and_prints_class_only(capsys, caplog):
    planted = "HTTPSConnectionPool(host='trends.google.com', url=/?geo=US) " + SECRET

    def _boom():
        raise ConnectionError(planted)

    assert c.main(["--symbols", "SOL"], trendreq_factory=_boom, sleep=lambda s: None) == 1
    cap = capsys.readouterr()
    text = cap.out + cap.err + caplog.text
    assert "ConnectionError" in text
    for bad in (planted, SECRET, "trends.google.com", "Traceback", "HTTPSConnectionPool"):
        assert bad not in text


# --- T134: checker v2, fixtures from the owner's run of 21-10-26 (id, title, Google type) ---

OWNER_PASS = {
    "BGB": ("Bitget Token", "/g/11xgyky_2b", "Bitget Token", "Currency"),
    "GT": ("GateToken", "/g/11n3zc6c3t", "GateToken", "Currency"),
    "KCS": ("KuCoin Token", "/g/11ydr7tg_8", "KuCoin Token", "Currency"),
    "VVV": ("Venice token", "/g/11xv_6jggk", "Venice Token", "Currency"),
    "XAUT": ("Tether Gold", "/g/11n3zb_gpq", "Tether Gold", "Currency"),
    "XRP": ("XRP", "/g/11ggfsh1hd", "XRP", "Currency"),
    "CAKE": ("PancakeSwap", "/g/11vb5nyrj6", "PancakeSwap", "Chain"),
    "UNI": ("Uniswap", "/g/11h1dsqb_m", "Uniswap", "Chain"),
    "HBAR": ("Hedera", "/g/11hbsyfq3f", "Hedera", "Distributed ledger"),
    "XLM": ("Stellar", "/m/0121k_50", "Stellar", "Payment network"),
    "HTX": ("HTX", "/m/012vj2d4", "HTX", "Cryptocurrency exchange company"),
    "NEAR": ("NEAR Protocol", "/g/11q3ypz8pd", "NEAR", "Blockchain platform"),
    "WLD": ("Worldcoin", "/g/11t_vkgtjf", "World", "Blockchain"),
}
OWNER_AMBIGUOUS = {
    "ETH": ("Ethereum", [("/m/0108bn2x", "Ethereum", "Software")]),
    "ALGO": ("Algorand", [("/g/11algo1", "Algorand", "Topic")]),
    "AVAX": ("Avalanche", [("/m/0avx1", "Colorado Avalanche", "Ice hockey team"),
                           ("/m/0avx2", "Chevrolet Avalanche", "Pickup truck")]),
    "ATOM": ("Cosmos", [("/m/0cosm", "Cosmos", "Topic")]),
    "APT": ("Aptos", [("/g/11apt1", "Aptos", "Community in California")]),
    "SUI": ("Sui", [("/g/11sui1", "Sui", "Topic")]),
    "TRX": ("TRON", [("/m/0tron", "Tron", "Topic")]),
    "JUP": ("Jupiter", [("/m/0jup", "Jupiter", "Planet")]),
    "BNB": ("BNB", [("/g/11bnb1", "Binance Coin", "Coin")]),
}


def _cands(rows):
    return [candidate(mid, title, type_) for mid, title, type_ in rows]


def test_v2_type_words_broadened_but_not_generic():
    for w in ("currency", "coin", "chain", "blockchain", "blockchain platform", "distributed ledger",
              "payment network", "cryptocurrency exchange company", "virtual currency", "cryptocurrency"):
        assert w in c.CRYPTO_TYPE_WORDS, w
    for generic in ("topic", "software", "company", "site", "computer program"):
        assert generic not in c.CRYPTO_TYPE_WORDS
    assert all(c.is_crypto_type(t) for t in ("Currency", "Chain", "Payment network", "Blockchain platform",
                                             "Cryptocurrency exchange company", "Decentralized finance protocol"))
    for t in ("Restaurant chain", "Software", "Topic", "Company", "Website", "Computer program", "Planet"):
        assert not c.is_crypto_type(t), t


def test_v2_owner_pass_list():
    script = {name: _cands([(mid, title, type_)]) for name, mid, title, type_ in OWNER_PASS.values()}
    res, text = _run({s: v[0] for s, v in OWNER_PASS.items()}, FakeTrendReq(script))
    assert {r.symbol: r.verdict for r in res} == {s: "PASS" for s in OWNER_PASS}
    block = _block(text)
    assert {s: e["topic"] for s, e in block.items()} == {s: v[1] for s, v in OWNER_PASS.items()}
    assert block["NEAR"]["label"] == "NEAR Protocol" and block["WLD"]["label"] == "Worldcoin"


def test_v2_owner_ambiguous_list():
    script = {name: _cands(rows) for name, rows in OWNER_AMBIGUOUS.values()}
    res, text = _run({s: v[0] for s, v in OWNER_AMBIGUOUS.items()}, FakeTrendReq(script))
    assert {r.symbol: r.verdict for r in res} == {s: "AMBIGUOUS" for s in OWNER_AMBIGUOUS}
    assert _block(text) == {}
    assert next(r for r in res if r.symbol == "BNB").reason.startswith("label is only the ticker")


def test_v2_xmr_prefers_the_name_matching_candidate():
    for coin_type in ("Topic", "Coin"):
        client = FakeTrendReq({"Monero": _cands([("/m/0xmr1", "Monero", "Cryptocurrency"), ("/m/0coin", "Coin", coin_type)])})
        res, _ = _run({"XMR": "Monero"}, client)
        assert res[0].verdict == "PASS" and res[0].proposed["mid"] == "/m/0xmr1", coin_type


def test_v2_exact_title_tier_beats_contained_siblings():
    script = {"Litecoin": _cands([("/m/0lt1", "Litecoin", "Currency"), ("/m/0lt2", "Litecoin Cash", "Coin")]),
              "Bitcoin": _cands([("/m/05p0rrx", "Bitcoin", "Cryptocurrency"), ("/m/0bch", "Bitcoin Cash", "Cryptocurrency")]),
              "Zcash": _cands([("/m/0zec", "Zcash", "Cryptocurrency"), ("/m/0zecf", "Zcash Foundation", "Coin")])}
    res, _ = _run({"LTC": "Litecoin", "BTC": "Bitcoin", "ZEC": "Zcash"}, FakeTrendReq(script))
    assert [(r.verdict, r.proposed["mid"]) for r in res] == [("PASS", "/m/0lt1"), ("PASS", "/m/05p0rrx"), ("PASS", "/m/0zec")]


def test_v2_two_exact_titles_stay_ambiguous():
    client = FakeTrendReq({"Litecoin": _cands([("/m/0lt1", "Litecoin", "Currency"), ("/m/0lt2", "Litecoin", "Coin")])})
    res, _ = _run({"LTC": "Litecoin"}, client)
    assert res[0].verdict == "AMBIGUOUS" and res[0].reason == "several crypto-typed candidates"


def test_v2_contained_title_of_a_longer_coin_is_not_passed():
    cases = {"ETH": ("Ethereum", "Ethereum Classic"), "BTC": ("Bitcoin", "Bitcoin SV"),
             "SKY": ("Sky", "Sky Mavis"), "POL": ("Polygon", "Polygon zkEVM")}
    script = {name: _cands([("/m/0x" + sym.lower(), title, "Cryptocurrency")]) for sym, (name, title) in cases.items()}
    res, _ = _run({sym: name for sym, (name, _) in cases.items()}, FakeTrendReq(script))
    assert {r.symbol: r.verdict for r in res} == {s: "AMBIGUOUS" for s in cases}


def test_v2_eth_software_and_algo_topic_stay_ambiguous():
    script = {"Ethereum": _cands([("/m/0eth", "Ethereum", "Software")]), "Algorand": _cands([("/g/11algo", "Algorand", "Topic")])}
    res, _ = _run({"ETH": "Ethereum", "ALGO": "Algorand"}, FakeTrendReq(script))
    assert [(r.verdict, r.reason) for r in res] == [("AMBIGUOUS", "no crypto-typed candidate")] * 2


def test_v2_protocol_and_token_words_need_a_crypto_phrase():
    for t in ("Internet protocol", "Network protocol", "Tokenization company", "Communication protocol"):
        assert not c.is_crypto_type(t), t
    for t in ("Currency", "Coin", "Chain", "Distributed ledger", "Payment network", "Cryptocurrency exchange company",
              "Decentralized finance protocol", "Token"):
        assert c.is_crypto_type(t), t
    res, _ = _run({"ATOM": "Cosmos"}, FakeTrendReq({"Cosmos": _cands([("/m/0cos", "Cosmos", "Internet protocol")])}))
    assert res[0].verdict == "AMBIGUOUS"


def test_v2_prefix_rule_needs_one_candidate_and_four_chars():
    res, _ = _run({"ARX": "Arx Protocol"}, FakeTrendReq({"Arx Protocol": _cands([("/g/11arx", "Arx", "Blockchain")])}))
    assert res[0].verdict == "AMBIGUOUS"  # "Arx" is shorter than 4
    for sym, name, title in (("BCH", "Bitcoin Cash", "Bitcoin"), ("ETC", "Ethereum Classic", "Ethereum")):
        res, _ = _run({sym: name}, FakeTrendReq({name: _cands([("/m/0x1", title, "Cryptocurrency")])}))
        assert res[0].verdict == "AMBIGUOUS", sym  # the rest of the name is not a generic suffix
    two = _cands([("/g/11w1", "World", "Blockchain"), ("/g/11w2", "World Chain", "Chain")])
    res, _ = _run({"WLD": "Worldcoin"}, FakeTrendReq({"Worldcoin": two}))
    assert res[0].verdict == "AMBIGUOUS"


def test_v2_ticker_label_passes_only_on_exact_ticker_title():
    script = {"OKB": _cands([("/g/11okb", "OKB", "Currency")]), "RAIN": _cands([("/g/11rain", "Rain", "Currency")])}
    res, _ = _run({"OKB": "OKB", "RAIN": "RAIN"}, FakeTrendReq(script))
    assert [r.verdict for r in res] == ["PASS", "AMBIGUOUS"]


def test_v2_ambiguous_coin_gets_exact_name_candidate_and_verify_hint():
    script = {name: _cands(rows) for name, rows in OWNER_AMBIGUOUS.values()}
    _, text = _run({"ETH": "Ethereum", "AVAX": "Avalanche"}, FakeTrendReq(script))
    decision = text.split(c.DECISION_HEADER)[1]
    assert 'ETH | AMBIGUOUS | no crypto-typed candidate' in decision
    assert '    verify /m/0108bn2x "Ethereum" (Software): https://trends.google.com/trends/explore?q=%2Fm%2F0108bn2x' in decision
    assert "AVAX | AMBIGUOUS" in decision and "verify /m/0avx" not in decision  # no exact-name candidate


# --- T155: checker v3, query variants and qualified-term fallback. The base-name rows are the owner's run of
# 22-10-26; the variant rows are hypothetical (the owner runs the real thing). ---

STAMP_23 = lambda: datetime(2026, 10, 23, 9, 0, tzinfo=timezone.utc)


class Clock:
    """Injected clock: sleep advances it, the client records the time of every request."""

    def __init__(self):
        self.t = 0.0
        self.sleeps: list[float] = []

    def sleep(self, s: float) -> None:
        self.sleeps.append(s)
        self.t += s


class TimedClient(FakeTrendReq):
    def __init__(self, suggestions, clock: Clock):
        super().__init__(suggestions)
        self.clock = clock
        self.times: list[float] = []

    def suggestions(self, keyword: str):
        self.times.append(self.clock.t)
        return super().suggestions(keyword)


class InterruptAt(FakeTrendReq):
    def __init__(self, suggestions, at: str):
        super().__init__(suggestions)
        self.at = at

    def suggestions(self, keyword: str):
        if keyword == self.at:
            self.suggestion_calls.append(keyword)
            raise KeyboardInterrupt
        return super().suggestions(keyword)


def _run3(mapping, client, sleep=None, now=STAMP_23):
    out = io.StringIO()
    res = c.run(mapping, client=client, sleep=sleep or (lambda s: None), out=out, now=now, variants=True)
    return res, out.getvalue()


def _qualified(text: str) -> dict:
    return json.JSONDecoder().raw_decode(text.split(c.QUALIFIED_HEADER)[1].lstrip())[0]


class NoiseClient(FakeTrendReq):
    """Unscripted queries return one non-crypto candidate, so the coin ends AMBIGUOUS rather than FAIL."""

    def suggestions(self, keyword: str):
        if keyword in self.suggestion_script:
            return super().suggestions(keyword)
        self.suggestion_calls.append(keyword)
        return [candidate("/m/0n" + "".join(ch for ch in keyword if ch.isalnum()), keyword, "Topic")]


def _by(res):
    return {r.symbol: r for r in res}


def test_v3_variant_queries_are_the_name_plus_three_variants_deduplicated_and_capped():
    assert c.VARIANT_TEMPLATES == ("{name} crypto", "{name} coin", "{ticker} crypto")
    assert c.queries_for("AVAX", "Avalanche") == ["Avalanche", "Avalanche crypto", "Avalanche coin", "AVAX crypto"]
    assert c.queries_for("AKE", "AKE") == ["AKE", "AKE crypto", "AKE coin"]  # ticker label: one duplicate dropped
    assert c.queries_for("PEPE", "Pepe coin") == ["Pepe coin", "Pepe coin crypto", "PEPE crypto"]  # no "coin coin"
    assert c.queries_for("ZZZ", "Zzz Crypto") == ["Zzz Crypto", "Zzz Crypto coin", "ZZZ crypto"]
    assert all(len(c.queries_for(s, n)) <= c.MAX_QUERIES_PER_COIN for s, n in (("AVAX", "Avalanche"), ("A", "a")))
    assert c.MAX_QUERIES_PER_COIN == 4


def test_v3_default_run_is_still_one_query_per_coin():
    client = FakeTrendReq({"Chainlink": [LINK_TOPIC]})
    res, text = _run({"LINK": "Chainlink", "AVAX": "Avalanche"}, client)
    assert client.suggestion_calls == ["Chainlink", "Avalanche"]
    assert c.QUALIFIED_HEADER not in text and " via '" not in text


AVAX_BASE = _cands([("/m/0avx1", "Colorado Avalanche", "Ice hockey team"), ("/m/0avx3", "Avalanche", "Topic"),
                    ("/m/0avx2", "Chevrolet Avalanche", "Pickup truck")])


def test_v3_avax_crypto_typed_title_found_by_a_variant_passes():
    script = {"Avalanche": AVAX_BASE, "Avalanche crypto": _cands([("/g/11avaxc", "Avalanche", "Cryptocurrency"),
                                                                  ("/m/0avx1", "Colorado Avalanche", "Ice hockey team")])}
    client = FakeTrendReq(script)
    res, text = _run3({"AVAX": "Avalanche"}, client)
    assert client.suggestion_calls == c.queries_for("AVAX", "Avalanche")
    r = res[0]
    assert r.verdict == "PASS" and r.proposed["mid"] == "/g/11avaxc"
    assert [x["mid"] for x in r.candidates] == ["/m/0avx1", "/m/0avx3", "/m/0avx2", "/g/11avaxc"]  # first seen, deduped
    assert r.found_by["/m/0avx1"] == ["Avalanche", "Avalanche crypto"]
    assert "via 'Avalanche crypto'" in text
    assert _block(text) == {"AVAX": {"topic": "/g/11avaxc", "label": "Avalanche", "note": "checker PASS 23-10-26"}}


def test_v3_jup_planet_and_company_stay_ambiguous():
    script = {"Jupiter": _cands([("/m/0jup", "Jupiter", "Planet")]),
              "Jupiter crypto": _cands([("/g/11jupx", "Jupiter Exchange", "Company"), ("/m/0jup", "Jupiter", "Planet")])}
    res, text = _run3({"JUP": "Jupiter"}, FakeTrendReq(script))
    assert res[0].verdict == "AMBIGUOUS" and res[0].reason == "no crypto-typed candidate"
    assert '/g/11jupx "Jupiter Exchange" (Company) via \'Jupiter crypto\'' in text


def test_v3_sui_blockchain_from_a_variant_passes_and_suitsupply_is_ignored():
    script = {"Sui": _cands([("/m/0suit", "Suitsupply", "Clothing company"), ("/m/0suic", "Suitcase", "Topic")]),
              "Sui coin": _cands([("/g/11suib", "Sui", "Blockchain")])}
    res, _ = _run3({"SUI": "Sui"}, FakeTrendReq(script))
    assert res[0].verdict == "PASS" and res[0].proposed["mid"] == "/g/11suib"


def test_v3_atom_passes_only_through_the_crypto_typed_cosmos():
    script = {"Cosmos": _cands([("/m/0cosm", "Cosmos", "Topic"), ("/m/0costv", "Cosmos", "TV program")]),
              "ATOM crypto": _cands([("/g/11atomc", "Cosmos", "Cryptocurrency"), ("/m/0costv", "Cosmos", "TV program")])}
    res, _ = _run3({"ATOM": "Cosmos"}, FakeTrendReq(script))
    assert res[0].verdict == "PASS" and res[0].proposed["mid"] == "/g/11atomc"
    tv_only = {"Cosmos": _cands([("/m/0costv", "Cosmos", "TV program")])}
    res, _ = _run3({"ATOM": "Cosmos"}, FakeTrendReq(tv_only))
    assert res[0].verdict == "AMBIGUOUS"


def test_v3_two_exact_crypto_titles_across_variants_stay_ambiguous():
    script = {"Avalanche crypto": _cands([("/g/11ava1", "Avalanche", "Cryptocurrency")]),
              "AVAX crypto": _cands([("/g/11ava2", "Avalanche", "Blockchain")])}
    res, _ = _run3({"AVAX": "Avalanche"}, FakeTrendReq(script))
    assert res[0].verdict == "AMBIGUOUS" and res[0].reason == "several crypto-typed candidates"


def test_v3_v2_cautions_hold_with_variants():
    script = {"Ethereum crypto": _cands([("/m/0etc", "Ethereum Classic", "Cryptocurrency")]),
              "Polygon": _cands([("/m/0polw", "Polygon", "Website")]),
              "Polygon crypto": _cands([("/g/11zkevm", "Polygon zkEVM", "Blockchain")])}
    res, _ = _run3({"ETH": "Ethereum", "POL": "Polygon"}, FakeTrendReq(script))
    assert {r.symbol: r.verdict for r in res} == {"ETH": "AMBIGUOUS", "POL": "AMBIGUOUS"}


def test_v3_sole_crypto_candidate_titled_with_the_ticker_or_name_qualifier_passes():
    script = {"ETC crypto": _cands([("/g/11etc", "etc", "Cryptocurrency")]),
              "Ethereum Classic": _cands([("/m/0etcp", "Ethereum Classic", "Computer program")]),
              "Stacks crypto": _cands([("/g/11stx", "Stacks (cryptocurrency)", "Coin")]),
              "Ondo coin": _cands([("/g/11ondo", "Ondo (crypto)", "Token")])}
    res, _ = _run3({"ETC": "Ethereum Classic", "STX": "Stacks", "ONDO": "Ondo"}, FakeTrendReq(script))
    assert {r.symbol: (r.verdict, r.proposed["mid"]) for r in res} == {
        "ETC": ("PASS", "/g/11etc"), "STX": ("PASS", "/g/11stx"), "ONDO": ("PASS", "/g/11ondo")}


def test_v3_ticker_title_needs_to_be_the_sole_crypto_candidate():
    script = {"ETC crypto": _cands([("/g/11etc", "ETC", "Cryptocurrency"), ("/g/11etc2", "ETC Coin", "Coin")]),
              "Stacks coin": _cands([("/g/11stx", "Stacks (cryptocurrency)", "Coin"), ("/g/11stx2", "STX", "Token")])}
    res, _ = _run3({"ETC": "Ethereum Classic", "STX": "Stacks"}, FakeTrendReq(script))
    assert {r.symbol: r.verdict for r in res} == {"ETC": "AMBIGUOUS", "STX": "AMBIGUOUS"}
    # A ticker-only label keeps the v2 case-sensitive rule: "Rain" is not "RAIN".
    res, _ = _run3({"RAIN": "RAIN"}, FakeTrendReq({"RAIN crypto": _cands([("/g/11rain", "Rain", "Currency")])}))
    assert res[0].verdict == "AMBIGUOUS"


def test_v3_a_failed_variant_query_blocks_a_pass():
    script = {"Avalanche crypto": _cands([("/g/11avaxc", "Avalanche", "Cryptocurrency")]), "AVAX crypto": forbidden()}
    res, text = _run3({"AVAX": "Avalanche"}, FakeTrendReq(script))
    assert res[0].verdict == "AMBIGUOUS" and res[0].proposed is None
    assert "1 of 4 queries failed: ResponseError(HTTP 403)" in res[0].reason
    assert "AVAX" not in _qualified(text)  # an incomplete check is re-run, not given a term
    for bad in FORBIDDEN_IN_OUTPUT + ("code 403",):
        assert bad not in text
    all_fail = {q: forbidden() for q in c.queries_for("AVAX", "Avalanche")}
    res, _ = _run3({"AVAX": "Avalanche"}, FakeTrendReq(all_fail))
    assert res[0].verdict == "FAIL" and res[0].reason.startswith("request failed: ResponseError(HTTP 403)")


def test_v3_spacing_is_three_seconds_between_every_request_and_the_count_is_printed():
    clock = Clock()
    client = TimedClient({}, clock)
    res, text = _run3({"AVAX": "Avalanche", "AKE": "AKE"}, client, sleep=clock.sleep)
    assert len(client.times) == 7
    assert all(b - a >= 3.0 for a, b in zip(client.times, client.times[1:]))
    assert clock.sleeps == [c.INTERVAL_SECONDS] * 6 and c.INTERVAL_SECONDS == 3.0
    assert "requests sent: 7" in text


def test_v3_plan_line_prints_expected_requests_and_minutes_before_the_first_request():
    mapping = {f"S{i}": f"Name{i}" for i in range(34)}
    client = FakeTrendReq()
    _, text = _run3(mapping, client)
    first = text.splitlines()[0]
    assert first == "plan: 34 coins, 136 requests, about 7 min (3 s apart)"
    assert len(client.suggestion_calls) == 136


def test_v3_breaker_stops_mid_coin_and_marks_the_rest_not_run():
    clock = Clock()
    script = {"Avalanche": AVAX_BASE, "Avalanche crypto": too_many(), "Avalanche coin": too_many(),
              "AVAX crypto": too_many()}
    client = TimedClient(script, clock)
    res, text = _run3({"AVAX": "Avalanche", "SUI": "Sui", "JUP": "Jupiter"}, client, sleep=clock.sleep)
    assert client.suggestion_calls == ["Avalanche", "Avalanche crypto", "Avalanche coin", "AVAX crypto"]
    assert [r.verdict for r in res] == ["AMBIGUOUS", "NOT-RUN", "NOT-RUN"]
    assert "NOT-RUN: 2" in text and "requests sent: 4" in text


def test_v3_breaker_skips_the_rest_of_a_coin_once_tripped():
    script = {"Aaa": too_many(), "Aaa crypto": too_many(), "Aaa coin": too_many(), "AAA crypto": [LINK_TOPIC]}
    client = FakeTrendReq(script)
    res, _ = _run3({"AAA": "Aaa", "BBB": "Bbb"}, client)
    assert client.suggestion_calls == ["Aaa", "Aaa crypto", "Aaa coin"]
    assert [r.verdict for r in res] == ["FAIL", "NOT-RUN"]


def test_v3_ctrl_c_prints_partial_results_and_exits_130():
    script = {"Avalanche crypto": _cands([("/g/11avaxc", "Avalanche", "Cryptocurrency")]),
              "Sui": _cands([("/g/11suib", "Sui", "Blockchain")])}
    client = InterruptAt(script, "Sui coin")
    res, text = _run3({"AVAX": "Avalanche", "SUI": "Sui", "JUP": "Jupiter"}, client)
    assert [r.verdict for r in res] == ["PASS", "AMBIGUOUS", "NOT-RUN"]
    assert "interrupted" in _by(res)["SUI"].reason and "interrupted" in _by(res)["JUP"].reason
    assert "JUP" not in client.suggestion_calls and "Jupiter" not in client.suggestion_calls
    assert set(_block(text)) == {"AVAX"}
    assert "SUI" not in _qualified(text)
    out = io.StringIO()
    code = c.main(["--symbols", "AVAX,SUI", "--variants"], trendreq_factory=factory(InterruptAt(script, "Sui coin")),
                  sleep=lambda s: None, out=out, now=STAMP_23)
    assert code == 130 and c.PASTE_HEADER in out.getvalue()


def test_v3_qualified_term_proposals_are_valid_loader_entries():
    assert c.qualified_term("AVAX", "Avalanche") == "avalanche crypto"
    assert c.qualified_term("PEPE", "Pepe coin") == "pepe coin"
    assert c.qualified_term("WBT", "WhiteBIT Coin") == "whitebit coin"
    assert c.qualified_term("LEO", "UNUS SED LEO") == "unus sed leo crypto"
    assert c.qualified_term("ZZZ", "Zzz Token") == "zzz token"
    assert c.qualified_term("AKE", "AKE") is None  # ticker only: the owner names it
    assert c.qualified_term("ABC", "Café") is None  # not ASCII
    assert c.qualified_term("ABC", "x" * 40) is None  # too long for a term
    script = {"Jupiter": _cands([("/m/0jup", "Jupiter", "Planet")]),
              "Avalanche crypto": _cands([("/g/11avaxc", "Avalanche", "Cryptocurrency")])}
    mapping = {"JUP": "Jupiter", "AVAX": "Avalanche", "PEPE": "Pepe coin", "AKE": "AKE", "LEO": "UNUS SED LEO"}
    res, text = _run3(mapping, NoiseClient(script))
    proposals = _qualified(text)
    assert proposals == {
        "JUP": {"term": "jupiter crypto", "label": "Jupiter", "note": "qualified-term fallback 23-10-26, not checker PASS"},
        "PEPE": {"term": "pepe coin", "label": "Pepe coin", "note": "qualified-term fallback 23-10-26, not checker PASS"},
        "LEO": {"term": "unus sed leo crypto", "label": "UNUS SED LEO",
                "note": "qualified-term fallback 23-10-26, not checker PASS"},
    }
    assert "AKE | no qualified term: label is only the ticker; the owner names it" in text.split(c.QUALIFIED_HEADER)[1]
    seed = json.loads(k.KEYWORDS_PATH.read_text(encoding="utf-8"))
    merged = {**seed, **_block(text), **proposals}
    out = k.validate(merged, set(k.load().entries))
    assert out["entries"]["JUP"]["term"] == "jupiter crypto" and out["entries"]["AVAX"]["topic"] == "/g/11avaxc"


def test_v3_qualified_term_skips_a_term_another_coin_already_uses():
    seed_terms = {e["term"].casefold(): s for s, e in k.load().entries.items() if "term" in e}
    assert "pepe coin" in seed_terms and seed_terms["pepe coin"] == "PEPE"
    # PEPE replacing its own term is fine; another symbol with the same name is not.
    res, text = _run3({"PEPE": "Pepe coin", "PEPX": "Pepe coin"}, NoiseClient())
    tail = text.split(c.QUALIFIED_HEADER)[1]
    assert set(_qualified(text)) == {"PEPE"}
    assert "PEPX | no qualified term: 'pepe coin' is already used" in tail


def test_v3_only_unresolved_checks_coins_without_a_topic_and_uses_variants():
    m = k.load()
    unresolved = [s for s, e in m.entries.items() if "topic" not in e]
    assert c.unresolved_symbols(m) == unresolved and "SOL" not in unresolved and "AVAX" in unresolved
    client = FakeTrendReq()
    out = io.StringIO()
    assert c.main(["--only-unresolved"], trendreq_factory=factory(client), sleep=lambda s: None, out=out,
                  now=STAMP_23) == 0
    expected = [q for s in unresolved for q in c.queries_for(s, m.entries[s]["label"])]
    assert client.suggestion_calls == expected
    assert "Solana" not in client.suggestion_calls
    assert out.getvalue().startswith(f"plan: {len(unresolved)} coins, {len(expected)} requests")
    client2 = FakeTrendReq()
    assert c.main(["--only-unresolved", "--symbols", "SOL,AVAX"], trendreq_factory=factory(client2),
                  sleep=lambda s: None, out=io.StringIO()) == 0
    assert client2.suggestion_calls == c.queries_for("AVAX", "Avalanche")


def test_v3_only_unresolved_writes_nothing_and_keeps_m1(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    before = tree_snapshot(k.KEYWORDS_PATH.parent)
    assert c.main(["--only-unresolved"], trendreq_factory=factory(FakeTrendReq()), sleep=lambda s: None,
                  out=io.StringIO()) == 0
    assert tree_snapshot(k.KEYWORDS_PATH.parent) == before and list(tmp_path.iterdir()) == []

    def _boom():
        raise ConnectionError("HTTPSConnectionPool(host='trends.google.com') " + SECRET)

    assert c.main(["--only-unresolved"], trendreq_factory=_boom, sleep=lambda s: None) == 1
    cap = capsys.readouterr()
    assert "ConnectionError" in cap.err
    for bad in (SECRET, "trends.google.com", "HTTPSConnectionPool", "Traceback"):
        assert bad not in cap.out + cap.err


def test_v3_variant_errors_print_class_and_status_only():
    script = {"Avalanche": forbidden(), "Avalanche crypto": too_many(),
              "Avalanche coin": ConnectionError("boom " + SECRET), "AVAX crypto": []}
    _, text = _run3({"AVAX": "Avalanche"}, FakeTrendReq(script))
    assert "ResponseError(HTTP 403)" in text
    for bad in FORBIDDEN_IN_OUTPUT + ("boom", "code 429", "code 403", "body "):
        assert bad not in text


def test_v3_docstring_keeps_the_eyeball_rule_and_powershell_examples():
    doc = c.__doc__
    assert "Eyeball every PASS line" in doc
    assert "--only-unresolved" in doc and "--symbols 'AVAX,SUI'" in doc
    assert "qualified" in doc and "130" in doc
