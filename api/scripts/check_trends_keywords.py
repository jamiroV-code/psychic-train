"""Check coin names against Google Trends suggestions and propose topic ids (T100a, v3 T155, T161).

Run from the repo root: uv run --project api --with pytrends python -m api.scripts.check_trends_keywords
Reads a symbol -> name JSON map (default, T155: every coin in api/data/trends_keywords.json with its label, then
every Discovery-eligible coin of the latest universe snapshot that has no entry, named from its CoinGecko id;
those names are listed first, check them), prints one line per coin, a paste-ready JSON of PASS entries and a 'needs a decision' block (each AMBIGUOUS coin with its first
exact-name candidate and a Trends link to check it by eye). Writes nothing. Exit 0, 1 if the Trends session cannot start, 2 if the
input or an option is bad, 3 if pytrends is not installed, 4 when Google refused and the run stopped, 130 after Ctrl-C.
Starting the session sends one cookie request to Google before the per-coin calls.
PowerShell: quote comma lists, e.g. --symbols 'LINK,AAVE'.
Requests go 3 s apart (--delay S raises it), with a 20 s pause every 40 requests (--pause-every N, 0 = never;
--pause-s S; --delay and --pause-s must be finite and at most 3600); the expected request count and minutes
print first. Three failed requests in a row of any kind
(ConnectionError, timeout, 429, 5xx) mean Google is refusing us: the run stops sending, marks the rest NOT-RUN,
prints the command options to re-run after 30-60 minutes (the NOT-RUN coins plus every coin whose request failed,
with --file, --only-unresolved, --variants and any non-default pacing echoed) and exits 4 (T161: on 23-10-26 every request after about
100 failed with ConnectionError and the run kept sending to 137).
--only-unresolved checks only those coins with no `topic` entry (or no entry at all), one request per coin.
--variants also queries each coin as '<name> crypto', '<name> coin' and '<ticker> crypto' (at most 4 queries per
coin), merging candidates by topic id, each tagged with the query that found it. It is opt-in since T161: in the
owner's run of 23-10-26 the variants found no crypto-typed topic for 13 of 13 ambiguous coins (they return books,
products and apartments), at four times the requests. Examples:
  uv run --project api --with pytrends python -m api.scripts.check_trends_keywords --only-unresolved
  uv run --project api --with pytrends python -m api.scripts.check_trends_keywords --only-unresolved --symbols 'AVAX,SUI'
  uv run --project api --with pytrends python -m api.scripts.check_trends_keywords --only-unresolved --variants --delay 5
With --only-unresolved or --variants, a coin still AMBIGUOUS gets a paste-ready qualified term ('avalanche crypto') in a 'qualified term
proposals' block: lower confidence than a topic, never a checker PASS. A coin with a failed query cannot PASS and
gets no term; re-run it. A coin whose request failed is counted as 'request failed' in the coverage line, apart from
'nothing' (a genuine empty answer), even when no 3-in-a-row streak stopped the run (exit stays 0). Ctrl-C stops the run, prints the partial results and exits 130. A last block lists
the proposed symbols outside the narrative-placed set (the loader only warns on them) and the Discovery coverage.
PASS needs exactly one crypto-typed candidate whose title equals the name. Failing that, the only crypto-typed
candidate passes when it is the name plus a generic word ("Kaspa Network") or a 4+ character start of the name
before one ("NEAR" for NEAR Protocol); "Ethereum Classic" for Ethereum never does. A label that is only the
ticker passes only on a title equal to the ticker; there is no display name to try. A named coin's only
crypto-typed candidate also passes when its title is the ticker in any case ("ETC") or the name with a crypto
qualifier in brackets ("Stacks (cryptocurrency)"). Such a PASS is a LEAD, not a match: another coin can share the
ticker (ONE, COMP, LIT, S), so its line names the rule and a Trends link, and its note says "(ticker-title)" or
"(bracket)": open the link and confirm the coin before pasting. A coin named from its CoinGecko id has a guessed
name; its notes say "name from CoinGecko id". A symbol that already holds a topic never gets a qualified term.
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

from api.analytics.attention import discovery, narratives
from api.analytics.attention.universe import load_universe_rows
from api.data.attention import trends_keywords as tk
from api.scripts.trends_cli_common import (
    error_class,
    make_trendreq,
    start_client,
)

INTERVAL_SECONDS = 3.0
# T161: any failure counts (ConnectionError, timeout, 429, 5xx), not only 429.
MAX_CONSECUTIVE_FAILURES = 3
MAX_PACING_SECONDS = 3600.0
PAUSE_EVERY = 40
PAUSE_SECONDS = 20.0
STOPPED_EXIT = 4
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
NOT_RUN_REASON = f"stopped after {MAX_CONSECUTIVE_FAILURES} consecutive failed requests"
INTERRUPTED_REASON = "interrupted (Ctrl-C)"
INTERRUPTED_EXIT = 130
# T155: extra suggestion queries per coin; the plain name hides the crypto entity for common words (Avalanche,
# Cosmos, Sui). "{name} coin" is skipped for a name that already holds the word ("Pepe coin").
VARIANT_TEMPLATES = ("{name} crypto", "{name} coin", "{ticker} crypto")
MAX_QUERIES_PER_COIN = 4
QUALIFIER_WORDS = ("crypto", "coin", "token")
BRACKET_QUALIFIERS = ("crypto", "cryptocurrency", "coin", "token", "blockchain")
QUALIFIED_HEADER = "--- qualified term proposals (lower confidence than topics) ---"
OUTSIDE_HEADER = "--- outside the narrative-placed set ---"
LEAD_RULES = ("ticker-title", "bracket")
LEAD_NOTE = ("a ticker-title or bracket PASS is a LEAD: open its Trends link and confirm the coin before pasting;"
             " notes marked 'name from CoinGecko id' carry a guessed name")
DERIVED_MARK = "name from CoinGecko id"
COVERAGE_KINDS = ("topic", "qualified-term", "term", "nothing", "request failed", "not run", "not checked")


@dataclass
class Pacing:
    """Request spacing in; requests sent and whether the failure breaker stopped the run out."""
    delay: float = INTERVAL_SECONDS
    pause_every: int = PAUSE_EVERY
    pause_s: float = PAUSE_SECONDS
    sent: int = 0
    stopped: bool = False

    def wait(self, sleep) -> None:
        """Before every request but the first: a pause after each `pause_every` requests, then the delay."""
        if not self.sent:
            return
        if self.pause_every and self.sent % self.pause_every == 0:
            sleep(self.pause_s)
        sleep(self.delay)


@dataclass
class Result:
    symbol: str
    name: str
    candidates: list[dict] = field(default_factory=list)
    proposed: dict | None = None
    verdict: str = "FAIL"
    reason: str = ""
    found_by: dict[str, list[str]] = field(default_factory=dict)
    failed: list[str] = field(default_factory=list)
    queries: int = 1
    done: int = 0
    rule: str = ""

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
    rule = "ticker" if ticker else "exact"
    if ticker:
        hits = [c for c in crypto if c["title"].strip() == symbol]
    else:
        hits = [c for c in crypto if _exact_match(c["title"], name)]
        if not hits and len(crypto) == 1:
            title = crypto[0]["title"]
            # Bracket first: "Stacks (cryptocurrency)" also passes the v2 contained rule, but a variant run marks it.
            rule = ("bracket" if loose and _bracket_match(title, name)
                    else "contained" if _contained_match(title, name) else "prefix" if _prefix_match(title, name)
                    else "ticker-title" if loose and _ticker_match(title, symbol) else "")
            hits = crypto if rule else []
    if len(hits) == 1:
        res.verdict, res.proposed, res.rule = "PASS", hits[0], rule
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


def _ps_quote(text: str) -> str:
    """PowerShell single-quoted literal: no expansion, a quote is doubled."""
    return "'" + text.replace("'", "''") + "'"


def _rerun_args(symbols: list[str], extra: tuple[str, ...], variants: bool, pacing: Pacing) -> str:
    """The options for the run-again command: the symbols, then every option the run used that is not a default."""
    parts = [f"--symbols {_ps_quote(','.join(symbols))}", *extra]
    if variants:
        parts.append("--variants")
    if pacing.delay != INTERVAL_SECONDS:
        parts.append(f"--delay {pacing.delay:g}")
    if pacing.pause_every != PAUSE_EVERY:
        parts.append(f"--pause-every {pacing.pause_every}")
    if pacing.pause_s != PAUSE_SECONDS:
        parts.append(f"--pause-s {pacing.pause_s:g}")
    return " ".join(parts)


def _plan_line(n_coins: int, n_requests: int, pacing: Pacing) -> str:
    gaps = max(n_requests - 1, 0)
    pauses = gaps // pacing.pause_every if pacing.pause_every else 0
    minutes = round((gaps * pacing.delay + pauses * pacing.pause_s) / 60)
    pause = f", {pacing.pause_s:g} s pause every {pacing.pause_every}" if pacing.pause_every else ""
    return f"plan: {n_coins} coins, {n_requests} requests, about {minutes} min ({pacing.delay:g} s apart{pause})"


def _query_coins(mapping: dict, client, sleep, variants: bool, pacing: Pacing) -> tuple[list[Result], bool]:
    """Requests are spaced by `pacing`; MAX_CONSECUTIVE_FAILURES failed requests in a row (across coins) stop the
    run and set pacing.stopped. Returns (results, interrupted)."""
    results: list[Result] = []
    streak = 0
    interrupted = False
    for sym, name in mapping.items():
        if interrupted or streak >= MAX_CONSECUTIVE_FAILURES:
            reason = INTERRUPTED_REASON if interrupted else NOT_RUN_REASON
            results.append(Result(sym, name, verdict="NOT-RUN", reason=reason))
            continue
        queries = queries_for(sym, name) if variants else [name]
        res = Result(sym, name, queries=len(queries))
        try:
            for q in queries:
                if streak >= MAX_CONSECUTIVE_FAILURES:
                    break
                pacing.wait(sleep)
                pacing.sent += 1
                try:
                    raw = client.suggestions(q)
                except Exception as exc:  # noqa: BLE001 - the class is reported, never the message
                    res.done += 1
                    res.failed.append(error_class(exc))
                    streak += 1
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
    pacing.stopped = streak >= MAX_CONSECUTIVE_FAILURES
    return results, interrupted


def _cand_via(r: Result, c: dict, variants: bool) -> str:
    if not variants:
        return _cand(c)
    return _cand(c) + " via " + ", ".join(f"'{q}'" for q in r.found_by.get(c["mid"], []))


def _print_qualified(results: list[Result], stamp: str, out, derived: dict) -> dict:
    entries = tk.load().entries
    taken = {e["term"].casefold(): s for s, e in entries.items() if "term" in e}
    block: dict[str, dict] = {}
    skipped: list[str] = []
    for r in results:
        if r.verdict != "AMBIGUOUS" or not r.complete:
            continue
        term = qualified_term(r.symbol, r.name)
        if "topic" in entries.get(r.symbol, {}):
            skipped.append(f"{r.symbol} | no qualified term: already has a topic")
        elif term is None:
            why = ("label is only the ticker; the owner names it" if r.name == r.symbol
                   else "the name is not a safe ASCII term; the owner picks one")
            skipped.append(f"{r.symbol} | no qualified term: {why}")
        elif taken.get(term.casefold(), r.symbol) != r.symbol:
            skipped.append(f"{r.symbol} | no qualified term: '{term}' is already used")
        else:
            taken[term.casefold()] = r.symbol
            block[r.symbol] = {"term": term, "label": r.name if tk.is_valid_label(r.name) else r.symbol,
                               "note": f"qualified-term fallback {stamp}, not checker PASS"
                                       + (f", {DERIVED_MARK}" if r.symbol in derived else "")}
    print(f"\n{QUALIFIED_HEADER}\n{json.dumps(block, indent=2)}", file=out)
    for line in skipped:
        print(line, file=out)
    return block


def _print_scope(proposed: set[str], eligible: list[str], results: list[Result], terms: set[str], out) -> None:
    """Symbols the blocks propose that no narrative places, and where every eligible coin stands after the run.
    A coin this run did not check and with no keyword is 'not checked', never 'nothing'; one whose request failed is
    'request failed', never 'nothing'."""
    keywords = tk.load().entries
    placed = {c["symbol"] for n in narratives.load_narratives()["narratives"] for c in n["coins"]}
    outside = sorted(proposed - placed)
    print(f"\n{OUTSIDE_HEADER}\n{', '.join(outside) or '-'}", file=out)
    if outside:
        print("    the keyword loader takes them with a 'not a placed coin' warning when given the placed set;"
              " the Trends pull reads only the coins its caller passes", file=out)
    passed = {r.symbol for r in results if r.verdict == "PASS"}
    checked = {r.symbol for r in results if r.verdict != "NOT-RUN"}
    not_run = {r.symbol for r in results if r.verdict == "NOT-RUN"}
    req_failed = {r.symbol for r in results if r.failed}
    status = {}
    for s in eligible:
        e = keywords.get(s, {})
        status[s] = ("topic" if "topic" in e or s in passed else "qualified-term" if s in terms
                     else "term" if "term" in e else "request failed" if s in req_failed else "nothing" if s in checked else "not run" if s in not_run else "not checked")
    counts = {k: sum(v == k for v in status.values()) for k in COVERAGE_KINDS}
    print(f"discovery eligible: {len(eligible)} | " + " | ".join(f"{k}: {n}" for k, n in counts.items())
          + f" (this run checked {len(checked & set(eligible))} of them)", file=out)


def _pass_note(r: Result, stamp: str, derived: bool) -> str:
    rule = f" ({r.rule})" if r.rule in LEAD_RULES else ""
    return f"checker PASS{rule} {stamp}" + (f", {DERIVED_MARK}" if derived else "")


def run(mapping: dict, *, client, sleep=time.sleep, out=None, now=None, variants: bool = False,
        eligible: list[str] | None = None, derived: dict | None = None, pacing: Pacing | None = None,
        qualify: bool | None = None, rerun_extra: tuple[str, ...] = ()) -> list[Result]:
    """`qualify` (default: `variants`) prints the qualified term proposals; `rerun_extra` are the already-quoted
    options (--file, --only-unresolved) the printed run-again command repeats."""
    out = out or sys.stdout
    now = now or (lambda: datetime.now(timezone.utc))
    pacing = pacing or Pacing()
    qualify = variants if qualify is None else qualify
    planned = sum(len(queries_for(s, n)) if variants else 1 for s, n in mapping.items())
    print(_plan_line(len(mapping), planned, pacing), file=out, flush=True)
    names = {s: n for s, n in (derived or {}).items() if s in mapping}
    if names:
        print("names from the CoinGecko id (check them): " + ", ".join(f"{s}={n}" for s, n in names.items()), file=out)
    results, _ = _query_coins(mapping, client, sleep, variants, pacing)
    _demote_duplicate_topics(results)

    for r in results:
        if r.verdict == "NOT-RUN":
            print(f"{r.symbol} | {r.name} | - | - | NOT-RUN ({r.reason})", file=out)
            continue
        proposed = f"proposed {_cand_via(r, r.proposed, variants)}" if r.proposed else "-"
        tail = f" ({r.reason})" if r.reason else ""
        if r.verdict == "PASS" and r.rule in LEAD_RULES:
            tail += f" [rule: {r.rule}; LEAD: open the Trends link and confirm the coin]"
        if r.symbol in names:
            tail += f" ({DERIVED_MARK}, a guess)"
        print(f"{r.symbol} | {r.name} | {len(r.candidates)} candidates | {proposed} | {r.verdict}{tail}", file=out)
        if r.verdict == "PASS" and r.rule in LEAD_RULES:
            print(f"    verify {_cand(r.proposed)}: {VERIFY_URL.format(quote(r.proposed['mid'], safe=''))}", file=out)
        if r.verdict == "AMBIGUOUS":
            for c in r.candidates:
                print(f"    {_cand_via(r, c, variants)}", file=out)
    counts = {v: sum(r.verdict == v for r in results) for v in ("PASS", "AMBIGUOUS", "FAIL", "NOT-RUN")}
    print("\n" + " ".join(f"{v}: {n}" for v, n in counts.items()), file=out)
    print(f"requests sent: {pacing.sent}", file=out)
    if pacing.stopped:
        rerun = [r.symbol for r in results if r.verdict == "NOT-RUN" or r.failed]
        print(f"stopped: Google is refusing connections after {pacing.sent} requests sent; wait 30-60 minutes, then"
              f" re-run the NOT-RUN coins plus every coin whose request failed with: "
              + _rerun_args(rerun, rerun_extra, variants, pacing), file=out)

    stamp = now().strftime("%d-%m-%y")
    block = {r.symbol: {"topic": r.proposed["mid"], "label": r.name if tk.is_valid_label(r.name) else r.symbol,
                        "note": _pass_note(r, stamp, r.symbol in names)}
             for r in results if r.verdict == "PASS"}
    print(f"\n{LEAD_NOTE}" if variants or names else "", file=out)
    print(f"{PASTE_HEADER}\n{json.dumps(block, indent=2)}\n{DECISION_HEADER}", file=out)
    for r in results:
        if r.verdict in ("AMBIGUOUS", "FAIL"):
            print(f"{r.symbol} | {r.verdict} | {r.reason}", file=out)
            hint = _verify_hint(r) if r.verdict == "AMBIGUOUS" else None
            if hint:
                print(hint, file=out)
    terms = _print_qualified(results, stamp, out, names) if qualify else {}
    if eligible is not None:
        _print_scope(set(block) | set(terms), eligible, results, set(terms), out)
    return results


def unresolved_symbols(keyword_map, symbols) -> list[str]:
    """The symbols with no `topic` entry, including those with no entry at all."""
    return [s for s in symbols if "topic" not in keyword_map.entries.get(s, {})]


def name_from_id(cg_id, symbol: str) -> str:
    """'ether-fi' -> 'Ether Fi', 'pearl-2' -> 'Pearl'; the ticker when there is no usable id."""
    if not isinstance(cg_id, str):
        return symbol
    words = re.sub(r"-\d+$", "", cg_id.strip()).replace("-", " ").split()
    name = " ".join(w[:1].upper() + w[1:] for w in words)
    return name if name.isascii() and tk.is_valid_label(name) else symbol


def eligible_coins(rows: list[dict]) -> tuple[list[str], dict[str, str]]:
    """Discovery's eligible set (the same classes and tradeability rules) and a name per coin from its CoinGecko id."""
    eligible = discovery.eligibility(discovery.load_config(), rows).eligible
    ids = {str(r.get("symbol", "")).upper(): r.get("id") for r in rows}
    return eligible, {s: name_from_id(ids.get(s), s) for s in eligible}


def _default_mapping(eligible: list[str], names: dict[str, str]) -> tuple[dict, dict]:
    """(keyword-file labels then eligible coins without an entry, the names derived for those coins)."""
    mapping = {sym: e["label"] for sym, e in tk.load().entries.items()}
    derived = {s: names[s] for s in eligible if s not in mapping}
    return {**mapping, **derived}, derived


def _rerun_extra(args) -> tuple[str, ...]:
    extra = [f"--file {_ps_quote(str(args.file))}"] if args.file is not None else []
    return (*extra, *(["--only-unresolved"] if args.only_unresolved else []))


def main(argv: list[str] | None = None, *, trendreq_factory=make_trendreq, sleep=time.sleep, out=None,
         err=None, now=None, universe_rows: list[dict] | None = None) -> int:
    out, err = out or sys.stdout, err or sys.stderr
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--file", type=Path, default=None, help="symbol -> name JSON map")
    ap.add_argument("--symbols", default=None, help="comma-separated subset, e.g. LINK,AAVE")
    ap.add_argument("--only-unresolved", action="store_true",
                    help="only coins with no topic in trends_keywords.json (one request per coin)")
    ap.add_argument("--variants", action="store_true", help="also query '<name> crypto', '<name> coin', '<ticker> crypto'")
    ap.add_argument("--delay", type=float, default=INTERVAL_SECONDS, help=f"seconds between requests, >= {INTERVAL_SECONDS:g}")
    ap.add_argument("--pause-every", type=int, default=PAUSE_EVERY, help="pause after this many requests (0 = never)")
    ap.add_argument("--pause-s", type=float, default=PAUSE_SECONDS, help="length of that pause in seconds")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    if (not INTERVAL_SECONDS <= args.delay <= MAX_PACING_SECONDS or args.pause_every < 0
            or not 0 <= args.pause_s <= MAX_PACING_SECONDS):
        print(f"--delay must be >= {INTERVAL_SECONDS:g}, --pause-every >= 0 and --pause-s >= 0; --delay and --pause-s"
              f" must be finite and at most {MAX_PACING_SECONDS:g}", file=err)
        return 2
    try:
        if universe_rows is None:
            universe_rows, _ = load_universe_rows()
        eligible, names = eligible_coins(universe_rows) if universe_rows else ([], {})
    except Exception as exc:  # noqa: BLE001 - the class is reported, never the message
        print(f"cannot read the Discovery universe: {type(exc).__name__}", file=err)
        return 1
    derived: dict = {}
    try:
        if args.file is None:
            mapping, derived = _default_mapping(eligible, names)
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
        keep = set(unresolved_symbols(tk.load(), mapping))
        mapping = {s: n for s, n in mapping.items() if s in keep}
    client, code = start_client(trendreq_factory, "check_trends_keywords", err)
    if client is None:
        return code
    if not universe_rows:
        print("no universe snapshot: checking the keyword file only", file=err)
    pacing = Pacing(args.delay, args.pause_every, args.pause_s)
    results = run(mapping, client=client, sleep=sleep, out=out, now=now, variants=args.variants,
                  eligible=eligible if universe_rows else None, derived=derived, pacing=pacing,
                  qualify=args.variants or args.only_unresolved, rerun_extra=_rerun_extra(args))
    if any(INTERRUPTED_REASON in r.reason for r in results):
        return INTERRUPTED_EXIT
    return STOPPED_EXIT if pacing.stopped else 0


if __name__ == "__main__":
    sys.exit(main())
