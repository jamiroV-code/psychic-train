"""GET/POST/DELETE /api/layout/{section} (T40 / S5a, C4)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.data import layout as layout_store
from api.models.layout import Layout, LayoutUpdate

router = APIRouter(prefix="/api/layout", tags=["layout"])


def _not_found(section: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"unknown layout section: {section}")


@router.get("/{section}", response_model=Layout)
def get_layout(section: str) -> Layout:
    try:
        return layout_store.read_layout(section)
    except layout_store.UnknownSectionError:
        raise _not_found(section)


@router.post("/{section}", response_model=Layout)
def save_layout(section: str, body: LayoutUpdate) -> Layout:
    try:
        return layout_store.save_layout(section, body)
    except layout_store.UnknownSectionError:
        raise _not_found(section)
    except layout_store.StaleRevisionError:
        raise HTTPException(status_code=409, detail="layout changed elsewhere")
    except layout_store.InvalidLayoutError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.delete("/{section}", response_model=Layout)
def reset_layout(section: str) -> Layout:
    try:
        return layout_store.reset_layout(section)
    except layout_store.UnknownSectionError:
        raise _not_found(section)
