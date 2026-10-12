"""Equities API (S9A): `/api/equities`.

GET/POST/DELETE the ticker list (30 cap, 409), the cache-only board, chart
and spaghetti (`timeframe` 1d or 1w, anything else 422), the refresh status
and `POST /refresh` (202). Reads never call the network (D-1): all logic
lives in `analytics/equities_board.py` and `data/equities_refresh.py`.

A new ticker triggers one background refresh. Layout upkeep is best effort,
as in `routers/watchlist.py`: a layout failure is logged and never fails the
add or remove.
"""
from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from api.analytics import equities_board
from api.data import equities_refresh
from api.data import equities_store
from api.data import layout as layout_store
from api.models.screener import ChartView, ScreenerBoardResponse, SpaghettiResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/equities", tags=["equities"])

_SECTION = "equities"
EquityTimeframe = Literal["1d", "1w"]


class EquitiesResponse(BaseModel):
    tickers: list[str]


class AddTickerRequest(BaseModel):
    symbol: str
    group_id: str | None = None


@router.get("", response_model=EquitiesResponse)
def get_equities() -> EquitiesResponse:
    return EquitiesResponse(tickers=equities_store.load_tickers())


@router.post("", response_model=EquitiesResponse)
def add_equity(body: AddTickerRequest) -> EquitiesResponse:
    try:
        ticker = equities_store.normalize_ticker(body.symbol)
        before = equities_store.load_tickers()
        tickers = equities_store.add_ticker(ticker)
    except equities_store.InvalidTickerError:
        raise HTTPException(status_code=422, detail=f"invalid ticker: {body.symbol!r}")
    except equities_store.TickerLimitError:
        raise HTTPException(status_code=409, detail=equities_store.CAP_MESSAGE)
    if ticker not in before:
        try:
            equities_refresh.request_refresh_now()
        except Exception as exc:
            logger.warning("equities refresh not started after adding %s: %s", ticker, type(exc).__name__)
        if body.group_id is not None:
            try:
                layout_store.place_coin(_SECTION, ticker, body.group_id)
            except Exception:
                logger.warning("layout not updated after adding %s", ticker, exc_info=True)
    return EquitiesResponse(tickers=tickers)


@router.delete("/{ticker}", response_model=EquitiesResponse)
def remove_equity(ticker: str) -> EquitiesResponse:
    try:
        tickers = equities_store.remove_ticker(ticker)
    except (equities_store.TickerNotFoundError, equities_store.InvalidTickerError):
        raise HTTPException(status_code=404, detail=f"ticker not on the equities list: {ticker}")
    try:
        layout_store.drop_coin(_SECTION, ticker.strip().upper())
    except Exception:
        logger.warning("layout not updated after removing %s", ticker, exc_info=True)
    return EquitiesResponse(tickers=tickers)


@router.get("/board", response_model=ScreenerBoardResponse)
def get_board(timeframe: EquityTimeframe = Query(default="1d")) -> ScreenerBoardResponse:
    return equities_board.build_board(timeframe=timeframe)


@router.get("/spaghetti", response_model=SpaghettiResponse)
def get_spaghetti(timeframe: EquityTimeframe = Query(default="1d")) -> SpaghettiResponse:
    return equities_board.build_spaghetti(timeframe=timeframe)


@router.get("/status")
def get_status() -> dict:
    return equities_refresh.status()


@router.post("/refresh", status_code=202)
def post_refresh() -> dict:
    return equities_refresh.request_refresh_now()


@router.get("/{ticker}/chart", response_model=ChartView)
def get_chart_view(ticker: str, timeframe: EquityTimeframe = Query(default="1d")) -> ChartView:
    return equities_board.build_chart_view(ticker, timeframe=timeframe)
