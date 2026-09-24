"""Farside spot-BTC ETF daily net flows adapter (regime dashboard RFC-003).

Source: https://farside.co.uk/bitcoin-etf-flow-all-data/ — a server-rendered
HTML table (`<table class="etf">`), one column per fund plus `Total`, in US$m.
RFC-003 Stage 0 (`regime-dashboard-farside_FEASIBILITY_24-09-26.md`, VIABLE)
confirmed a plain `httpx` GET with a browser-like User-Agent receives the
full table; no bot-protection bypass is attempted here, ever. A challenge
page, 403 or 503 is reported as `unavailable` with a reason.

Licensing: Farside's terms reserve all rights and grant no reuse licence, so
every result carries `redistributable=False` (personal use only — replace or
license the source before any public launch).

Parsing rules (all from the Stage 0 probe):
- only the `Total` column is kept; `(123.4)` is negative; commas are
  thousands separators (daily cells too, not just the summary row);
- `-` means "no figure" and is never read as zero: a `-` Total drops the row;
- a row whose fund cells are all `-` is "not reported yet" (today's row
  shows `0.0` in Total before the close) and is dropped as well;
- non-date rows (the trailing `Total` summary, headers, `Average` etc.) and
  malformed rows are skipped, never fatal.

Contract (same as the other adapters): typed result, `status` is
`ok | unavailable | stale`, never raises. Cache-first: the live page is
requested at most once per UTC day (a failed attempt counts), and each
successful fetch is merged into `cache/etf_flows/btc_spot.parquet`
(`date, net_flow_usd_m`, overwrite-merge deduped on date — plan §12b).
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Literal

import httpx
import pandas as pd

from api.data import cache

FARSIDE_URL = "https://farside.co.uk/bitcoin-etf-flow-all-data/"
SOURCE = "Farside Investors (farside.co.uk) — personal use only"
REDISTRIBUTABLE = False
COLUMNS = ["date", "net_flow_usd_m"]
MAX_RETRIES = 3
BACKOFF_BASE_SECONDS = 2.0
TIMEOUT_SECONDS = 30.0
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}
# Standard Cloudflare interstitial strings. The generic `cloudflare` /
# `challenge-platform` beacon appears on normal pages too, so it is not used.
CHALLENGE_MARKERS = ("just a moment", "checking your browser", "cf-error", "cf-chl-", "captcha")

Status = Literal["ok", "unavailable", "stale"]


@dataclass
class EtfFlowsResult:
    df: pd.DataFrame  # columns: date (tz-naive, day-normalised), net_flow_usd_m (US$m)
    status: Status
    reason: str | None = None
    redistributable: bool = REDISTRIBUTABLE
    source: str = SOURCE


# ------------------------------------------------------------------ cache


def cache_path() -> Path:
    return cache.CACHE_ROOT / "etf_flows" / "btc_spot.parquet"


def _attempt_marker_path() -> Path:
    return cache.CACHE_ROOT / "etf_flows" / ".last_attempt"


def _utc_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def read_cached() -> pd.DataFrame:
    path = cache_path()
    if not path.exists():
        return pd.DataFrame(columns=COLUMNS)
    try:
        df = cache._connect().sql(
            f"SELECT date, net_flow_usd_m FROM read_parquet('{path.as_posix()}') ORDER BY date"
        ).df()
    except Exception:
        return pd.DataFrame(columns=COLUMNS)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    return df


def merge_into_cache(fetched: pd.DataFrame) -> pd.DataFrame:
    """Overwrite-merge: union with the cached rows, newest fetch wins per date."""
    merged = pd.concat([read_cached(), fetched[COLUMNS]], ignore_index=True)
    merged["date"] = pd.to_datetime(merged["date"]).dt.normalize()
    merged = merged.drop_duplicates(subset="date", keep="last").sort_values("date").reset_index(drop=True)
    path = cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(path, index=False)
    return merged


def _todays_attempt() -> tuple[bool, str | None]:
    """(attempted today?, failure reason or None if that attempt succeeded)."""
    try:
        text = _attempt_marker_path().read_text(encoding="utf-8").strip()
    except OSError:
        return False, None
    day, _, outcome = text.partition("|")
    if day != _utc_today():
        return False, None
    return True, (None if outcome == "ok" else (outcome or "earlier attempt failed"))


def _record_attempt(outcome: str) -> None:
    try:
        marker = _attempt_marker_path()
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(f"{_utc_today()}|{outcome}", encoding="utf-8")
    except OSError:
        pass


# ---------------------------------------------------------------- parsing


class _EtfTableParser(HTMLParser):
    """Collects the text of every cell of every row inside `<table class="etf">`."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._depth = 0  # table nesting depth while inside the etf table
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            if self._depth:
                self._depth += 1
            elif "etf" in (dict(attrs).get("class") or "").split():
                self._depth = 1
            return
        if not self._depth:
            return
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag):
        if not self._depth:
            return
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None
        elif tag == "table":
            self._depth -= 1

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def parse_value(text: str) -> float | None:
    """`(95.1)` -> -95.1, `1,234.5` -> 1234.5, `-`/blank/garbage -> None."""
    t = (text or "").strip().replace(",", "").replace(" ", "")
    if t in ("", "-", "–", "—"):
        return None
    negative = t.startswith("(") and t.endswith(")")
    if negative:
        t = t[1:-1].strip()
    try:
        value = float(t)
    except ValueError:
        return None
    if value != value or value in (float("inf"), float("-inf")):
        return None
    return -value if negative else value


def parse_date(text: str) -> pd.Timestamp | None:
    try:
        return pd.Timestamp(datetime.strptime((text or "").strip(), "%d %b %Y"))
    except ValueError:
        return None


def parse_flows_html(html: str) -> pd.DataFrame:
    """Parse the `Total` column of Farside's etf table into `date, net_flow_usd_m`."""
    parser = _EtfTableParser()
    try:
        parser.feed(html or "")
        parser.close()
    except Exception:
        pass
    total_idx: int | None = None
    records: dict[pd.Timestamp, float] = {}
    for row in parser.rows:
        if total_idx is None:
            if "Total" in row and row and row[0].strip().lower() == "date":
                total_idx = row.index("Total")
            continue
        if len(row) <= total_idx:
            continue  # malformed
        date = parse_date(row[0])
        if date is None:
            continue  # Total / Average / repeated header rows
        total = parse_value(row[total_idx])
        if total is None:
            continue  # `-`: no figure, never zero
        fund_cells = row[1:total_idx]
        if fund_cells and all(parse_value(c) is None for c in fund_cells):
            continue  # not reported yet (Total shows 0.0 before the close)
        records[date] = total
    if not records:
        return pd.DataFrame(columns=COLUMNS)
    df = pd.DataFrame({"date": list(records.keys()), "net_flow_usd_m": list(records.values())})
    return df.sort_values("date").reset_index(drop=True)


# ---------------------------------------------------------------- fetching


def _is_challenge(text: str) -> bool:
    lowered = (text or "")[:20000].lower()
    return any(marker in lowered for marker in CHALLENGE_MARKERS)


def _fetch_html(client: httpx.Client, sleep=time.sleep) -> tuple[str | None, str | None]:
    """Return (html, None) or (None, reason). Retries only transient failures."""
    reason = "unknown failure"
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.get(FARSIDE_URL, headers=HEADERS, timeout=TIMEOUT_SECONDS, follow_redirects=True)
        except httpx.TimeoutException:
            reason = "request timed out"
        except httpx.HTTPError as exc:
            reason = f"network error: {type(exc).__name__}"
        except Exception as exc:  # never raise past the adapter
            return None, f"unexpected error: {type(exc).__name__}"
        else:
            if resp.status_code in (403, 503) or (resp.status_code == 200 and _is_challenge(resp.text)):
                # Bot protection: report it, never try to get around it.
                return None, f"blocked by source (HTTP {resp.status_code}, bot-protection page)"
            if resp.status_code == 200:
                return resp.text, None
            reason = f"HTTP {resp.status_code}"
            if resp.status_code != 429 and resp.status_code < 500:
                return None, reason
        if attempt < MAX_RETRIES - 1:
            sleep(BACKOFF_BASE_SECONDS * (2**attempt))
    return None, reason


def fetch_btc_spot_flows(client: httpx.Client | None = None, force: bool = False) -> EtfFlowsResult:
    """Daily US spot-BTC ETF net flows (US$m), cache-first.

    The page is requested at most once per UTC day (a failed attempt counts)
    unless `force=True`. Fresh parse -> merged into the cache -> `ok`. Any
    failure falls back to the cache as `stale`, or `unavailable` when nothing
    is cached. Never raises.
    """
    try:
        cached = read_cached()
        if not force:
            attempted, earlier_failure = _todays_attempt()
            if attempted:
                if cached.empty:
                    return EtfFlowsResult(cached, "unavailable", earlier_failure or "nothing cached")
                if earlier_failure:
                    return EtfFlowsResult(cached, "stale", f"today's fetch failed ({earlier_failure}); showing cached data")
                return EtfFlowsResult(cached, "ok")

        own_client = client is None
        client = client or httpx.Client()
        try:
            html, reason = _fetch_html(client)
        finally:
            if own_client:
                client.close()

        if html is not None:
            fetched = parse_flows_html(html)
            if not fetched.empty:
                merged = merge_into_cache(fetched)
                _record_attempt("ok")
                return EtfFlowsResult(merged, "ok")
            reason = "page fetched but no flow rows parsed (layout changed?)"

        _record_attempt(reason or "unknown failure")
        if cached.empty:
            return EtfFlowsResult(pd.DataFrame(columns=COLUMNS), "unavailable", reason)
        return EtfFlowsResult(cached, "stale", f"latest fetch failed ({reason}); showing cached data")
    except Exception as exc:  # pragma: no cover - last-resort guard
        return EtfFlowsResult(pd.DataFrame(columns=COLUMNS), "unavailable", f"adapter error: {type(exc).__name__}")
