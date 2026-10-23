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
