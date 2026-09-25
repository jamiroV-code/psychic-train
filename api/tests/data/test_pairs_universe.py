"""Pair-screener RFC-001: universe loader, pair enumeration (AC-1), isolation (AC-9)."""
from __future__ import annotations

import ast
import json
import subprocess
import sys
from math import comb
from pathlib import Path

import pytest

from api.data import pairs_universe as pu

REPO_ROOT = Path(__file__).resolve().parents[3]


def _write(tmp_path, payload) -> Path:
    p = tmp_path / "u.json"
    p.write_text(payload if isinstance(payload, str) else json.dumps(payload), encoding="utf-8")
    return p


class TestLoadUniverse:
    def test_real_file_has_the_approved_18(self):
        coins = pu.load_universe()
        assert coins == [
            "BTC", "ETH", "SOL", "HYPE", "XRP", "DOGE", "ADA", "AVAX", "LINK",
            "LTC", "BCH", "DOT", "SUI", "NEAR", "APT", "ARB", "OP", "ATOM",
        ]

    def test_uppercases_and_strips(self, tmp_path):
        assert pu.load_universe(_write(tmp_path, {"coins": [" btc", "Eth "]})) == ["BTC", "ETH"]

    def test_duplicate_warns_and_is_dropped(self, tmp_path):
        with pytest.warns(UserWarning, match="duplicate"):
            coins = pu.load_universe(_write(tmp_path, {"coins": ["BTC", "btc", "ETH"]}))
        assert coins == ["BTC", "ETH"]

    def test_stablecoin_warns_but_is_kept(self, tmp_path):
        with pytest.warns(UserWarning, match="stablecoin"):
            coins = pu.load_universe(_write(tmp_path, {"coins": ["BTC", "USDT"]}))
        assert coins == ["BTC", "USDT"]

    @pytest.mark.parametrize(
        "payload",
        [["BTC", "ETH"], {"tickers": ["BTC"]}, {"coins": "BTC"}, {"coins": ["BTC", 5]},
         {"coins": [""]}, "{not json"],
    )
    def test_malformed_raises(self, tmp_path, payload):
        with pytest.raises(pu.UniverseFileError):
            pu.load_universe(_write(tmp_path, payload))

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(pu.UniverseFileError, match="not found"):
            pu.load_universe(tmp_path / "nope.json")


class TestEnumeratePairs:
    def test_count_is_n_choose_2_no_dupes_no_self(self):
        coins = pu.load_universe()
        pairs = pu.enumerate_pairs(coins)
        assert len(pairs) == comb(len(coins), 2) == 153
        assert all(a != b for a, b in pairs)
        assert len({frozenset(p) for p in pairs}) == len(pairs)

    @pytest.mark.parametrize("n", [0, 1, 2, 5])
    def test_small_sizes(self, n):
        assert len(pu.enumerate_pairs([f"C{i}" for i in range(n)])) == comb(n, 2)


class TestIsolationFromWatchlist:
    def test_import_does_not_load_watchlist_module(self):
        code = (
            "import sys; import api.data.pairs_universe; "
            "print('api.data.watchlist' in sys.modules)"
        )
        out = subprocess.run(
            [sys.executable, "-c", code], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        )
        assert out.stdout.strip() == "False"

    def test_source_has_no_watchlist_import(self):
        tree = ast.parse(Path(pu.__file__).read_text(encoding="utf-8"))
        names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names += [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names.append(node.module or "")
                names += [a.name for a in node.names]
        assert not any("watchlist" in n for n in names)

    def test_separate_file_from_watchlist_json(self):
        assert pu.default_universe_path().name == "pairs_universe.json"
        assert pu.default_universe_path() != pu.default_universe_path().with_name("watchlist.json")
