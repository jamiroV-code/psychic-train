"""GET/POST/DELETE /api/watchlist (API Surface)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.data import watchlist as watchlist_store

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


class WatchlistResponse(BaseModel):
    coins: list[str]


class AddCoinRequest(BaseModel):
    symbol: str


@router.get("", response_model=WatchlistResponse)
def get_watchlist() -> WatchlistResponse:
    return WatchlistResponse(coins=watchlist_store.read_watchlist())


@router.post("", response_model=WatchlistResponse)
def add_coin(body: AddCoinRequest) -> WatchlistResponse:
    coins = watchlist_store.add_coin(body.symbol)
    return WatchlistResponse(coins=coins)


@router.delete("/{symbol}", response_model=WatchlistResponse)
def remove_coin(symbol: str) -> WatchlistResponse:
    try:
        coins = watchlist_store.remove_coin(symbol)
    except watchlist_store.SymbolNotFoundError:
        raise HTTPException(status_code=404, detail=f"symbol not on watchlist: {symbol}")
    return WatchlistResponse(coins=coins)
