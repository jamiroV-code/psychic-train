"""Finish plan RC-1, RC-7, RC-8, RC-9: Reddit live vocabulary, item reduction and the factory table. No network."""
from __future__ import annotations

import json
import sys
import types
from datetime import datetime, timezone

import pytest

from api.data.attention import reddit_core as rc
from api.data.attention import reddit_items, reddit_live, registry, web_queries
from api.data.attention.reddit_surface import RawItem

T = datetime(2026, 11, 6, 12, tzinfo=timezone.utc)
SALT = b"s" * 32


def raw(i="t3_a1", kind="post", author="SomeUser", text="I like $SOL a lot") -> RawItem:
    return RawItem(i, kind, "CryptoCurrency", T, author, None, 4, text)


def test_vocabulary_matches_config_and_plan():
    assert set(rc.STORES) == set(web_queries.REDDIT_LIVE_METHODS)
    assert set(rc.STORES.values()) <= registry.PC_STORES
    assert set(rc.STORES.values()) <= set(registry.SOURCE_IMPLS["reddit"])
    assert set(rc.METHOD_IDS) == set(rc.STORES.values())
    assert rc.STOP_REASONS == ("exhausted", "cap", "error", "breaker", "empty_shell", "login_required",
                               "schema_mismatch", "unsupported_format", "unknown")
    assert set(rc.REASONS) == {"lane_incomplete", "needs_probe", "method_disabled", "no_ready_account",
                               "request_cap", "schema_mismatch", "unsupported_format", "zero_unverified",
                               "method_unavailable"}
    assert "ready" in rc.GATE_STATES and "method_unavailable" in rc.GATE_STATES and len(rc.GATE_STATES) == 10
    assert rc.FACTORY_TABLE == {"browser": "api.data.attention.reddit_browser:make_method",
                                "gql_anon": "api.data.attention.reddit_gql:make_method"}


def test_reduce_item_keeps_only_the_six_fields_and_hashes_the_author():
    hasher = reddit_items.AuthorHasher(SALT)
    it = rc.reduce_item(raw(), hasher, lambda text: ("SOL",) if "$SOL" in text else ())
    assert set(it.to_json()) == {"id", "kind", "subreddit", "created_utc", "author_hash", "coins"}
    assert it.coins == ("SOL",) and it.author_hash == hasher("SomeUser")
    dumped = json.dumps(it.to_json())
    assert "SomeUser" not in dumped and "like" not in dumped and "someuser" not in dumped
    for gone in ("[deleted]", "[removed]", "", None):
        assert rc.reduce_item(raw(author=gone), hasher, lambda t: ()).author_hash is None


def test_live_item_validates():
    for bad in (dict(id="t3_A"), dict(kind="comment"), dict(subreddit="a b"), dict(created_utc=T.replace(tzinfo=None)),
                dict(author_hash="name"), dict(coins=("sol",))):
        args = dict(id="t3_a1", kind="post", subreddit="solana", created_utc=T, author_hash=None, coins=())
        args.update(bad)
        with pytest.raises(ValueError):
            rc.LiveItem(**args)


def test_item_store_first_row_wins_and_merges_coins(attention_cache):
    store_name = "reddit_live_browser"
    a = rc.LiveItem("t3_a1", "post", "solana", T, None, ("SOL",))
    assert rc.add_items(store_name, [a]) == 1
    assert rc.add_items(store_name, [rc.LiveItem("t3_a1", "post", "Bitcoin", T, None, ("BTC",))]) == 0
    got = rc.read_items(store_name, T.date())["t3_a1"]
    assert got.subreddit == "solana" and got.coins == ("BTC", "SOL")
    with pytest.raises(ValueError):
        rc.items_path("reddit_stream", T.date())


# --- the factory table ---

class Cfg:
    def __init__(self, methods):
        self.reddit_live_methods = tuple(methods)


class Synthetic:
    method_id, label, store = "gql_anon", "x", "reddit_live_gql"

    def gate_state(self, now):
        return "ready"

    def next_poll_due(self, now):
        return now

    def run_poll(self, ctx):
        raise AssertionError

    def close(self):
        pass


@pytest.fixture
def fake_module(monkeypatch):
    mod = types.ModuleType("fake_reddit_method")
    mod.make_method = lambda config, deps: Synthetic()
    mod.boom = lambda config, deps: 1 / 0
    mod.not_a_method = lambda config, deps: object()
    monkeypatch.setitem(sys.modules, "fake_reddit_method", mod)
    return mod


def test_resolution_is_lazy_and_only_for_named_methods(fake_module, monkeypatch):
    table = {"browser": "no_such_module_xyz:make_method", "gql_anon": "fake_reddit_method:make_method"}
    calls = []
    real = rc.importlib.import_module
    monkeypatch.setattr(rc.importlib, "import_module", lambda name: calls.append(name) or real(name))
    got = rc.resolve_methods(Cfg(["gql_anon"]), None, table=table)
    assert list(got) == ["gql_anon"] and isinstance(got["gql_anon"], Synthetic)
    assert calls == ["fake_reddit_method"]
    assert rc.resolve_methods(Cfg([]), None, table=table) == {} and calls == ["fake_reddit_method"]
    assert isinstance(got["gql_anon"], reddit_live.LiveMethod)


@pytest.mark.parametrize("entry", ["no_such_module_xyz:make_method", "fake_reddit_method:missing",
                                   "fake_reddit_method:boom", "fake_reddit_method:not_a_method", "bad", None])
def test_unresolvable_entry_is_method_unavailable_never_an_exception(fake_module, entry):
    m = rc.resolve_method("browser", Cfg(["browser"]), None, table={"browser": entry})
    assert isinstance(m, rc.UnavailableMethod)
    assert m.gate_state(T) == "method_unavailable" and m.next_poll_due(T) is None and m.store == "reddit_live_browser"
    assert isinstance(m, reddit_live.LiveMethod)
    with pytest.raises(RuntimeError):
        m.run_poll(None)


def test_shipped_table_without_landed_modules_is_unavailable():
    got = rc.resolve_methods(Cfg(["browser", "gql_anon"]), None)
    for name in ("browser", "gql_anon"):
        try:
            __import__(rc.FACTORY_TABLE[name].split(":")[0])
        except ImportError:
            assert got[name].gate_state(T) == "method_unavailable"
