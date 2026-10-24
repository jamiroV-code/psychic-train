"""GET/POST/DELETE /api/watchlist (API Surface).

T40 / S5a: adds refuse a 31st coin (409) and malformed symbols (422); an
optional `group_id` places a new coin in that layout group. Layout upkeep is
best effort: a layout failure is logged and never fails the add or remove.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.data import baskets_view
from api.data import layout as layout_store
from api.data import watchlist as watchlist_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

_SECTION = "crypto"


class WatchlistResponse(BaseModel):
    coins: list[str]


class RemoveCoinResponse(WatchlistResponse):
    affected_baskets: list[str]


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
    elif symbol not in before:
        # _reconcile appends unplaced coins to the LAST group, which would be a
        # basket: pin a new coin to Unassigned (main) when a saved layout has one.
        try:
            lay = layout_store.read_layout(_SECTION)
            if lay.source == "file" and any(g.id == layout_store.DEFAULT_GROUP_ID for g in lay.groups):
                layout_store.place_coin(_SECTION, symbol, layout_store.DEFAULT_GROUP_ID)
        except Exception:
            logger.warning("layout not updated after adding %s", symbol, exc_info=True)
    return WatchlistResponse(coins=coins)


@router.delete("/{symbol}", response_model=RemoveCoinResponse)
def remove_coin(symbol: str) -> RemoveCoinResponse:
    affected: list[str] = []
    try:
        basket = baskets_view.basket_of(layout_store.read_layout(_SECTION), symbol.upper().strip())
        affected = [basket.name] if basket else []
    except Exception:
        logger.warning("baskets not read before removing %s", symbol, exc_info=True)
    try:
        coins = watchlist_store.remove_coin(symbol)
    except watchlist_store.SymbolNotFoundError:
        raise HTTPException(status_code=404, detail=f"symbol not on watchlist: {symbol}")
    try:
        layout_store.drop_coin(_SECTION, symbol.upper().strip())
    except Exception:
        logger.warning("layout not updated after removing %s", symbol, exc_info=True)
    return RemoveCoinResponse(coins=coins, affected_baskets=affected)
