"""T113 U1: the narratives file and its loader. Files only; the shipped file is checked without the cache."""
from __future__ import annotations

import json

import pytest

from api.analytics.attention import narratives as narr

# The 2026-10-18 top-100 snapshot (PLAN section 5 / G-OWN), embedded so the test never reads the rewritten cache.
SNAPSHOT_2026_10_18 = (
    "BTC ETH USDT BNB XRP USDC SOL TRX FIGR_HELOC ZEC HYPE DOGE XMR USDS WBT LINK LEO ADA RAIN NEAR XLM BCH USDE "
    "LTC DAI UNI AVAX USD1 CC SUI HBAR GRAM BTW XAUT USDG TAO SHIB PYUSD CRO QNT ENA RLUSD USYC OKB USDY AAVE BUIDL "
    "ONDO PUMP ASTER USDF WLD DOT PAXG WLFI M USDD MNT EURSAFO MORPHO PEPE SKY ICP U HTX BFUSD BGB USDGO ARB ETC JST "
    "VVV GT KCS ALGO KAS POL BCAP JUP RENDER ATOM PI FIL OUSD USTB AERO INJ NEXO LIT ZRO GHO PRL APT CAKE AKE STX "
    "STABLE XDC NIGHT EUTBL").split()
# Stablecoins and tokenized funds of that snapshot (SPEC per-coin table): not placed in any narrative.
NOT_PLACED = set(("USDT USDC FIGR_HELOC USDS USDE DAI USD1 USDG PYUSD RLUSD USYC USDY BUIDL USDF USDD EURSAFO U "
                  "BFUSD USDGO BCAP OUSD USTB GHO EUTBL M").split())


def doc(*narratives, status="proposed", as_of="2026-10-18"):
    return {"status": status, "as_of": as_of, "narratives": list(narratives)}


def n(nid, *coins, name=None):
    """coins: "SYM" (primary) or "SYM-" (not primary)."""
    return {"id": nid, "name": name or nid.upper(),
            "coins": [{"symbol": c.rstrip("-"), "primary": not c.endswith("-")} for c in coins]}


def test_loads_reviewed_file():
    d = narr.load_narratives()
    assert d["status"] == "reviewed" and d["as_of"] == "2026-10-18"
    assert [x["id"] for x in d["narratives"]] == [
        "majors-store-of-value", "layer-1", "layer-2", "defi", "memecoins", "ai-data-compute", "real-world-assets",
        "privacy", "payments-settlement", "infrastructure", "exchange-tokens"]


def test_shipped_file_places_every_snapshot_coin_once_as_primary():
    m = narr.memberships(SNAPSHOT_2026_10_18, 3)
    assert set(m.unassigned) == NOT_PLACED and "M" in m.unassigned
    assert len(m.primary) == 75 and set(m.primary) == set(SNAPSHOT_2026_10_18) - NOT_PLACED
    assert m.hidden == []


def test_shipped_owner_placements():
    m = narr.memberships(SNAPSHOT_2026_10_18, 3)
    assert {"BNB", "LEO", "OKB", "HYPE", "PUMP", "NEXO"} <= m.visible["exchange-tokens"]
    assert {s: m.primary[s] for s in ("HYPE", "PUMP", "NEXO", "XRP")} == {
        "HYPE": "exchange-tokens", "PUMP": "exchange-tokens", "NEXO": "exchange-tokens",
        "XRP": "majors-store-of-value"}
    assert "PUMP" in m.visible["memecoins"] and "XRP" in m.visible["payments-settlement"]
    assert "gaming" not in m.names and "oracle" not in m.names


def test_shipped_unverified_placements_carry_a_note():
    marked = {c["symbol"] for x in narr.load_narratives()["narratives"] for c in x["coins"]
              if "UNVERIFIED" in c.get("note", "")}
    assert marked == {"GRAM", "BTW", "AKE", "PRL", "RAIN", "STABLE", "NIGHT", "WLFI", "NEXO"}


def test_duplicate_primary_is_error_naming_symbol():
    with pytest.raises(narr.NarrativesError, match=r"'HYPE'.*defi, exchange-tokens"):
        narr.validate(doc(n("defi", "HYPE"), n("exchange-tokens", "HYPE")))


def test_no_primary_is_error():
    with pytest.raises(narr.NarrativesError, match=r"'INJ'.*has 0"):
        narr.validate(doc(n("defi", "UNI", "INJ-"), n("layer-1", "INJ-")))


def test_lowercase_symbol_is_error():
    with pytest.raises(narr.NarrativesError, match=r"'defi'.*'uni'"):
        narr.validate(doc(n("defi", "uni")))


@pytest.mark.parametrize("sym", ["../X", "A/B", "A\\B", "", "BTC\n", " BTC", "A" * 25, "B.TC"])
def test_symbol_with_path_characters_is_error(sym):
    with pytest.raises(narr.NarrativesError, match="symbol"):
        narr.validate(doc({"id": "defi", "name": "DeFi", "coins": [{"symbol": sym, "primary": True}]}))


@pytest.mark.parametrize("nid", ["DeFi", "../defi", "a/b", "", "defi\n", "x" * 41, None])
def test_bad_narrative_id_is_error(nid):
    with pytest.raises(narr.NarrativesError, match="narrative id"):
        narr.validate(doc({"id": nid, "name": "X", "coins": []}))


@pytest.mark.parametrize("bad", [
    {"status": "live"}, {"as_of": "18-10-26"}, {"as_of": "2026-13-01"}, {"as_of": None}, {"narratives": []},
])
def test_bad_header_is_error(bad):
    with pytest.raises(narr.NarrativesError):
        narr.validate({**doc(n("defi", "UNI")), **bad})


def test_duplicate_id_and_symbol_twice_are_errors():
    with pytest.raises(narr.NarrativesError, match="duplicate narrative id 'defi'"):
        narr.validate(doc(n("defi", "UNI"), n("defi", "AAVE")))
    with pytest.raises(narr.NarrativesError, match="'UNI' twice"):
        narr.validate(doc(n("defi", "UNI", "UNI-")))
    with pytest.raises(narr.NarrativesError, match="primary must be true or false"):
        narr.validate(doc({"id": "defi", "name": "DeFi", "coins": [{"symbol": "UNI"}]}))


def test_narrative_with_two_coins_is_hidden_not_error():
    d = narr.validate(doc(n("defi", "UNI", "AAVE", "CAKE"), n("privacy", "ZEC", "XMR", "NIGHT")))
    m = narr.memberships(["UNI", "AAVE", "CAKE", "ZEC", "XMR"], 3, d)
    assert list(m.visible) == ["defi"]
    assert m.hidden == [{"id": "privacy", "name": "PRIVACY", "coins": ["ZEC", "XMR"]}]


def test_memberships_count_every_narrative_toward_min():
    d = narr.validate(doc(n("layer-1", "SOL", "NEAR", "ICP"), n("ai-data-compute", "TAO", "NEAR-", "ICP-")))
    m = narr.memberships(["SOL", "NEAR", "ICP", "TAO"], 3, d)
    assert m.visible == {"layer-1": {"SOL", "NEAR", "ICP"}, "ai-data-compute": {"TAO", "NEAR", "ICP"}}


def test_coin_in_three_narratives_counted_in_each():
    d = narr.validate(doc(n("a", "X", "A1", "A2"), n("b", "X-", "B1", "B2"), n("c", "X-", "C1", "C2")))
    m = narr.memberships(["X", "A1", "A2", "B1", "B2", "C1", "C2"], 3, d)
    assert all("X" in m.visible[k] for k in ("a", "b", "c")) and m.primary["X"] == "a"


def test_unassigned_new_coin_listed_not_error():
    d = narr.validate(doc(n("defi", "UNI", "AAVE", "CAKE")))
    m = narr.memberships(["NEW", "UNI", "AAVE", "CAKE", "M"], 3, d)
    assert m.unassigned == ["NEW", "M"]


def test_file_sha_changes_with_any_edit(tmp_path):
    p = tmp_path / "n.json"
    p.write_text(json.dumps(doc(n("defi", "UNI"))))
    a = narr.file_sha(p)
    p.write_text(json.dumps(doc(n("defi", "UNI"), as_of="2026-10-19")))
    assert len(a) == 16 and narr.file_sha(p) != a


def test_shipped_id_map_resolves_old_ids():
    d, m = narr.load_narratives(), narr.load_id_map()
    assert narr.resolve_id("meme-token", d, m) == "memecoins"
    assert narr.resolve_id("decentralized-finance-defi", d, m) == "defi"
    assert narr.resolve_id("oracle", d, m) == "infrastructure"
    assert narr.resolve_id("layer-1", d, m) == "layer-1"
    assert narr.resolve_id("gaming", d, m) is None and narr.resolve_id("nonsense", d, m) is None
    assert set(m) == {"layer-1", "layer-2", "decentralized-finance-defi", "meme-token", "artificial-intelligence",
                      "real-world-assets-rwa", "gaming", "privacy-coins", "oracle"}


def test_id_map_with_path_characters_is_error(tmp_path):
    p = tmp_path / "m.json"
    p.write_text(json.dumps({"map": {"../x": {"narrative": "defi", "name": "X"}}}))
    with pytest.raises(narr.NarrativesError, match="old category id"):
        narr.load_id_map(p)
