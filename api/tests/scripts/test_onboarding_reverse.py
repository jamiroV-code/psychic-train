"""T223 O4: the owner's reverse tool (AC15). Cache isolated; no network."""
from __future__ import annotations

import io
import json

import pytest

from api.data.attention import onboarding_store as ob
from api.data.attention import web_queries
from api.scripts import onboarding_reverse as rev

@pytest.fixture
def isolated_cache(tmp_path, monkeypatch):
    import socket
    from api.data import cache
    def boom(*args, **kwargs):
        raise AssertionError("no network")
    monkeypatch.setattr(socket.socket, "connect", boom)
    monkeypatch.setattr(cache, "CACHE_ROOT", tmp_path)
    return tmp_path


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    return rev.main(list(argv), out=out, err=err, today="2026-11-01"), out.getvalue(), err.getvalue()


def test_reverse_removes_the_entry_logs_it_and_prints_the_blocked_line(isolated_cache):
    ob.write_json("trends_keywords_auto.json", {"entries": {"ZZNEW": {"topic": "/g/zz", "label": "Zz"},
                                                            "ZZKEEP": {"topic": "/g/k", "label": "K"}}})
    code, out, _ = run("ZZNEW", "trends")
    assert code == 0
    assert set(ob.read_json("trends_keywords_auto.json")["entries"]) == {"ZZKEEP"}
    entry = ob.read_log("2026-11-01")["entries"][-1]
    assert (entry["action"], entry["source"], entry["previous"]["topic"]) == ("reversed", "trends", "/g/zz")
    assert json.loads(out.splitlines()[-1]) == {"ZZNEW": ["trends"]}


def test_nothing_to_reverse_is_exit_1(isolated_cache):
    assert run("ZZNEW", "wikipedia")[0] == 1


@pytest.mark.parametrize("argv", [("bad sym", "trends"), ("ZZNEW", "google"), ("ZZ\u202e", "trends"),
                                  ("ZZNEW", "../x")])
def test_hostile_arguments_are_refused(isolated_cache, argv):
    code, out, err = run(*argv)
    assert code == 2 and out == "" and "bad argument" in err


def test_a_placed_coin_is_refused(isolated_cache):
    placed = web_queries.placed_symbols()[0]
    ob.write_json("attention_queries_auto.json", {"entries": {placed: {"name": "X", "cashtag_only": True}}})
    code, _, err = run(placed, "reddit_x")
    assert code == 2 and "placed" in err
    assert placed in ob.read_json("attention_queries_auto.json")["entries"]
