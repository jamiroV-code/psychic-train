"""fetch (any Fetcher) -> parse -> validate -> adaptive -> normalise -> store -> provenance.

Nothing is written until every check passed. Never imports a fetch tier.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from data_integration import adaptive, provenance, status
from data_integration.normalise import normalise
from data_integration import parse as _parse
from data_integration.parse import ParseError, SelectorMatchedNothing, parse_table
from data_integration.store_writer import TargetNotEmpty, existing, write_series
from data_integration.types import Fetcher
from data_integration.validate import validate_table


@dataclass(frozen=True)
class PipelineResult:
    status: str
    detail: str = ""
    rows: int = 0
    outline: tuple[str, ...] = ()


def _same(a, b) -> bool:
    return len(a) == len(b) and provenance.content_hash(a.reset_index(drop=True)) == provenance.content_hash(b.reset_index(drop=True))


def run(
    fetcher: Fetcher,
    pass_,
    *,
    url: str,
    selector: str,
    symbol: str,
    timeframe: str,
    source_label: str | None = None,
    min_rows: int = 2,
    replace: bool = False,
    accept_baseline: bool = False,
    adaptive_path: Path | None = None,
    clock=None,
) -> PipelineResult:
    if not pass_.permits(url):
        return PipelineResult(status.REFUSED, "url outside the approved hosts and pages")
    outcome = fetcher.fetch(url, pass_)
    if outcome.status != status.OK:
        return PipelineResult(outcome.status, outcome.detail)
    try:
        table = parse_table(outcome.body, selector)
    except ParseError as exc:
        # a page whose table moved is a layout change, not bad data: ask the baseline before giving up
        moved = adaptive.assess(outcome.body, selector, url=url, path=adaptive_path)
        if moved.has_baseline and moved.status != status.OK:
            return PipelineResult(moved.status, moved.detail)
        lines: tuple[str, ...] = ()
        if isinstance(exc, SelectorMatchedNothing):
            try:
                lines = _parse.render_outline(_parse.outline(outcome.body, urlsplit(url).hostname))
            except Exception:
                lines = ()
        return PipelineResult(status.INVALID, str(exc), outline=lines)
    problems = validate_table(table, min_rows)
    if problems:
        return PipelineResult(status.INVALID, "; ".join(problems[:5]))
    verdict = adaptive.assess(outcome.body, selector, url=url, path=adaptive_path)
    first_run = verdict.status == status.UNCERTAIN and accept_baseline
    if verdict.status != status.OK and not first_run:
        return PipelineResult(verdict.status, verdict.detail)
    df = normalise(table, source_label or pass_.source)
    current = existing(symbol, timeframe)
    if len(current) and _same(current, df):
        return PipelineResult(status.CACHE_HIT, "data unchanged", len(df))
    try:
        write_series(symbol, timeframe, df, replace=replace)
    except TargetNotEmpty as exc:
        return PipelineResult(status.REFUSED, str(exc))
    now = (clock or (lambda: datetime.now(timezone.utc)))()
    provenance.append_record(symbol, timeframe, provenance.build_record(
        pass_, url, df, now, outcome.body_sha256 or hashlib.sha256(outcome.body).hexdigest()))
    if first_run:
        adaptive.remember(outcome.body, selector, url=url, path=adaptive_path)
    return PipelineResult(status.OK, rows=len(df))
