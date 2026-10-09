"""GET/POST/DELETE /api/watchlist (API Surface).

T40 / S5a: adds refuse a 31st coin (409) and malformed symbols (422); an
optional `group_id` places a new coin in that layout group. Layout upkeep is
best effort: a layout failure is logged and never fails the add or remove.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.data import layout as layout_store
from api.data import watchlist as watchlist_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

_SECTION = "crypto"


class WatchlistResponse(BaseModel):
    coins: list[str]


class AddCoinRequest(BaseModel):
    symbol: str
    group_id: str | None = None


@router.get("", response_model=WatchlistResponse)
def get_watchlist() -> WatchlistResponse:
    return WatchlistResponse(coins=watchlist_store.read_watchlist())


@router.post("", response_model=WatchlistResponse)
def add_coin(body: AddCoinRequest) -> WatchlistResponse:
    try:
        symbol = watchlist_store.normalize_symbol(body.symbol)
        before = watchlist_store.read_watchlist()
        coins = watchlist_store.add_coin(symbol)
    except watchlist_store.InvalidSymbolError:
        raise HTTPException(status_code=422, detail=f"invalid symbol: {body.symbol!r}")
    except watchlist_store.WatchlistFullError:
        raise HTTPException(status_code=409, detail=watchlist_store.CAP_MESSAGE)
    if body.group_id is not None and symbol not in before:
        try:
            layout_store.place_coin(_SECTION, symbol, body.group_id)
        except Exception:
            logger.warning("layout not updated after adding %s", symbol, exc_info=True)
    return WatchlistResponse(coins=coins)


@router.delete("/{symbol}", response_model=WatchlistResponse)
def remove_coin(symbol: str) -> WatchlistResponse:
    try:
        coins = watchlist_store.remove_coin(symbol)
    except watchlist_store.SymbolNotFoundError:
        raise HTTPException(status_code=404, detail=f"symbol not on watchlist: {symbol}")
    try:
        layout_store.drop_coin(_SECTION, symbol.upper().strip())
    except Exception:
        logger.warning("layout not updated after removing %s", symbol, exc_info=True)
    return WatchlistResponse(coins=coins)
