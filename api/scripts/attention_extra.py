"""Verifier for the attention-refresh `refresh-extra` job (pure classifier plus a thin log reader).

Each extra source prints one `source: ...` line (refresh_attention.py). A provider block
(HTTP 4xx/5xx, timeouts, rate limits) is `unavailable`: a yellow ::warning::, no probe record,
no failure. A line whose reasons are mostly code errors (exception classes outside PROVIDER_CLASSES, no HTTP
status), an `error` line that is not a provider failure, or a missing line is `failed`.
"""
from __future__ import annotations

import os
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import NamedTuple

if __package__ in (None, ""):  # direct invocation
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from api.scripts import attention_freshness  # noqa: E402

EXTRA_SOURCES = ("exchange_volume", "hyperliquid_volume", "trends", "reddit")
# Exception classes that mean "the provider said no / was unreachable", not "our code is broken".
PROVIDER_CLASSES = ("HTTPStatusError", "ConnectError", "ConnectTimeout", "ReadTimeout", "ReadError", "TimeoutException",
                    "RemoteProtocolError", "NetworkError", "RequestTimeout", "ExchangeNotAvailable",
                    "RateLimitExceeded", "DDoSProtection", "TooManyRequests")


# Reasons that are data outcomes (nothing to fix in our code); never trip the breaker, never make a line red.
DATA_REASONS = ("no keyword mapped", "bad date", "partial row dropped", "empty response", "presumed-dead",
                "symbol not listed or no volume", "snapshot unavailable")
DATA_CLASSES = ("BadSymbol",)
_CODE_REASON = re.compile(r"(?:fetch|parse)-failed: (\w+)")


def reason_kind(reason: str) -> str:
    """'code' = an exception class outside PROVIDER_CLASSES with no HTTP status; 'data' = a plain data outcome;
    'provider' = everything else (HTTP status, provider class, rate limit, token/search failure, skips)."""
    r = reason.strip()
    if r in DATA_REASONS:
        return "data"
    m = _CODE_REASON.fullmatch(r)
    if m and m.group(1) in DATA_CLASSES:
        return "data"
    if m and m.group(1) not in PROVIDER_CLASSES:
        return "code"
    return "provider"


def _reasons_failed(text: str) -> bool:
    """True when the listed reasons are mostly code errors: code weight >= provider-or-data weight."""
    code = other = 0
    for part in text.split(";"):
        part = part.strip()
        if not part:
            continue
        m = re.search(r"\s+x(\d+)$", part)
        n = int(m.group(1)) if m else 1
        part = part[:m.start()] if m else part
        if reason_kind(part) == "code":
            code += n
        else:
            other += n
    return code > 0 and code >= other


class Result(NamedTuple):
    status: str  # ok | unavailable | not-probed | failed
    detail: str


def _clean(text: str, limit: int = 200) -> str:
    """One ASCII line with no workflow-command syntax."""
    out = re.sub(r"\s+", " ", text.encode("ascii", "replace").decode("ascii")).replace("::", ": ").replace("%", "")
    return out.strip()[:limit]


def classify(source: str, line: str | None) -> Result:
    if not line:
        return Result("failed", "no result line (step crashed or timed out)")
    rest = line[len(source) + 1:].strip()
    if rest.startswith("not-probed"):
        return Result("not-probed", _clean(rest[len("not-probed"):]) or "not probed")
    if rest.startswith("error "):
        err = rest[len("error "):]
        head = err.split(":", 1)[0]
        if re.search(r"\bHTTP [45]\d\d\b", head) or head.split(" ")[0] in PROVIDER_CLASSES:
            return Result("unavailable", _clean(err))
        return Result("failed", _clean(err))
    m = re.match(r"(\d+)/(\d+) ok, (\d+) rows written", rest)
    if not m or int(m.group(2)) == 0:
        return Result("failed", _clean(rest) or "unparseable result line")
    if int(m.group(1)) > 0 or int(m.group(3)) > 0:
        return Result("ok", _clean(rest))
    if "reasons:" in rest and _reasons_failed(rest.split("reasons:", 1)[1]):
        return Result("failed", _clean(rest))  # every/most reasons are code errors, not provider blocks
    return Result("unavailable", _clean(rest))  # every series was a provider/data outcome, nothing stored


def latest_day(source: str, root: Path) -> str | None:
    import pandas as pd
    days = [pd.read_parquet(p)["date"].max() for p in (root / source).glob("*.parquet")]
    return max(days).date().isoformat() if days else None


def verify(logs: dict[str, str | None], root: Path, today: date) -> tuple[list[str], list[str], list[str]]:
    """Returns (summary lines, sources to probe, failed sources); also yields ::warning:: lines in the summary."""
    out, probe, failed = [], [], []
    for src in EXTRA_SOURCES:
        lines = [ln for ln in (logs.get(src) or "").splitlines() if ln.startswith(src + ":")]
        r = classify(src, lines[-1] if lines else None)
        status, detail = r
        if status == "ok":
            latest = latest_day(src, root)
            v = attention_freshness.judge(src, latest, today)
            detail += f", latest day {latest}, stale before {v.threshold}"
            if v.ok:
                probe.append(src)
            else:
                status, detail = "failed", f"{v.reason}; {detail}"
        if status == "failed":
            failed.append(src)
        if status == "unavailable":
            out.append(f"::warning::attention source {src} unavailable: {detail}")
        out.append(f"summary {src}: {status} - {detail}")
    return out, probe, failed


def main() -> int:
    tmp = Path(os.environ["RUNNER_TEMP"])
    logs = {s: (tmp / f"extra-{s}.log").read_text() if (tmp / f"extra-{s}.log").exists() else None
            for s in EXTRA_SOURCES}
    root = Path("api/data/cache/attention")
    out, probe, failed = verify(logs, root, datetime.now(timezone.utc).date())
    print("\n".join(out))
    (tmp / "attention-extra-ok.txt").write_text(",".join(probe))
    if failed:
        print(f"::error::attention extra refresh failed (code error or missing result) for: {', '.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
