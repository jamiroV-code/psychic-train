"""Check coin names against Google Trends suggestions and propose topic ids (T100a).

Run from the repo root: uv run --project api --with pytrends python -m api.scripts.check_trends_keywords
Reads a symbol -> name JSON map (default: the labels of api/data/trends_keywords.json), prints one line per
coin, a paste-ready JSON of PASS entries and a 'needs a decision' block (each AMBIGUOUS coin with its first
exact-name candidate and a Trends link to check it by eye). Writes nothing. Exit 0 (also after a 429 stop), 1 if the Trends
session cannot start, 2 if the input is unreadable, 3 if pytrends is not installed.
Starting the session sends one cookie request to Google before the per-coin calls.
PowerShell: quote comma lists, e.g. --symbols 'LINK,AAVE'.
PASS needs exactly one crypto-typed candidate whose title equals or contains the name (or, when it is the only
crypto-typed candidate, a title of 4+ characters that starts the name before a generic suffix, e.g. NEAR for NEAR Protocol). A label
that is only the ticker passes only on a title equal to the ticker; there is no display name to try.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from api.data.attention import trends_keywords as tk
from api.scripts.trends_cli_common import (
    error_class,
    is_rate_limited,
    make_trendreq,
    start_client,
)

INTERVAL_SECONDS = 3.0
MAX_CONSECUTIVE_429 = 3
# Google `type` strings seen in the owner's run of 21-10-26 (T134): Currency, Coin, Chain, Blockchain,
# Blockchain platform, Distributed ledger, Payment network, Cryptocurrency, Cryptocurrency exchange company.
# Generic types (Topic, Software, Company, Website, Computer program) stay out: a hit there needs the owner.
# CRYPTO_SUBSTRINGS may sit inside a longer type; the other words count only as the whole type
# ("Chain" is crypto-typed, "Restaurant chain" is not).
CRYPTO_SUBSTRINGS = ("cryptocurrency", "blockchain", "token", "coin", "digital currency", "virtual currency",
                     "protocol", "decentralized")
CRYPTO_TYPE_WORDS = CRYPTO_SUBSTRINGS + ("currency", "chain", "blockchain platform", "distributed ledger",
                                         "payment network", "cryptocurrency exchange company")
PREFIX_MIN = 4
# What may follow a prefix title in the name: "World" -> Worldcoin, "NEAR" -> NEAR Protocol; never "Bitcoin" ->
# Bitcoin Cash or "Ethereum" -> Ethereum Classic.
PREFIX_SUFFIXES = ("coin", "protocol", "network", "token", "chain", "blockchain", "finance")
VERIFY_URL = "https://trends.google.com/trends/explore?q={}"
PASTE_HEADER = "--- paste-ready JSON (PASS entries) ---"
DECISION_HEADER = "--- needs a decision ---"
NOT_RUN_REASON = f"stopped after {MAX_CONSECUTIVE_429} consecutive HTTP 429"


@dataclass
class Result:
    symbol: str
    name: str
    candidates: list[dict] = field(default_factory=list)
    proposed: dict | None = None
    verdict: str = "FAIL"
    reason: str = ""
    rate_limited: bool = False


def _usable(raw) -> list[dict]:
    out = []
    for c in raw if isinstance(raw, list) else []:
        if not isinstance(c, dict):
            continue
        mid, title, type_ = c.get("mid"), c.get("title"), c.get("type")
        if tk.is_valid_topic(mid) and isinstance(title, str) and title.strip() and isinstance(type_, str) and type_.strip():
            out.append({"mid": mid, "title": title[:80], "type": type_[:80]})
    return out


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^0-9a-z]+", " ", text.casefold()).split())


def is_crypto_type(type_: str) -> bool:
    t = _norm(type_)
    return t in CRYPTO_TYPE_WORDS or any(w in t for w in CRYPTO_SUBSTRINGS)


def _names_match(title: str, name: str) -> bool:
    t, n = _norm(title), _norm(name)
    return bool(n) and f" {n} " in f" {t} "


def _prefix_match(title: str, name: str) -> bool:
    t, n = _norm(title), _norm(name)
    return len(t) >= PREFIX_MIN and n.startswith(t) and n[len(t):].strip() in PREFIX_SUFFIXES


def _fallback(name: str) -> str:
    return "falls back to term" if tk.is_valid_term(name) else "needs a human"


def check_name(client, symbol: str, name: str) -> Result:
    res = Result(symbol, name)
    try:
        raw = client.suggestions(name)
    except Exception as exc:  # noqa: BLE001 - the class is reported, never the message
        res.rate_limited = is_rate_limited(exc)
        res.reason = f"request failed: {error_class(exc)}; {_fallback(name)}"
        return res
    res.candidates = _usable(raw)
    crypto = [c for c in res.candidates if is_crypto_type(c["type"])]
    ticker = name == symbol
    if ticker:
        hits = [c for c in crypto if c["title"].strip() == symbol]
    else:
        hits = [c for c in crypto if _names_match(c["title"], name)]
        if not hits and len(crypto) == 1 and _prefix_match(crypto[0]["title"], name):
            hits = crypto
    if len(hits) == 1:
        res.verdict, res.proposed = "PASS", hits[0]
    elif ticker and crypto and not hits:
        res.verdict, res.reason = "AMBIGUOUS", "label is only the ticker; no display name in narratives/universe"
    elif len(crypto) == 1:
        res.verdict, res.reason = "AMBIGUOUS", "title does not contain the name"
    elif len(crypto) > 1:
        res.verdict, res.reason = "AMBIGUOUS", "several crypto-typed candidates"
    elif res.candidates:
        res.verdict, res.reason = "AMBIGUOUS", "no crypto-typed candidate"
    else:
        res.reason = f"no usable candidate; {_fallback(name)}"
    return res


def _demote_duplicate_topics(results: list[Result]) -> None:
    by_mid: dict[str, list[Result]] = {}
    for r in results:
        if r.verdict == "PASS":
            by_mid.setdefault(r.proposed["mid"], []).append(r)
    for group in by_mid.values():
        if len(group) > 1:
            for r in group:
                r.verdict, r.proposed, r.reason = "AMBIGUOUS", None, "same topic proposed for several coins"


def _cand(c: dict) -> str:
    return f'{c["mid"]} "{c["title"]}" ({c["type"]})'


def _verify_hint(r: Result) -> str | None:
    exact = next((c for c in r.candidates if _norm(c["title"]) == _norm(r.name)), None)
    return f"    verify {_cand(exact)}: {VERIFY_URL.format(quote(exact['mid'], safe=''))}" if exact else None


def run(mapping: dict, *, client, sleep=time.sleep, out=None, now=None) -> list[Result]:
    out = out or sys.stdout
    now = now or (lambda: datetime.now(timezone.utc))
    results: list[Result] = []
    streak = 0
    calls = 0
    for sym, name in mapping.items():
        if streak >= MAX_CONSECUTIVE_429:
            results.append(Result(sym, name, verdict="NOT-RUN", reason=NOT_RUN_REASON))
            continue
        if calls:
            sleep(INTERVAL_SECONDS)
        calls += 1
        r = check_name(client, sym, name)
        streak = streak + 1 if r.rate_limited else 0
        results.append(r)
    _demote_duplicate_topics(results)

    for r in results:
        if r.verdict == "NOT-RUN":
            print(f"{r.symbol} | {r.name} | - | - | NOT-RUN ({r.reason})", file=out)
            continue
        proposed = f"proposed {_cand(r.proposed)}" if r.proposed else "-"
        tail = f" ({r.reason})" if r.reason else ""
        print(f"{r.symbol} | {r.name} | {len(r.candidates)} candidates | {proposed} | {r.verdict}{tail}", file=out)
        if r.verdict == "AMBIGUOUS":
            for c in r.candidates:
                print(f"    {_cand(c)}", file=out)
    counts = {v: sum(r.verdict == v for r in results) for v in ("PASS", "AMBIGUOUS", "FAIL", "NOT-RUN")}
    print("\n" + " ".join(f"{v}: {n}" for v, n in counts.items()), file=out)

    stamp = now().strftime("%d-%m-%y")
    block = {r.symbol: {"topic": r.proposed["mid"], "label": r.name if tk.is_valid_label(r.name) else r.symbol,
                        "note": f"checker PASS {stamp}"}
             for r in results if r.verdict == "PASS"}
    print(f"\n{PASTE_HEADER}\n{json.dumps(block, indent=2)}\n{DECISION_HEADER}", file=out)
    for r in results:
        if r.verdict in ("AMBIGUOUS", "FAIL"):
            print(f"{r.symbol} | {r.verdict} | {r.reason}", file=out)
            hint = _verify_hint(r) if r.verdict == "AMBIGUOUS" else None
            if hint:
                print(hint, file=out)
    return results


def _default_mapping() -> dict:
    return {sym: e["label"] for sym, e in tk.load().entries.items()}


def main(argv: list[str] | None = None, *, trendreq_factory=make_trendreq, sleep=time.sleep, out=None,
         err=None, now=None) -> int:
    out, err = out or sys.stdout, err or sys.stderr
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--file", type=Path, default=None, help="symbol -> name JSON map")
    ap.add_argument("--symbols", default=None, help="comma-separated subset, e.g. LINK,AAVE")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    try:
        if args.file is None:
            mapping = _default_mapping()
        else:
            mapping = json.loads(args.file.read_bytes().decode("utf-8"))
        if not isinstance(mapping, dict) or not all(isinstance(v, str) for v in mapping.values()):
            raise ValueError("not an object of strings")
    except (OSError, ValueError) as exc:
        print(f"cannot read the input map: {type(exc).__name__}", file=err)
        return 2
    if args.symbols:
        wanted = [s.strip() for s in args.symbols.split(",") if s.strip()]
        if not all(tk.SYMBOL_RE.fullmatch(s) for s in wanted):
            print(f"--symbols must be comma-separated symbols matching {tk.SYMBOL_RE.pattern}", file=err)
            return 2
        mapping = {s: mapping[s] for s in wanted if s in mapping}
    client, code = start_client(trendreq_factory, "check_trends_keywords", err)
    if client is None:
        return code
    run(mapping, client=client, sleep=sleep, out=out, now=now)
    return 0


if __name__ == "__main__":
    sys.exit(main())
