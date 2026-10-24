"""GET/POST /api/narrative/baskets (S-A, T68): baskets are screener groups.

Create, rename and delete stay on /api/layout/crypto (revision 409). A move
checks screener membership first (AC-27); `place_coin` does not.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path

from api.data import baskets_view
from api.data import layout as layout_store
from api.data import watchlist as watchlist_store
from api.models.baskets import BasketsResponse, MoveCoinRequest, MoveCoinResponse

router = APIRouter(prefix="/api/narrative/baskets", tags=["baskets"])

_SECTION = "crypto"


@router.get("", response_model=BasketsResponse)
def get_baskets() -> BasketsResponse:
    lay = layout_store.read_layout(_SECTION)
    return BasketsResponse(
        revision=lay.revision, baskets=baskets_view.baskets(lay), unassigned=baskets_view.unassigned(lay)
    )


@router.post("/{group_id}/coins", response_model=MoveCoinResponse)
def move_coin(
    body: MoveCoinRequest, group_id: str = Path(pattern=layout_store.GROUP_ID_RE.pattern)
) -> MoveCoinResponse:
    try:
        symbol = watchlist_store.normalize_symbol(body.symbol)
    except watchlist_store.InvalidSymbolError:
        raise HTTPException(status_code=422, detail=f"invalid symbol: {body.symbol!r}")
    if symbol not in watchlist_store.read_watchlist():
        raise HTTPException(
            status_code=404, detail=f"{symbol} is not on your screener. Add it to the screener first."
        )
    lay = layout_store.read_layout(_SECTION)
    target = next((g for g in lay.groups if g.id == group_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail=f"unknown group: {group_id}")
    previous = baskets_view.basket_of(lay, symbol)
    if not layout_store.place_coin(_SECTION, symbol, group_id):
        raise HTTPException(status_code=404, detail=f"unknown group: {group_id}")
    is_basket = group_id != layout_store.DEFAULT_GROUP_ID
    return MoveCoinResponse(
        symbol=symbol,
        basket=target.name if is_basket else None,
        previous_basket=previous.name if previous else None,
    )
