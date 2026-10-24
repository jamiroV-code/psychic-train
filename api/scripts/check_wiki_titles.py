"""Check candidate English Wikipedia titles against the REST summary endpoint (T102).

Run from the repo root: uv run --project api python -m api.scripts.check_wiki_titles
Reads a symbol -> title JSON map, prints one line per coin and a paste-ready JSON of PASS entries.
Writes nothing to the repo. Exit code 0 unless the file is unreadable.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import httpx

from api.data.attention.wikipedia import USER_AGENT

SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
DEFAULT_FILE = Path(__file__).resolve().parents[1] / "data" / "wiki_articles_candidates.json"
INTERVAL_SECONDS = 1.0
TIMEOUT_SECONDS = 10.0
CRYPTO_WORDS = ("cryptocurrency", "blockchain", "token", "coin", "protocol", "decentralized", "network")


@dataclass
class Result:
    symbol: str
    title: str
    status: int | None = None
    page_type: str = ""
    description: str = ""
    extract: str = ""
    verdict: str = "FAIL"
    reason: str = ""


def check_title(client: httpx.Client, symbol: str, title: str) -> Result:
    res = Result(symbol, title)
    url = SUMMARY_URL.format(title=quote(title.replace(" ", "_"), safe="()_.,'-"))
    try:
        resp = client.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_SECONDS,
                          follow_redirects=True)
    except Exception as exc:
        res.reason = f"request failed: {type(exc).__name__}"
        return res
    res.status = resp.status_code
    if resp.status_code != 200:
        res.reason = f"HTTP {resp.status_code}"
        return res
    try:
        body = resp.json()
        res.page_type = str(body.get("type") or "other")
        res.description = str(body.get("description") or "")
        res.extract = str(body.get("extract") or "")
    except Exception as exc:
        res.reason = f"bad JSON: {type(exc).__name__}"
        return res
    if res.page_type == "disambiguation":
        res.reason = "type disambiguation"
    elif res.page_type != "standard":
        res.page_type = "other"
        res.reason = "type other"
    else:
        text = f"{res.description} {res.extract}".lower()
        if any(w in text for w in CRYPTO_WORDS):
            res.verdict = "PASS"
        else:
            res.reason = "no crypto-related words in description/extract"
    return res


def run(mapping: dict, *, client: httpx.Client, sleep=time.sleep, out=sys.stdout) -> list[Result]:
    items = [(s, t) for s, t in mapping.items() if t]
    results: list[Result] = []
    for i, (sym, title) in enumerate(items):
        if i:
            sleep(INTERVAL_SECONDS)
        r = check_title(client, sym, title)
        results.append(r)
        print(f"{sym} | {title} | HTTP {r.status if r.status is not None else '-'} | "
              f"{r.page_type or '-'} | {r.description or '-'} | {r.extract[:100]!r} | "
              f"{r.verdict}{' (' + r.reason + ')' if r.reason else ''}", file=out)
    passed = {r.symbol: r.title for r in results if r.verdict == "PASS"}
    print(f"\nPASS: {len(passed)}  FAIL: {len(results) - len(passed)}\n", file=out)
    print(json.dumps(passed, indent=2), file=out)
    return results


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--file", type=Path, default=DEFAULT_FILE)
    args = ap.parse_args(argv)
    try:
        mapping = json.loads(args.file.read_text(encoding="utf-8"))
        if not isinstance(mapping, dict):
            raise ValueError("not an object")
    except (OSError, ValueError) as exc:
        print(f"cannot read {args.file}: {type(exc).__name__}", file=sys.stderr)
        return 2
    with httpx.Client(follow_redirects=True) as client:
        run(mapping, client=client)
    return 0


if __name__ == "__main__":
    sys.exit(main())
