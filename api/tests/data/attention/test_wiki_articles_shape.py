"""Shape guard for api/data/wiki_articles.json (T99): every new entry must keep the map safe to fetch."""
import json
import re
from pathlib import Path
from urllib.parse import quote

from api.data.attention import wikipedia

PATH = Path(wikipedia.__file__).parents[1] / "wiki_articles.json"
UNIVERSE = Path(wikipedia.__file__).parents[1] / "cache" / "attention" / "universe.json"

# Keys known at T99. A new key must be added here on purpose (or be in the latest universe snapshot).
KNOWN_KEYS = {
    "BTC", "ETH", "XRP", "BNB", "SOL", "DOGE", "TRX", "ADA", "HYPE", "LINK", "XLM", "BCH", "AVAX", "SHIB", "LTC",
    "TON", "DOT", "XMR", "UNI", "AAVE", "NEAR", "ETC", "ICP", "ATOM", "ALGO", "FIL", "APT", "ARB", "OP", "SUI",
    "PEPE", "ONDO", "TAO", "RENDER", "INJ", "HBAR", "VET", "XTZ", "EOS", "MKR", "CRV", "LDO", "SAND", "MANA",
    "AXS", "THETA", "FLOW", "QNT", "GRT", "LEO", "CRO", "XDC", "KAS", "BGB", "OKB", "MNT", "POL", "FET", "IMX",
    "SEI", "TIA", "STX", "RUNE", "KAVA", "EGLD", "NEO", "IOTA", "DASH", "ZEC", "XEM", "WLD", "JUP", "PYTH",
    "BONK", "WIF", "FLOKI", "ENA", "PENDLE", "GALA", "CHZ", "ENS", "SNX", "COMP", "1INCH", "BAT", "ZIL", "KSM",
    "CAKE", "RAY", "JTO", "ZRO", "STRK", "MORPHO", "TRUMP", "PENGU", "FARTCOIN", "VIRTUAL", "AERO", "S", "BERA",
    "PAXG", "XAUT", "USDT",
}
# Single words / names that are a disambiguation page, person, place or generic word on English Wikipedia.
AMBIGUOUS = {"link", "near", "sui", "gas", "sand", "op", "grt", "ens", "flow", "sei", "s", "m", "u", "pi", "stable",
             "night", "render", "ondo", "aster", "pump", "jupiter", "raydium", "ray", "sky", "lit", "cc", "rain"}


def _map() -> dict:
    return json.loads(PATH.read_text())


def _titles() -> dict[str, str]:
    return {k: v for k, v in _map().items() if v is not None}


def test_symbols_upper_unique_and_known():
    raw = PATH.read_text()
    keys = [k for k, _ in json.loads(raw, object_pairs_hook=lambda p: p)]
    assert len(keys) == len(set(keys))
    assert all(re.fullmatch(r"[A-Z0-9]+", k) for k in keys)
    universe = set()
    try:
        snap = json.loads(UNIVERSE.read_text())["snapshots"][-1]
        universe = {str(r["symbol"]).upper() for r in snap["coins"]}
    except (OSError, ValueError, KeyError, IndexError):
        pass
    assert set(keys) <= KNOWN_KEYS | universe


def test_titles_are_plain_article_names():
    for sym, t in _titles().items():
        assert isinstance(t, str) and t == t.strip() and t, sym
        assert not re.search(r"https?:|wikipedia\.org|/wiki/|[/?#%\\]", t), (sym, t)
        assert not t.startswith("_") and not t.endswith("_") and "__" not in t, (sym, t)
        assert " " not in t, (sym, t)  # file convention: underscores, as the fetcher normalises either


def test_no_title_appears_twice():
    norm = [t.replace(" ", "_").casefold() for t in _titles().values()]
    assert len(norm) == len(set(norm))


def test_no_ambiguous_bare_titles():
    bad = {s: t for s, t in _titles().items() if t.casefold() in AMBIGUOUS}
    assert bad == {}


def test_fetcher_url_is_one_path_segment_per_title():
    for sym, t in _titles().items():
        seg = quote(t.replace(" ", "_"), safe="")
        assert "/" not in seg and seg, sym
        url = wikipedia.BASE_URL.format(article=seg, start="2026010100", end="2026010200")
        assert url.count("/daily/") == 1, sym
