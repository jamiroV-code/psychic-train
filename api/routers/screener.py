"""GET /api/screener/board, GET /api/screener/{symbol}/scalp,
GET /api/screener/relative-performance (API Surface).

Thin FastAPI wrapper — all real logic lives in
`api/analytics/screener_board.py` (framework-independent, directly testable
without an HTTP client). No router calls a provider (ccxt_adapter,
watchlist store) directly — every fetch goes through that module.
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from api.analytics import screener_board
from api.models.screener import (
    RelativePerformanceResponse,
    RelativePerformanceTimeframe,
    ScalpView,
    ScreenerBoardResponse,
    Timeframe,
)

router = APIRouter(prefix="/api/screener", tags=["screener"])


@router.get("/board", response_model=ScreenerBoardResponse)
def get_board(timeframe: Timeframe = Query(default="1d")) -> ScreenerBoardResponse:
    """`timeframe` (Amendment 2) selects the displayed chart/SMA interval
    only — `momentum`/`trend` PASS-FAIL fields are always computed from
    real daily+weekly bars regardless of this param (AC-16).
    """
    return screener_board.build_screener_board(timeframe=timeframe)


@router.get("/relative-performance", response_model=RelativePerformanceResponse)
def get_relative_performance(
    timeframe: RelativePerformanceTimeframe = Query(default="30d"),
) -> RelativePerformanceResponse:
    return screener_board.build_relative_performance(timeframe=timeframe)


@router.get("/{symbol}/scalp", response_model=ScalpView)
def get_scalp_view(symbol: str, timeframe: Timeframe = Query(default="4h")) -> ScalpView:
    """`timeframe` (Amendment 2, default 4h) selects the chart's interval;
    the scalp RSI reading stays labeled with its own timeframe (AC-18).
    """
    return screener_board.build_scalp_view(symbol, timeframe=timeframe)
