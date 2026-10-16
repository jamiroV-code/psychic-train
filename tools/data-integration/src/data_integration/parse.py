"""Table parsing over the Scrapling Selector (parser only: no fetchers, no networking)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from scrapling.parser import Selector

from data_integration.types import ParsedTable


PARSER_VERSION = "dit-parse-1"


class ParseError(ValueError):
    """The page did not contain the expected table."""


class SelectorMatchedNothing(ParseError):
    """The selector found no element (the page may be a different layout)."""


def _text(cell) -> str:
    return " ".join(str(cell.get_all_text()).split())


def parse_table(content: str | bytes, selector: str = "table") -> ParsedTable:
    """First element matching `selector` read as header row plus body rows (Scrapling has no table helper)."""
    page = Selector(content)
    found = page.css(selector)
    if not found:
        raise SelectorMatchedNothing(f"selector matched nothing: {selector}")
    rows = [[_text(c) for c in tr.css("th, td")] for tr in found[0].css("tr")]
    rows = [r for r in rows if r]
    if not rows:
        raise ParseError("table has no rows")
    width = len(rows[0])
    if any(len(r) != width for r in rows):
        raise ParseError("ragged table")
    return ParsedTable(columns=tuple(rows[0]), rows=tuple(tuple(r) for r in rows[1:]))


# ---- page outline: what the fetched page holds, never its text -----------------------------------------------------

_COUNT_TAGS = ("table", "pre", "ul", "ol", "canvas", "svg", "iframe", "form", "script", "img")
_TITLE_OK = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 .,:-")
_HOST_RE = re.compile(r"[a-z0-9.-]+")
_PATH_RE = re.compile(r"[A-Za-z0-9_./-]+")
_TOKEN_RE = re.compile(r"[A-Za-z0-9_-]{1,40}")
_TAG_RE = re.compile(r"[a-z0-9]{1,20}")
_NUM_RE = re.compile(r"[+-]?[$]?\d[\d,]*(\.\d+)?%?[kKmMbB]?")
_DATA_EXT = (".csv", ".json", ".xlsx", ".txt")
_MAX_BYTES, _MAX_DEPTH, _MAX_ELEMENTS, _MAX_TEXT = 2 * 1024 * 1024, 30, 2000, 20000
_MAX_HOSTS, _MAX_LINKS, _MAX_CANDIDATES, _MIN_NUMERIC, _MAX_TITLE = 10, 10, 15, 20, 60


@dataclass(frozen=True)
class PageOutline:
    ok: bool = False
    size: int = 0
    title: str = ""
    counts: tuple = ()
    hosts: tuple = ()
    links: tuple = ()
    candidates: tuple = ()


def _outline_title(page) -> str:
    found = page.css("title")
    if not found:
        return ""
    raw = " ".join(str(found[0].get_all_text()).split())[:400]
    return "".join(ch for ch in raw if ch in _TITLE_OK)[:_MAX_TITLE].strip()


def _outline_host(value) -> str:
    try:
        host = urlsplit(str(value).strip()).hostname or ""
    except ValueError:
        return ""
    return host if _HOST_RE.fullmatch(host) else ""


def _outline_hosts(page) -> tuple:
    seen: list = []
    for el in page.css("script[src], iframe[src]"):
        host = _outline_host(el.attrib.get("src", ""))
        if host and host not in seen:
            seen.append(host)
        if len(seen) >= _MAX_HOSTS:
            break
    return tuple(seen)


def _outline_links(page, page_host) -> tuple:
    seen: list = []
    for el in page.css("a[href]"):
        try:
            parts = urlsplit(str(el.attrib.get("href", "")).strip())
        except ValueError:
            continue
        if parts.netloc and (parts.hostname or "") != page_host:
            continue
        path = parts.path.lstrip("/")
        if path.lower().endswith(_DATA_EXT) and _PATH_RE.fullmatch(path) and path not in seen:
            seen.append(path)
        if len(seen) >= _MAX_LINKS:
            break
    return tuple(seen)


def _outline_token(el):
    tag = str(el.tag).lower()
    if not _TAG_RE.fullmatch(tag) or tag in ("html", "body"):
        return None
    ident = str(el.attrib.get("id", ""))
    if ident and _TOKEN_RE.fullmatch(ident):
        return tag, "#" + ident
    for token in str(el.attrib.get("class", "")).split():
        if _TOKEN_RE.fullmatch(token):
            return tag, "." + token
    return None


def _outline_candidates(page) -> tuple:
    found = []  # document order: (root, tag, token, count)
    for el in page.css("[id], [class]")[:_MAX_ELEMENTS]:
        named = _outline_token(el)
        if named is None:
            continue
        count = sum(1 for t in str(el.get_all_text())[:_MAX_TEXT].split() if _NUM_RE.fullmatch(t))
        if count >= _MIN_NUMERIC:
            found.append((el, named[0], named[1], count))
    roots = {id(e._root): i for i, (e, _, _, _) in enumerate(found)}
    dropped: set = set()
    for el, _, _, count in found:
        for depth, anc in enumerate(el.iterancestors()):
            if depth >= _MAX_DEPTH:
                break
            j = roots.get(id(anc._root))
            if j is not None and found[j][3] == count:
                dropped.add(j)
    return tuple((t, tok, n) for i, (_, t, tok, n) in enumerate(found) if i not in dropped)[:_MAX_CANDIDATES]


def outline(content, page_host=None) -> PageOutline:
    """Counts, host names, link paths and id/class tokens of a page. Pure; never raises; never returns page text."""
    try:
        body = content if isinstance(content, (bytes, bytearray)) else str(content).encode("utf-8", "replace")
        page = Selector(bytes(body[:_MAX_BYTES]))
        host = str(page_host or "").lower() or None
        return PageOutline(
            ok=True, size=len(body), title=_outline_title(page),
            counts=tuple((t, len(page.css(t))) for t in _COUNT_TAGS),
            hosts=_outline_hosts(page), links=_outline_links(page, host), candidates=_outline_candidates(page),
        )
    except Exception:
        return PageOutline()


def render_outline(o: PageOutline) -> tuple:
    if not o.ok:
        return ()
    out = []
    if o.title:
        out.append(f"title: {o.title}")
    out.append(f"size: {o.size} bytes")
    out.append("elements: " + " ".join(f"{t}={n}" for t, n in o.counts))
    if o.hosts:
        out.append("script/iframe hosts: " + ", ".join(o.hosts))
    if o.links:
        out.append("data links: " + ", ".join(o.links))
    if o.candidates:
        out.append("numeric-heavy elements: " + ", ".join(f"{t}{tok} ({n})" for t, tok, n in o.candidates))
    return tuple(out)


# ---- table outline: header names of the selected table, never its data rows ----------------------------------------

_HEADER_OK = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 _./%()-")
_MAX_HEADERS, _MAX_HEADER_CHARS, _MAX_CELL_RAW = 12, 24, 400


@dataclass(frozen=True)
class TableOutline:
    ok: bool = False
    matched: int = 0
    headers: tuple = ()
    extra: int = 0
    rows: int = 0
    cols: int = 0


def _header_text(cell) -> str:
    raw = " ".join(str(cell.get_all_text()).split())[:_MAX_CELL_RAW]
    return " ".join("".join(ch for ch in raw if ch in _HEADER_OK).split())[:_MAX_HEADER_CHARS].strip()


def table_outline(content, selector, table=None) -> TableOutline:
    """Header names and counts of the first table matching `selector`. Pure; never raises; never returns data rows."""
    try:
        body = content if isinstance(content, (bytes, bytearray)) else str(content).encode("utf-8", "replace")
        found = Selector(bytes(body[:_MAX_BYTES])).css(selector)
        if not found:
            return TableOutline(ok=True)
        trs = [tr for tr in found[0].css("tr") if len(tr.css("th, td"))]
        if not trs:
            return TableOutline(ok=True, matched=len(found))
        cells = trs[0].css("th, td")
        names = tuple(n for n in (_header_text(c) for c in cells) if n)
        return TableOutline(ok=True, matched=len(found), headers=names[:_MAX_HEADERS],
                            extra=max(0, len(names) - _MAX_HEADERS), rows=len(trs) - 1, cols=len(cells))
    except Exception:
        return TableOutline()


def render_table_outline(o: TableOutline) -> tuple:
    if not o.ok:
        return ()
    out = [f"tables matched: {o.matched}"]
    if o.cols:
        out += [f"columns: {o.cols}", f"rows: {o.rows}"]
    if o.headers:
        out.append("headers: " + ", ".join(o.headers) + (f" (+{o.extra} more)" if o.extra else ""))
    return tuple(out)
