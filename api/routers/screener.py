"""GET /api/screener/board, GET /api/screener/{symbol}/chart,
GET /api/screener/spaghetti (API Surface).

Thin FastAPI wrapper — all real logic lives in
`api/analytics/screener_board.py` (framework-independent, directly testable
without an HTTP client). No router calls a provider (ccxt_adapter,
watchlist store) directly — every fetch goes through that module.

T35 / S8: while the background refresh worker runs, each read is wrapped in
`refresh_worker.reads_cache_only_if_running()`, so it serves the cache and
queues a refresh for stale or missing pairs instead of fetching inline. With
the worker off, behaviour is the S1 fetch-through.
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from api.analytics import screener_board
from api.data.refresh_worker import reads_cache_only_if_running
from api.models.screener import (
    ChartView,
    ScreenerBoardResponse,
    SpaghettiResponse,
    Timeframe,
)

router = APIRouter(prefix="/api/screener", tags=["screener"])


@router.get("/board", response_model=ScreenerBoardResponse)
def get_board(timeframe: Timeframe = Query(default="1d")) -> ScreenerBoardResponse:
    """`timeframe` (Amendment 2) selects the displayed chart/SMA interval;
    the gain chips cover every timeframe regardless (AC-20).
    """
    with reads_cache_only_if_running():
        return screener_board.build_screener_board(timeframe=timeframe)


@router.get("/spaghetti", response_model=SpaghettiResponse)
def get_spaghetti(timeframe: Timeframe = Query(default="1d")) -> SpaghettiResponse:
    """T37 / S6: the spaghetti chart, following the board's timeframe."""
    with reads_cache_only_if_running():
        return screener_board.build_spaghetti(timeframe=timeframe)


@router.get("/{symbol}/chart", response_model=ChartView)
def get_chart_view(symbol: str, timeframe: Timeframe = Query(default="4h")) -> ChartView:
    """`timeframe` (Amendment 2, default 4h) selects the drill-down chart's interval."""
    with reads_cache_only_if_running():
        return screener_board.build_chart_view(symbol, timeframe=timeframe)
