"""RFC-004 integration test (item 65): end-to-end synthetic fixtures across
all four modules (momentum/trend, leg-boundary, narrative, confidence
badge) — AC-13's own gate.

SANDBOX NOTE: same fastapi-unavailable bypass as `test_screener.py` — goes
through `screener_board.build_screener_board` directly rather than
`fastapi.testclient.TestClient`.
"""
from __future__ import annotations

import re
import typing
from pathlib import Path

import pandas as pd
import pytest

from api.analytics import screener_board
from api.data import watchlist as watchlist_store
from api.data.ccxt_adapter import OhlcvResult
from api.models.narrative import NarrativeCategory
from api.models.regime import CurrentLegState, LegBoundary
from api.models.screener import ConfidenceState

_CONFIRMED_LEG = CurrentLegState(
    candidate_boundaries=[LegBoundary(date="2024-01-01", z_score=2.0, confirmed=True, confirmed_date="2024-01-05")],
    confirmed_boundaries=[LegBoundary(date="2024-01-01", z_score=2.0, confirmed=True, confirmed_date="2024-01-05")],
    composite_variant="reduced",
    has_data=True,
)

_AI_IN_FOCUS = NarrativeCategory(
    id="ai", label="AI", keywords=["ai"], seed=True, triggered=True, confirmed=False,
    trust_weight=0.6, source_availability={"pytrends": "ok", "reddit": "ok", "coingecko": "ok"},
)


def _bullish_df(n: int = 90, base: float = 100.0) -> pd.DataFrame:
    idx = pd.date_range(start="2024-01-01", periods=n, freq="D", tz="UTC")
    closes = [base + i * 2.0 for i in range(n)]
    return pd.DataFrame({
        "timestamp": idx, "open": closes, "high": closes, "low": closes, "close": closes,
        "volume": [100.0] * n, "source": "test",
    })


def _bearish_df(n: int = 90, base: float = 100.0) -> pd.DataFrame:
    idx = pd.date_range(start="2024-01-01", periods=n, freq="D", tz="UTC")
    closes = [base - i * 2.0 for i in range(n)]
    return pd.DataFrame({
        "timestamp": idx, "open": closes, "high": closes, "low": closes, "close": closes,
        "volume": [100.0] * n, "source": "test",
    })


class _FakeAdapter:
    def __init__(self, per_symbol: dict[str, pd.DataFrame]):
        self.per_symbol = per_symbol

    def fetch_ohlcv(self, symbol, timeframe, since=None, limit=None, exchange=None):
        df = self.per_symbol.get(symbol, pd.DataFrame())
        return OhlcvResult(symbol=symbol, timeframe=timeframe, df=df, insufficient_history=len(df) < 60, status="ok" if not df.empty else "unavailable")


@pytest.fixture
def two_coin_same_momentum_fixture(monkeypatch):
    """AC-13's exact scenario: two coins, both PASS momentum, both up trend,
    both a confirmed leg — differing only in their mapped narrative state
    (`ALIGN` gets `ai`, in-focus/triggered; `NOMAP` has no curated mapping
    at all) — so any badge difference between them is attributable to the
    narrative signal alone, isolating that one input.
    """
    per_symbol = {"ALIGN": _bullish_df(), "NOMAP": _bullish_df()}
    fake = _FakeAdapter(per_symbol)
    monkeypatch.setattr(screener_board.ccxt_adapter, "fetch_ohlcv", fake.fetch_ohlcv)
    monkeypatch.setattr(watchlist_store, "read_watchlist", lambda *a, **kw: ["ALIGN", "NOMAP"])
    monkeypatch.setattr(screener_board.leg_boundary, "compute_current_leg_state", lambda *a, **k: _CONFIRMED_LEG)
    monkeypatch.setattr(screener_board.narrative_trigger, "assemble_narrative_categories", lambda *a, **k: [_AI_IN_FOCUS])
    # ALIGN maps to the triggered "ai" seed category; NOMAP has no curated
    # mapping at all (map_coin_to_category returns None for it).
    monkeypatch.setattr(
        screener_board.narrative_mapping, "map_coin_to_category",
        lambda symbol: "ai" if symbol == "ALIGN" else None,
    )
    return fake


def test_same_momentum_differing_narrative_shows_distinct_badges(two_coin_same_momentum_fixture):
    board = screener_board.build_screener_board(timeframe="1d")
    by_symbol = {p.symbol: p for p in board.coins}

    assert by_symbol["ALIGN"].momentum.state == by_symbol["NOMAP"].momentum.state == "PASS"
    assert by_symbol["ALIGN"].trend.direction == by_symbol["NOMAP"].trend.direction == "up"

    # Same momentum, same trend, same (shared, macro) leg context — only the
    # narrative signal differs, and that alone must move the badge (AC-13).
    assert by_symbol["ALIGN"].confidence == "aligned"
    assert by_symbol["NOMAP"].confidence == "mixed"
    assert by_symbol["ALIGN"].confidence != by_symbol["NOMAP"].confidence


def test_opposite_price_action_shows_distinct_badges(monkeypatch, two_coin_same_momentum_fixture):
    """Complements the narrative-only comparison above: with the same leg
    context and narrative mapping for both coins, a bullish vs. bearish
    price series (moving both momentum AND trend together, since they're
    both RSI/SMA-derived from the same real bars — they can't be varied
    independently with realistic OHLCV fixtures) still produces visibly
    distinct badges (AC-13's disagreement-must-be-visible requirement is not
    limited to the narrative signal alone).
    """
    per_symbol = {"UP": _bullish_df(), "DOWN": _bearish_df()}
    fake = _FakeAdapter(per_symbol)
    monkeypatch.setattr(screener_board.ccxt_adapter, "fetch_ohlcv", fake.fetch_ohlcv)
    monkeypatch.setattr(watchlist_store, "read_watchlist", lambda *a, **kw: ["UP", "DOWN"])
    monkeypatch.setattr(screener_board.narrative_mapping, "map_coin_to_category", lambda symbol: "ai")

    board = screener_board.build_screener_board(timeframe="1d")
    by_symbol = {p.symbol: p for p in board.coins}

    assert by_symbol["UP"].momentum.state == "PASS"
    assert by_symbol["DOWN"].momentum.state == "FAIL"
    assert by_symbol["UP"].trend.direction == "up"
    assert by_symbol["DOWN"].trend.direction == "down"
    assert by_symbol["UP"].confidence != by_symbol["DOWN"].confidence


class TestContractSync:
    """Golden-fixture contract-sync check (item 65): a real response's
    `confidence` field must be one of the 4 literal enum values, and those
    4 values must exactly match `web/lib/types/screener.ts`'s manually-
    mirrored `ConfidenceState` union — so the two can't silently drift.
    """

    def test_confidence_field_is_one_of_the_four_closed_values(self, two_coin_same_momentum_fixture):
        board = screener_board.build_screener_board(timeframe="1d")
        allowed = set(typing.get_args(ConfidenceState))
        assert allowed == {"aligned", "mixed", "conflicting", "insufficient-data"}
        for panel in board.coins:
            assert panel.confidence in allowed

    def test_backend_enum_matches_frontend_mirrored_union(self):
        backend_values = set(typing.get_args(ConfidenceState))

        ts_path = Path(__file__).resolve().parents[3] / "web" / "lib" / "types" / "screener.ts"
        ts_source = ts_path.read_text()
        match = re.search(r'export type ConfidenceState = ([^;]+);', ts_source)
        assert match is not None, "ConfidenceState union not found in screener.ts — contract-sync check itself is broken"
        frontend_values = {v.strip().strip('"') for v in match.group(1).split("|")}

        assert backend_values == frontend_values, (
            f"api/models/screener.py::ConfidenceState {backend_values} and "
            f"web/lib/types/screener.ts::ConfidenceState {frontend_values} have drifted apart"
        )
