"""Adaptive change detection: Scrapling's SQLite baseline, kept machine-local and written only on request.

Lost or empty baseline -> uncertain; selector hit -> ok; relocated by similarity -> changed;
no match -> uncertain. Nothing is guessed and `assess` never writes.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from scrapling.parser import Selector

from data_integration import paths, status


@dataclass(frozen=True)
class Assessment:
    status: str
    detail: str = ""
    has_baseline: bool = True


def store_path() -> Path:
    return paths.scrape_dir() / "adaptive.sqlite"


def _page(content, url: str, path: Path) -> Selector:
    return Selector(content, adaptive=True, storage_args={"storage_file": str(path), "url": url})


def assess(content: str | bytes, selector: str, *, url: str, path: Path | None = None) -> Assessment:
    path = Path(path) if path is not None else store_path()
    if not path.is_file():
        return Assessment(status.UNCERTAIN, "no baseline store", False)
    page = _page(content, url, path)
    if page.retrieve(selector) is None:
        return Assessment(status.UNCERTAIN, "no baseline for selector", False)
    if page.css(selector):
        return Assessment(status.OK)
    if page.css(selector, adaptive=True):
        return Assessment(status.CHANGED, "selector no longer matches; element relocated by similarity")
    return Assessment(status.UNCERTAIN, "selector matches nothing and nothing relocated")


def remember(content: str | bytes, selector: str, *, url: str, path: Path | None = None) -> None:
    path = Path(path) if path is not None else store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    _page(content, url, path).css(selector, auto_save=True)
