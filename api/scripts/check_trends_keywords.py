"""Check coin names against Google Trends suggestions and propose topic ids (T100a, v3 T155).

Run from the repo root: uv run --project api --with pytrends python -m api.scripts.check_trends_keywords
Reads a symbol -> name JSON map (default: the labels of api/data/trends_keywords.json), prints one line per
coin, a paste-ready JSON of PASS entries and a 'needs a decision' block (each AMBIGUOUS coin with its first
exact-name candidate and a Trends link to check it by eye). Writes nothing. Exit 0 (also after a 429 stop), 1 if the Trends
session cannot start, 2 if the input is unreadable, 3 if pytrends is not installed, 130 after Ctrl-C.
Starting the session sends one cookie request to Google before the per-coin calls.
PowerShell: quote comma lists, e.g. --symbols 'LINK,AAVE'.
--only-unresolved checks only coins with no `topic` entry in trends_keywords.json and turns on --variants: each
coin is also queried as '<name> crypto', '<name> coin' and '<ticker> crypto' (at most 4 queries per coin, 3 s
apart; the expected request count and minutes print first). Candidates are merged by topic id, each tagged with
the query that found it. Examples:
  uv run --project api --with pytrends python -m api.scripts.check_trends_keywords --only-unresolved
  uv run --project api --with pytrends python -m api.scripts.check_trends_keywords --only-unresolved --symbols 'AVAX,SUI'
With variants, a coin still AMBIGUOUS gets a paste-ready qualified term ('avalanche crypto') in a 'qualified term
proposals' block: lower confidence than a topic, never a checker PASS. A coin with a failed query cannot PASS and
gets no term; re-run it. Ctrl-C stops the run, prints the partial results and exits 130.
PASS needs exactly one crypto-typed candidate whose title equals the name. Failing that, the only crypto-typed
candidate passes when it is the name plus a generic word ("Kaspa Network") or a 4+ character start of the name
before one ("NEAR" for NEAR Protocol); "Ethereum Classic" for Ethereum never does. A label that is only the
ticker passes only on a title equal to the ticker; there is no display name to try. A named coin's only
crypto-typed candidate also passes when its title is the ticker in any case ("ETC") or the name with a crypto
qualifier in brackets ("Stacks (cryptocurrency)").
Eyeball every PASS line (title against the coin name) before pasting the block.
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
# CRYPTO_SUBSTRINGS may sit anywhere in the type, CRYPTO_WORDS only as whole words ("Tokenization company" is
# out), and CRYPTO_PHRASES only as the whole type ("Chain" is in, "Restaurant chain" and "Internet protocol" out).
CRYPTO_SUBSTRINGS = ("cryptocurrency", "blockchain")
CRYPTO_WORDS = ("token", "coin", "digital currency", "virtual currency")
CRYPTO_PHRASES = ("currency", "chain", "distributed ledger", "payment network", "decentralized finance",
                  "decentralized finance protocol", "decentralized exchange", "defi protocol")
CRYPTO_TYPE_WORDS = CRYPTO_SUBSTRINGS + CRYPTO_WORDS + CRYPTO_PHRASES + (
    "blockchain platform", "cryptocurrency exchange company")
PREFIX_MIN = 4
# What may follow a prefix title in the name: "World" -> Worldcoin, "NEAR" -> NEAR Protocol; never "Bitcoin" ->
# Bitcoin Cash or "Ethereum" -> Ethereum Classic.
PREFIX_SUFFIXES = ("coin", "protocol", "network", "token", "chain", "blockchain", "finance")
# What may follow the name in a longer title: "Kaspa Network"; never "Ethereum Classic", "Bitcoin SV",
# "Sky Mavis", "Sky Protocol" or "Polygon zkEVM" (other coins or companies).
CONTAINED_SUFFIXES = ("coin", "token", "network", "blockchain", "cryptocurrency")
VERIFY_URL = "https://trends.google.com/trends/explore?q={}"
PASTE_HEADER = "--- paste-ready JSON (PASS entries) ---"
DECISION_HEADER = "--- needs a decision ---"
NOT_RUN_REASON = f"stopped after {MAX_CONSECUTIVE_429} consecutive HTTP 429"
INTERRUPTED_REASON = "interrupted (Ctrl-C)"
INTERRUPTED_EXIT = 130
# T155: extra suggestion queries per coin; the plain name hides the crypto entity for common words (Avalanche,
# Cosmos, Sui). "{name} coin" is skipped for a name that already holds the word ("Pepe coin").
VARIANT_TEMPLATES = ("{name} crypto", "{name} coin", "{ticker} crypto")
MAX_QUERIES_PER_COIN = 4
QUALIFIER_WORDS = ("crypto", "coin", "token")
BRACKET_QUALIFIERS = ("crypto", "cryptocurrency", "coin", "token", "blockchain")
QUALIFIED_HEADER = "--- qualified term proposals (lower confidence than topics) ---"


@dataclass
class Result:
    symbol: str
    name: str
    candidates: list[dict] = field(default_factory=list)
    proposed: dict | None = None
    verdict: str = "FAIL"
    reason: str = ""
    rate_limited: bool = False
    found_by: dict[str, list[str]] = field(default_factory=dict)
    failed: list[str] = field(default_factory=list)
    queries: int = 1
    done: int = 0

    @property
    def complete(self) -> bool:
        return not self.failed and self.done == self.queries


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
    return (t in CRYPTO_PHRASES or any(w in t for w in CRYPTO_SUBSTRINGS)
            or any(f" {w} " in f" {t} " for w in CRYPTO_WORDS))


def _exact_match(title: str, name: str) -> bool:
    n = _norm(name)
    return bool(n) and _norm(title) == n


def _contained_match(title: str, name: str) -> bool:
    t, n = _norm(title), _norm(name)
    return bool(n) and t.startswith(n + " ") and t[len(n):].strip() in CONTAINED_SUFFIXES


def _prefix_match(title: str, name: str) -> bool:
    t, n = _norm(title), _norm(name)
    return len(t) >= PREFIX_MIN and n.startswith(t) and n[len(t):].strip() in PREFIX_SUFFIXES


def _bracket_match(title: str, name: str) -> bool:
    m = re.fullmatch(r"(.+?)\s*\(([^()]+)\)", title.strip())
    return bool(m) and _exact_match(m.group(1), name) and _norm(m.group(2)) in BRACKET_QUALIFIERS


def _ticker_match(title: str, symbol: str) -> bool:
    return title.strip().casefold() == symbol.casefold()


def queries_for(symbol: str, name: str) -> list[str]:
    """The name first, then the variants; identical strings (case-insensitive) once, at most MAX_QUERIES_PER_COIN."""
    words = set(_norm(name).split())
    out: list[str] = []
    for q in (name, *(t.format(name=name, ticker=symbol) for t in VARIANT_TEMPLATES)):
        if q.startswith(name + " ") and _norm(q[len(name):]) in words:
            continue
        if q.casefold() not in {x.casefold() for x in out}:
            out.append(q)
    return out[:MAX_QUERIES_PER_COIN]


def qualified_term(symbol: str, name: str) -> str | None:
    """'<name> crypto' in lower case, or the name alone when it already ends in a qualifier word."""
    if name == symbol or not name.isascii():
        return None
    base = name.strip().lower()
    term = base if set(_norm(base).split()) & set(QUALIFIER_WORDS) else f"{base} crypto"
    return term if tk.is_valid_term(term) else None


def _fallback(name: str) -> str:
    return "falls back to term" if tk.is_valid_term(name) else "needs a human"


def _verdict(res: Result, loose: bool) -> None:
    """v2 rules; `loose` (variant runs, T155) also lets the only crypto-typed candidate pass on the ticker or on
    the name with a bracketed crypto qualifier."""
    symbol, name = res.symbol, res.name
    crypto = [c for c in res.candidates if is_crypto_type(c["type"])]
    ticker = name == symbol
    if ticker:
        hits = [c for c in crypto if c["title"].strip() == symbol]
    else:
        hits = [c for c in crypto if _exact_match(c["title"], name)]
        if not hits and len(crypto) == 1 and (_contained_match(crypto[0]["title"], name)
                                              or _prefix_match(crypto[0]["title"], name)
                                              or loose and (_bracket_match(crypto[0]["title"], name)
                                                            or _ticker_match(crypto[0]["title"], symbol))):
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


def _merge(res: Result, query: str, raw) -> None:
    for c in _usable(raw):
        if c["mid"] not in res.found_by:
            res.candidates.append(c)
            res.found_by[c["mid"]] = []
        if query not in res.found_by[c["mid"]]:
            res.found_by[c["mid"]].append(query)


def _settle(res: Result, interrupted: bool, loose: bool) -> Result:
    """Verdict from the merged candidates; an incomplete check (failed, skipped or interrupted queries) never PASSes."""
    if res.failed and len(res.failed) == res.done:
        res.reason = f"request failed: {res.failed[0]}; {_fallback(res.name)}"
        if interrupted:
            res.reason += f"; {INTERRUPTED_REASON}"
        return res
    _verdict(res, loose)
    why = []
    if res.failed:
        why.append(f"{len(res.failed)} of {res.queries} queries failed: {', '.join(dict.fromkeys(res.failed))}")
    if interrupted:
        why.append(INTERRUPTED_REASON)
    elif res.queries > res.done:
        why.append(f"{res.queries - res.done} of {res.queries} queries not run")
    if res.verdict == "PASS" and not res.complete:
        res.verdict, res.proposed, res.reason = "AMBIGUOUS", None, "a crypto-typed title passed on part of the queries"
    if why:
        res.reason = "; ".join([res.reason, *why]) if res.reason else "; ".join(why)
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
    exact = next((c for c in r.candidates if _exact_match(c["title"], r.name)), None)
    return f"    verify {_cand(exact)}: {VERIFY_URL.format(quote(exact['mid'], safe=''))}" if exact else None


def _plan_line(n_coins: int, n_requests: int) -> str:
    minutes = round(max(n_requests - 1, 0) * INTERVAL_SECONDS / 60)
    return f"plan: {n_coins} coins, {n_requests} requests, about {minutes} min ({INTERVAL_SECONDS:g} s apart)"


def _query_coins(mapping: dict, client, sleep, variants: bool) -> tuple[list[Result], int, bool]:
    """Every request is INTERVAL_SECONDS after the previous one; MAX_CONSECUTIVE_429 in a row (across coins)
    stop the run. Returns (results, requests sent, interrupted)."""
    results: list[Result] = []
    streak = sent = 0
    interrupted = False
    for sym, name in mapping.items():
        if interrupted or streak >= MAX_CONSECUTIVE_429:
            reason = INTERRUPTED_REASON if interrupted else NOT_RUN_REASON
            results.append(Result(sym, name, verdict="NOT-RUN", reason=reason))
            continue
        queries = queries_for(sym, name) if variants else [name]
        res = Result(sym, name, queries=len(queries))
        try:
            for q in queries:
                if streak >= MAX_CONSECUTIVE_429:
                    break
                if sent:
                    sleep(INTERVAL_SECONDS)
                sent += 1
                try:
                    raw = client.suggestions(q)
                except Exception as exc:  # noqa: BLE001 - the class is reported, never the message
                    res.done += 1
                    res.failed.append(error_class(exc))
                    streak = streak + 1 if is_rate_limited(exc) else 0
                    continue
                res.done += 1
                streak = 0
                _merge(res, q, raw)
        except KeyboardInterrupt:
            interrupted = True
        if interrupted and res.done == 0:
            results.append(Result(sym, name, verdict="NOT-RUN", reason=INTERRUPTED_REASON))
        else:
            results.append(_settle(res, interrupted, loose=variants))
    return results, sent, interrupted


def _cand_via(r: Result, c: dict, variants: bool) -> str:
    if not variants:
        return _cand(c)
    return _cand(c) + " via " + ", ".join(f"'{q}'" for q in r.found_by.get(c["mid"], []))


def _print_qualified(results: list[Result], stamp: str, out) -> None:
    taken = {e["term"].casefold(): s for s, e in tk.load().entries.items() if "term" in e}
    block: dict[str, dict] = {}
    skipped: list[str] = []
    for r in results:
        if r.verdict != "AMBIGUOUS" or not r.complete:
            continue
        term = qualified_term(r.symbol, r.name)
        if term is None:
            why = ("label is only the ticker; the owner names it" if r.name == r.symbol
                   else "the name is not a safe ASCII term; the owner picks one")
            skipped.append(f"{r.symbol} | no qualified term: {why}")
        elif taken.get(term.casefold(), r.symbol) != r.symbol:
            skipped.append(f"{r.symbol} | no qualified term: '{term}' is already used")
        else:
            taken[term.casefold()] = r.symbol
            block[r.symbol] = {"term": term, "label": r.name if tk.is_valid_label(r.name) else r.symbol,
                               "note": f"qualified-term fallback {stamp}, not checker PASS"}
    print(f"\n{QUALIFIED_HEADER}\n{json.dumps(block, indent=2)}", file=out)
    for line in skipped:
        print(line, file=out)


def run(mapping: dict, *, client, sleep=time.sleep, out=None, now=None, variants: bool = False) -> list[Result]:
    out = out or sys.stdout
    now = now or (lambda: datetime.now(timezone.utc))
    planned = sum(len(queries_for(s, n)) if variants else 1 for s, n in mapping.items())
    print(_plan_line(len(mapping), planned), file=out, flush=True)
    results, sent, _ = _query_coins(mapping, client, sleep, variants)
    _demote_duplicate_topics(results)

    for r in results:
        if r.verdict == "NOT-RUN":
            print(f"{r.symbol} | {r.name} | - | - | NOT-RUN ({r.reason})", file=out)
            continue
        proposed = f"proposed {_cand_via(r, r.proposed, variants)}" if r.proposed else "-"
        tail = f" ({r.reason})" if r.reason else ""
        print(f"{r.symbol} | {r.name} | {len(r.candidates)} candidates | {proposed} | {r.verdict}{tail}", file=out)
        if r.verdict == "AMBIGUOUS":
            for c in r.candidates:
                print(f"    {_cand_via(r, c, variants)}", file=out)
    counts = {v: sum(r.verdict == v for r in results) for v in ("PASS", "AMBIGUOUS", "FAIL", "NOT-RUN")}
    print("\n" + " ".join(f"{v}: {n}" for v, n in counts.items()), file=out)
    print(f"requests sent: {sent}", file=out)

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
    if variants:
        _print_qualified(results, stamp, out)
    return results


def unresolved_symbols(keyword_map) -> list[str]:
    return [s for s, e in keyword_map.entries.items() if "topic" not in e]


def _default_mapping() -> dict:
    return {sym: e["label"] for sym, e in tk.load().entries.items()}


def main(argv: list[str] | None = None, *, trendreq_factory=make_trendreq, sleep=time.sleep, out=None,
         err=None, now=None) -> int:
    out, err = out or sys.stdout, err or sys.stderr
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--file", type=Path, default=None, help="symbol -> name JSON map")
    ap.add_argument("--symbols", default=None, help="comma-separated subset, e.g. LINK,AAVE")
    ap.add_argument("--only-unresolved", action="store_true",
                    help="only coins with no topic in trends_keywords.json; implies --variants")
    ap.add_argument("--variants", action="store_true", help="also query '<name> crypto', '<name> coin', '<ticker> crypto'")
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
    if args.only_unresolved:
        keep = set(unresolved_symbols(tk.load()))
        mapping = {s: n for s, n in mapping.items() if s in keep}
    client, code = start_client(trendreq_factory, "check_trends_keywords", err)
    if client is None:
        return code
    results = run(mapping, client=client, sleep=sleep, out=out, now=now,
                  variants=args.variants or args.only_unresolved)
    return INTERRUPTED_EXIT if any(INTERRUPTED_REASON in r.reason for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
