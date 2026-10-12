"""S9B: the layout section "equities". Every test runs against tmp_path: the
autouse fixture redirects the watchlist, equities and layout paths and drops
any LSE key; nothing here reaches the network.
"""
from __future__ import annotations

import json

import pytest

from api.data import equities_store
from api.data import layout as layout_store
from api.data import watchlist as watchlist_store
from api.models.layout import LayoutGroup, LayoutUpdate


@pytest.fixture(autouse=True)
def _redirect(tmp_path, monkeypatch):
    monkeypatch.setattr(watchlist_store, "DEFAULT_WATCHLIST_PATH", tmp_path / "watchlist.json")
    monkeypatch.setenv("SCREENER_EQUITIES_PATH", str(tmp_path / "equities.json"))
    monkeypatch.delenv("SCREENER_LAYOUT_PATH", raising=False)
    monkeypatch.delenv("LSE_API_KEY", raising=False)
    return tmp_path


def _tickers(*symbols):
    for s in symbols:
        equities_store.add_ticker(s)


def _coins(*symbols):
    for s in symbols:
        watchlist_store.add_coin(s)


def _update(revision, groups, hidden=()):
    return LayoutUpdate(
        revision=revision,
        groups=[LayoutGroup(id=i, name=n, coins=list(c)) for i, n, c in groups],
        hidden_lines=list(hidden),
    )


def _stored(tmp_path):
    return json.loads((tmp_path / "layout.json").read_text())


def test_sections_tuple():
    assert layout_store.SECTIONS == ("crypto", "equities")


def test_default_equities_layout_comes_from_the_store(tmp_path):
    _tickers("VOD", "AAPL", "MSFT")
    layout = layout_store.read_layout("equities")
    assert layout.section == "equities" and layout.source == "default" and layout.revision == 0
    assert [(g.id, g.name, g.coins) for g in layout.groups] == [("main", "Main", ["VOD", "AAPL", "MSFT"])]
    assert layout.hidden_lines == []
    assert not (tmp_path / "layout.json").exists()


def test_crypto_and_equities_members_never_mix():
    _coins("BTC", "ETH")
    _tickers("AAPL", "VOD")
    crypto = layout_store.read_layout("crypto")
    equities = layout_store.read_layout("equities")
    assert [c for g in crypto.groups for c in g.coins] == ["BTC", "ETH"]
    assert [c for g in equities.groups for c in g.coins] == ["AAPL", "VOD"]
    layout_store.save_layout("crypto", _update(0, [("main", "Main", ["BTC", "ETH", "AAPL"])]))
    assert [c for g in layout_store.read_layout("crypto").groups for c in g.coins] == ["BTC", "ETH"]


def test_removed_ticker_is_reconciled_out():
    _tickers("AAPL", "VOD", "MSFT")
    layout_store.save_layout("equities", _update(0, [("us", "US", ["AAPL", "MSFT"]), ("uk", "UK", ["VOD"])], ["MSFT"]))
    equities_store.remove_ticker("MSFT")
    layout = layout_store.read_layout("equities")
    assert [(g.id, g.coins) for g in layout.groups] == [("us", ["AAPL"]), ("uk", ["VOD"])]
    assert layout.hidden_lines == []


def test_place_and_drop_ticker():
    _tickers("AAPL", "VOD")
    layout_store.save_layout("equities", _update(0, [("us", "US", ["AAPL", "VOD"]), ("uk", "UK", [])]))
    assert layout_store.place_coin("equities", "VOD", "uk") is True
    assert [(g.id, g.coins) for g in layout_store.read_layout("equities").groups] == [("us", ["AAPL"]), ("uk", ["VOD"])]
    assert layout_store.place_coin("equities", "VOD", "nope") is False
    equities_store.remove_ticker("VOD")
    assert layout_store.drop_coin("equities", "VOD") is True
    layout = layout_store.read_layout("equities")
    assert [(g.id, g.coins) for g in layout.groups] == [("us", ["AAPL"]), ("uk", [])]
    assert layout.revision == 3


def test_stale_revision_is_refused():
    _tickers("AAPL")
    layout_store.save_layout("equities", _update(0, [("main", "Main", ["AAPL"])]))
    with pytest.raises(layout_store.StaleRevisionError):
        layout_store.save_layout("equities", _update(0, [("main", "Main", ["AAPL"])]))
    assert layout_store.read_layout("equities").revision == 1


def test_invalid_updates_are_refused(tmp_path):
    _tickers("AAPL", "VOD")
    bad = [
        _update(0, []),
        _update(0, [("Bad Id", "Main", ["AAPL"])]),
        _update(0, [("a", "Same", ["AAPL"]), ("b", "same", ["VOD"])]),
        _update(0, [("a", "A", ["AAPL"]), ("b", "B", ["AAPL"])]),
        _update(0, [("a", "   ", ["AAPL"])]),
    ]
    for update in bad:
        with pytest.raises(layout_store.InvalidLayoutError):
            layout_store.save_layout("equities", update)
    assert not (tmp_path / "layout.json").exists()


def test_hidden_lines_keep_tickers_only_and_refuse_btc():
    _tickers("AAPL", "VOD")
    saved = layout_store.save_layout("equities", _update(0, [("main", "Main", ["AAPL", "VOD"])], ["VOD", "BTC", "HYPE"]))
    assert saved.hidden_lines == ["VOD"]
    assert layout_store.read_layout("equities").hidden_lines == ["VOD"]


def test_reset_equities_leaves_crypto(tmp_path):
    _coins("BTC")
    _tickers("AAPL")
    layout_store.save_layout("crypto", _update(0, [("main", "Main", ["BTC"])], ["HYPE"]))
    layout_store.save_layout("equities", _update(0, [("us", "US", ["AAPL"])]))
    crypto_before = _stored(tmp_path)["sections"]["crypto"]
    reset = layout_store.reset_layout("equities")
    assert reset.source == "default" and reset.revision == 0
    assert _stored(tmp_path)["sections"] == {"crypto": crypto_before}


def test_corrupt_file_recovers_equities(tmp_path):
    _tickers("AAPL")
    (tmp_path / "layout.json").write_text("{broken")
    layout = layout_store.read_layout("equities")
    assert layout.source == "recovered" and [g.coins for g in layout.groups] == [["AAPL"]]
    saved = layout_store.save_layout("equities", _update(0, [("main", "Main", ["AAPL"])]))
    assert saved.revision == 1 and saved.source == "file"
    assert (tmp_path / "layout.json.bad").read_text() == "{broken"


def test_reconcile_default_still_keeps_reference_symbols():
    groups, hidden = layout_store._reconcile([], ["BTC", "HYPE", "XYZ"], ["ETH"])
    assert groups == [{"id": "main", "name": "Main", "coins": ["ETH"]}]
    assert hidden == ["BTC", "HYPE"]


def test_save_equities_leaves_stored_crypto_byte_equal(tmp_path):
    _coins("BTC", "ETH")
    _tickers("AAPL")
    layout_store.save_layout("crypto", _update(0, [("a", "A", ["ETH"]), ("b", "B", ["BTC"])], ["HYPE"]))
    before = json.dumps(_stored(tmp_path)["sections"]["crypto"], sort_keys=True)
    layout_store.save_layout("equities", _update(0, [("main", "Main", ["AAPL"])]))
    assert json.dumps(_stored(tmp_path)["sections"]["crypto"], sort_keys=True) == before
