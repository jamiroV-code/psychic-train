"""<timeframe>.provenance.json beside the data file: a list of records, appended atomically."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd

from data_integration import paths
from data_integration.approvals import format_utc

paths._repo_root()
from api.data import cache  # noqa: E402


def provenance_path(symbol: str, timeframe: str) -> Path:
    return cache.ohlcv_path(symbol, timeframe).with_name(f"{timeframe}.provenance.json")


def content_hash(df: pd.DataFrame) -> str:
    return hashlib.sha256(df.to_csv(index=False).encode("utf-8")).hexdigest()


def build_record(pass_, url: str, df: pd.DataFrame, now: datetime) -> dict:
    return {
        "source": pass_.source,
        "tier": pass_.tier,
        "hosts": list(pass_.hosts),
        "pages": list(pass_.pages),
        "url": url,
        "fetched_at": format_utc(now),
        "rows": len(df),
        "columns": list(df.columns),
        "content_sha256": content_hash(df),
    }


def read_records(symbol: str, timeframe: str) -> list[dict]:
    path = provenance_path(symbol, timeframe)
    if not path.is_file():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def append_record(symbol: str, timeframe: str, record: dict) -> None:
    path = provenance_path(symbol, timeframe)
    path.parent.mkdir(parents=True, exist_ok=True)
    records = read_records(symbol, timeframe) + [record]
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(records, fh, indent=2)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
