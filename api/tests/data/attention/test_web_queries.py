"""W8b AC8/AC15/AC20: query file, collector config block and validator, coin set. Pure; no network."""
from __future__ import annotations

import copy
import json

import pytest

from api.data.attention import web_queries as wq

LOCKED = {
    "x_query_delay_min_s": 180, "x_query_delay_max_s": 360, "x_daily_post_budget": 800, "x_sample_n": 40,
    "x_sample_min": 20, "x_page_cap": 3, "reddit_request_delay_min_s": 60, "reddit_request_delay_max_s": 120,
    "reddit_daily_request_budget": 250, "reddit_sample_min": 10,
}


@pytest.fixture
def doc():
    return json.loads(wq.QUERIES_PATH.read_text(encoding="utf-8"))


def test_committed_file_loads_with_locked_defaults():
    q = wq.load(placed_symbols=wq.placed_symbols())
    for key, value in LOCKED.items():
        assert getattr(q.config, key) == value, key
    assert q.config.x_page_gap_min_s == 5 and q.config.x_page_gap_max_s == 15
    assert q.config.x_backfill_days == 14
    assert {k: wq.DEFAULTS[k] for k in LOCKED} == LOCKED
    assert set(wq.DEFAULTS) == set(q.config.as_dict())

def test_transport_identity_defaults_are_off(doc):
    config = wq.validate(doc).config
    assert config.x_connection_style == "plain"
    assert config.x_identity_enabled is False
    assert config.x_account_identities == {}


def test_plain_identity_requires_compatible_fallback_target(doc):
    block = doc["collector"]
    block["x_accounts"] = ["alpha"]
    block["x_identity_enabled"] = True
    block["x_account_identities"] = {"alpha": {
        "accept_language": "en-US,en;q=0.9", "region": "US", "timezone": "America/New_York",
        "user_agent": "Mozilla/5.0 Chrome/131.0.0.0 Safari/537.36",
        "impersonation_target": "chrome131",
    }}
    assert wq.validate(doc).config.x_account_identities["alpha"]["impersonation_target"] == "chrome131"
    del block["x_account_identities"]["alpha"]["impersonation_target"]
    with pytest.raises(wq.QueriesError):
        wq.validate(doc)
    block["x_account_identities"]["alpha"]["impersonation_target"] = "firefox133"
    with pytest.raises(wq.QueriesError):
        wq.validate(doc)


@pytest.mark.parametrize("style", ["plain", "curl"])
def test_identity_rejects_unknown_duplicate_and_missing_labels(doc, style):
    block = doc["collector"]
    block.update(x_accounts=["alpha", "beta"], x_identity_enabled=True, x_connection_style=style)
    identity = {"accept_language": "en-US,en;q=0.9", "region": "US", "timezone": "America/New_York",
                "user_agent": "Mozilla/5.0 Chrome/131.0.0.0 Safari/537.36",
                "impersonation_target": "chrome131"}
    block["x_account_identities"] = {"alpha": identity.copy(), "beta": identity.copy()}
    with pytest.raises(wq.QueriesError):
        wq.validate(doc)
    block["x_account_identities"] = {"alpha": identity.copy()}
    with pytest.raises(wq.QueriesError):
        wq.validate(doc)
    block["x_account_identities"] = {"alpha": identity.copy(), "unknown": identity.copy()}
    with pytest.raises(wq.QueriesError):
        wq.validate(doc)


def test_plain_identities_cannot_share_fallback_target(doc):
    block = doc["collector"]
    block.update(x_accounts=["alpha", "beta"], x_identity_enabled=True)
    one = {"accept_language": "en-US", "region": "US", "timezone": "America/New_York",
           "user_agent": "Mozilla/5.0 Chrome/131.0.0.0 Safari/537.36", "impersonation_target": "chrome131"}
    two = {**one, "user_agent": "Mozilla/5.0 Chrome/131.0.1.0 Safari/537.36"}
    block["x_account_identities"] = {"alpha": one, "beta": two}
    with pytest.raises(wq.QueriesError):
        wq.validate(doc)


@pytest.mark.parametrize("key,value", [
    ("x_connection_style", "browser"), ("x_identity_enabled", 1),
    ("x_account_identities", []),
])
def test_identity_settings_reject_invalid_types(doc, key, value):
    doc["collector"][key] = value
    with pytest.raises(wq.QueriesError):
        wq.validate(doc)


@pytest.mark.parametrize("key,value", [
    ("accept_language", ""), ("accept_language", "en\r\nX-Injected: yes"),
    ("region", ""), ("timezone", "not/a/timezone"), ("user_agent", ""),
    ("impersonation_target", "chrome"), ("impersonation_target", "chrome999999"),
    ("user_agent", "@chrome"), ("accept_language", "not a language"),
])
def test_enabled_identity_rejects_invalid_fields(doc, key, value):
    block = doc["collector"]
    block.update(x_accounts=["alpha"], x_identity_enabled=True)
    identity = {"accept_language": "en-US,en;q=0.9", "region": "US", "timezone": "America/New_York",
                "user_agent": "Mozilla/5.0 Chrome/131.0.0.0 Safari/537.36",
                "impersonation_target": "chrome131"}
    identity[key] = value
    block["x_account_identities"] = {"alpha": identity}
    with pytest.raises(wq.QueriesError):
        wq.validate(doc)


def _coherent_identity(doc, style, **changes):
    identity = {"accept_language": "en-US,en;q=0.9", "region": "US", "timezone": "America/New_York",
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/131.0.0.0 Safari/537.36",
                "impersonation_target": "chrome131"}
    identity.update(changes)
    doc["collector"].update(x_accounts=["alpha"], x_identity_enabled=True, x_connection_style=style,
                            x_account_identities={"alpha": identity})
    return identity


@pytest.mark.parametrize("style", ["plain", "curl"])
@pytest.mark.parametrize("changes", [
    {"region": "FR"},  # Neither New York nor the primary language's region agrees.
    {"timezone": "Europe/Paris"},
    {"accept_language": "en-GB,en;q=0.9"},
    {"user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0 Safari/537.36"},
])
def test_identity_coherence_rejects_explicit_contradictions(doc, style, changes):
    _coherent_identity(doc, style, **changes)
    with pytest.raises(wq.QueriesError, match="coherence"):
        wq.validate(doc)


@pytest.mark.parametrize("style", ["plain", "curl"])
@pytest.mark.parametrize("changes", [
    {},  # macOS can be used in New York; OS never determines geography.
    {"timezone": "America/Phoenix"},  # Same country, no seasonal offset change.
    {"timezone": "Pacific/Honolulu"},  # Same country, very different offset.
    {"region": "DE", "timezone": "Europe/Zurich", "accept_language": "de-DE,de;q=0.9"},
    {"region": "CH", "timezone": "Europe/Zurich", "accept_language": "fr-CH,fr;q=0.9"},
    {"accept_language": "fr,en-GB;q=0.5"},  # No regional claim in primary language.
    {"accept_language": "en-US,en-GB;q=0.5"},  # Secondary preference is not residence.
    {"timezone": "UTC"},  # Region-neutral zone: no country claim to contradict.
    {"timezone": "US/Eastern"},  # Valid alias not in country tables: unknown, not false.
    {"user_agent": "Mozilla/5.0 Chrome/131.0.0.0 Safari/537.36"},  # Platform-neutral B1 UA.
])
def test_identity_coherence_accepts_bounded_claims(doc, style, changes):
    identity = _coherent_identity(doc, style, **changes)
    assert wq.validate(doc).config.x_account_identities["alpha"] == identity


@pytest.mark.parametrize("style", ["plain", "curl"])
def test_disabled_identity_skips_coherence(doc, style):
    _coherent_identity(doc, style, region="FR", timezone="America/New_York",
                       user_agent="Mozilla/5.0 (Windows NT 10.0) Chrome/131.0.0.0 Safari/537.36")
    doc["collector"]["x_identity_enabled"] = False
    assert wq.validate(doc).config.x_identity_enabled is False


def test_identity_coherence_is_not_an_offset_or_dst_test(doc):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    zone = ZoneInfo("America/New_York")
    assert datetime(2026, 1, 15, tzinfo=zone).utcoffset() != datetime(2026, 7, 15, tzinfo=zone).utcoffset()
    _coherent_identity(doc, "plain")
    assert wq.validate(doc).config.x_identity_enabled


@pytest.mark.parametrize("target,ua", [
    ("edge101", "Mozilla/5.0 (Macintosh) Chrome/101.0 Edg/101.0"),
    ("safari170", "Mozilla/5.0 (Windows NT 10.0) Version/17.0 Safari/605.1"),
    ("firefox133", "Mozilla/5.0 (Windows NT 10.0) Firefox/133.0"),
    ("chrome131_android", "Mozilla/5.0 (Macintosh) Chrome/131.0"),
    ("safari172_ios", "Mozilla/5.0 (Macintosh) Version/17.2 Safari/605.1"),
])
def test_identity_coherence_platform_evidence_is_target_specific(doc, target, ua):
    _coherent_identity(doc, "plain", impersonation_target=target, user_agent=ua)
    with pytest.raises(wq.QueriesError, match="coherence target/UA platform"):
        wq.validate(doc)


def test_identity_coherence_requires_country_tables_only_when_enabled(doc, monkeypatch):
    monkeypatch.setattr(wq, "TZPATH", ())
    def absent(_package):
        raise ModuleNotFoundError
    monkeypatch.setattr(wq, "files", absent)
    _coherent_identity(doc, "plain")
    with pytest.raises(wq.QueriesError, match="tables unavailable"):
        wq.validate(doc)
    doc["collector"]["x_identity_enabled"] = False
    assert not wq.validate(doc).config.x_identity_enabled


def test_identity_coherence_loads_system_country_tables(tmp_path, monkeypatch):
    (tmp_path / "zone.tab").write_text("US\t+0000+00000\tAmerica/New_York\n", encoding="utf-8")
    (tmp_path / "zone1970.tab").write_text("# shared\nCH,DE,LI\t+0000+00000\tEurope/Zurich\n", encoding="utf-8")
    monkeypatch.setattr(wq, "TZPATH", (str(tmp_path),))
    assert wq._timezone_countries() == {"America/New_York": {"US"}, "Europe/Zurich": {"CH", "DE", "LI"}}


def test_reddit_baseline_250_and_separate_degraded_150_budget():
    assert wq.DEFAULTS["reddit_daily_request_budget"] == 250
    assert wq.REDDIT_DEFAULTS["reddit_degraded_request_budget"] == wq.REDDIT_DEGRADED_BUDGET == 150
    c = wq.load().config
    assert c.reddit_daily_request_budget == 250 and c.reddit_degraded_request_budget == 150
    absent = {k: v for k, v in c.as_dict().items() if k != "reddit_degraded_request_budget"}
    assert wq.validate_config(absent).reddit_degraded_request_budget == 150  # the default applies when absent


def test_pace_config_rejects_min_above_max_and_nonpositive(doc):
    for key, bad in (("x_query_delay_min_s", 400), ("reddit_request_delay_min_s", 121), ("x_page_gap_min_s", 16)):
        d = copy.deepcopy(doc)
        d["collector"][key] = bad
        with pytest.raises(wq.QueriesError, match="must be <="):
            wq.validate(d)
    for key in LOCKED:
        for bad in (0, -1, "180", True, None):
            d = copy.deepcopy(doc)
            d["collector"][key] = bad
            with pytest.raises(wq.QueriesError):
                wq.validate(d)


def test_sample_min_above_sample_n_rejected(doc):
    doc["collector"]["x_sample_min"] = 41
    with pytest.raises(wq.QueriesError, match="x_sample_min"):
        wq.validate(doc)


def test_unknown_and_missing_config_keys_rejected(doc):
    d = copy.deepcopy(doc)
    d["collector"]["x_turbo"] = 1
    with pytest.raises(wq.QueriesError, match="unknown"):
        wq.validate(d)
    d = copy.deepcopy(doc)
    del d["collector"]["x_daily_post_budget"]
    with pytest.raises(wq.QueriesError, match="x_daily_post_budget"):
        wq.validate(d)


def test_config_change_is_read(doc, tmp_path):
    doc["collector"]["x_query_delay_min_s"] = 600
    doc["collector"]["x_query_delay_max_s"] = 900
    p = tmp_path / "q.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    q = wq.load(p)
    assert (q.config.x_query_delay_min_s, q.config.x_query_delay_max_s) == (600, 900)


def test_coin_set_is_narrative_placed_symbols_minus_ambiguous():
    placed = wq.placed_symbols()
    assert len(placed) == len(set(placed)) and "SOL" in placed
    q = wq.load_merged(placed_symbols=placed)
    assert set(placed) <= set(q.coins)
    for source in wq.SOURCES:
        coins = wq.coin_set(q, source, placed)
        assert set(coins) == set(placed) - q.ambiguous[source]
        assert coins == sorted(coins)
    assert set(wq.coin_set(q, "xsearch_web", ["SOL", "NOPE"])) == {"SOL", "NOPE"} - q.ambiguous["xsearch_web"]


def test_ambiguous_coin_is_missing(doc):
    doc["ambiguous"]["xsearch_web"] = ["SOL"]
    q = wq.validate(doc)
    assert wq.x_query(q, "SOL") is None
    assert "SOL" not in wq.coin_set(q, "xsearch_web", ["SOL", "ETH"])
    assert wq.x_query(q, "ETH") == '("$ETH" OR "Ethereum") lang:en -filter:replies -filter:retweets'


def test_every_placed_coin_has_a_name_entry():
    with pytest.raises(wq.QueriesError, match="no entry"):
        wq.validate({**json.loads(wq.QUERIES_PATH.read_text(encoding="utf-8")), "coins": {}},
                    placed_symbols=["SOL"])


def test_bad_terms_and_subreddits_rejected(doc):
    d = copy.deepcopy(doc)
    d["coins"]["SOL"]["name"] = 'Sol" OR "x'
    with pytest.raises(wq.QueriesError):
        wq.validate(d)
    d = copy.deepcopy(doc)
    d["subreddits"] = ["ok", "bad/path"]
    with pytest.raises(wq.QueriesError):
        wq.validate(d)
    d = copy.deepcopy(doc)
    d["ambiguous"]["unknown_source"] = []
    with pytest.raises(wq.QueriesError):
        wq.validate(d)


def test_subreddit_set_matches_spec_proposal():
    q = wq.load()
    assert q.subreddits[:3] == ("CryptoCurrency", "CryptoMarkets", "altcoin") and len(q.subreddits) == 12


def test_honest_user_agent_is_plain():
    assert wq.HONEST_USER_AGENT == "attention-probe/0.1"


# --- W8c2 stream keys (owner deltas 29-10-26: 12-name set by reference, comments 7200 s, posts 21600 s, paging on) ---

def test_stream_keys_committed_with_owner_defaults():
    c = wq.load().config
    assert c.reddit_stream_subreddits is None  # None: the stream uses the top-level `subreddits` list
    assert c.reddit_comments_poll_interval_s == 7200 and c.reddit_posts_poll_interval_s == 21600
    assert c.reddit_stream_polls_per_day_cap == 12 and c.reddit_stream_min_coverage == 0.8
    assert c.reddit_comments_paging is True
    assert c.reddit_impl_order == NEW_ORDER  # finish plan C1: committed order, live methods first (S-RDisc)


def test_stream_keys_default_when_absent(doc):
    for key in wq.REDDIT_STREAM_DEFAULTS:
        doc["collector"].pop(key, None)
    c = wq.validate(doc).config
    for key, value in wq.REDDIT_STREAM_DEFAULTS.items():
        assert getattr(c, key) == (tuple(value) if isinstance(value, list) else value), key


def test_stream_subreddit_set_resolves_to_top_level_list(doc):
    q = wq.validate(doc)
    assert wq.stream_subreddits(q) == q.subreddits and len(q.subreddits) == 12
    doc["collector"]["reddit_stream_subreddits"] = ["CryptoCurrency", "altcoin"]
    assert wq.stream_subreddits(wq.validate(doc)) == ("CryptoCurrency", "altcoin")


@pytest.mark.parametrize("key,bad", [
    ("reddit_stream_subreddits", []), ("reddit_stream_subreddits", ["bad name!"]),
    ("reddit_stream_subreddits", ["altcoin", "Altcoin"]), ("reddit_stream_subreddits", "subreddits"),
    ("reddit_comments_poll_interval_s", 0), ("reddit_comments_poll_interval_s", True),
    ("reddit_posts_poll_interval_s", -1), ("reddit_stream_polls_per_day_cap", 0),
    ("reddit_stream_min_coverage", 0), ("reddit_stream_min_coverage", 1.5), ("reddit_stream_min_coverage", True),
    ("reddit_comments_paging", 1), ("reddit_impl_order", []), ("reddit_impl_order", ["reddit_web", "reddit_web"]),
    ("reddit_impl_order", ["reddit_api"]), ("reddit_impl_order", "reddit_stream"),
])
def test_stream_keys_rejected_when_invalid(doc, key, bad):
    doc["collector"][key] = bad
    with pytest.raises(wq.QueriesError, match=key):
        wq.validate(doc)


# --- W8c2 fix round 3: poll-file retention (E2) and the per-poll page cap (E3) ---

@pytest.mark.parametrize("key,default", [("reddit_stream_poll_retention_days", 30),
                                         ("reddit_stream_max_pages_per_poll", 10)])
def test_stream_retention_and_page_cap_keys(doc, key, default):
    assert getattr(wq.load().config, key) == default and wq.REDDIT_STREAM_DEFAULTS[key] == default
    doc["collector"][key] = 7
    assert getattr(wq.validate(doc).config, key) == 7


@pytest.mark.parametrize("key", ["reddit_stream_poll_retention_days", "reddit_stream_max_pages_per_poll"])
@pytest.mark.parametrize("bad", [0, -1, True, False, 1.5, "10", None])
def test_stream_retention_and_page_cap_rejected_when_invalid(doc, key, bad):
    doc["collector"][key] = bad
    with pytest.raises(wq.QueriesError, match=key):
        wq.validate(doc)


# --- W8c2w: the stream's share of the Reddit request budget (owner Q1 option b, default 0.45) ---

def test_budget_share_default_is_0_45():
    assert wq.REDDIT_STREAM_DEFAULTS["reddit_stream_budget_share"] == 0.45
    assert wq.load().config.reddit_stream_budget_share == 0.45


@pytest.mark.parametrize("bad", [0, 0.0, -0.1, -1, True, False, 1.0001, 2, "0.45", None])
def test_budget_share_rejects_zero_negative_bool_over_one_text_and_none(doc, bad):
    doc["collector"]["reddit_stream_budget_share"] = bad
    with pytest.raises(wq.QueriesError, match="reddit_stream_budget_share"):
        wq.validate(doc)


@pytest.mark.parametrize("good", [1, 1.0, 0.5, 0.45, 0.01])
def test_budget_share_accepts_one_and_fractions(doc, good):
    doc["collector"]["reddit_stream_budget_share"] = good
    assert wq.validate(doc).config.reddit_stream_budget_share == good


def test_budget_share_absent_key_uses_default(doc):
    doc["collector"].pop("reddit_stream_budget_share", None)
    assert wq.validate(doc).config.reddit_stream_budget_share == 0.45


# --- collector identity pool, Part A: optional per-account cap and rest days (defaults live in code) ---

def test_account_cap_and_rest_optional_off_by_default(doc):
    assert "x_account_daily_cap" not in wq.X_DEFAULTS and "x_account_rest_days" not in wq.X_DEFAULTS
    c = wq.validate(doc).config
    assert c.x_account_daily_cap is None and c.x_account_rest_days == 0
    doc["collector"]["x_account_daily_cap"] = 300
    doc["collector"]["x_account_rest_days"] = 3
    c = wq.validate(doc).config
    assert (c.x_account_daily_cap, c.x_account_rest_days) == (300, 3)


@pytest.mark.parametrize("key,bad", [("x_account_daily_cap", 0), ("x_account_daily_cap", True),
                                     ("x_account_daily_cap", 1.5), ("x_account_daily_cap", "300"),
                                     ("x_account_rest_days", -1), ("x_account_rest_days", None),
                                     ("x_account_rest_days", False)])
def test_account_cap_and_rest_rejected_when_invalid(doc, key, bad):
    doc["collector"][key] = bad
    with pytest.raises(wq.QueriesError, match=key):
        wq.validate(doc)


# --- S-Config (finish plan 06-11-26, Public Contracts -> configuration; SPEC notes N1-N5 of 07-11-26) ---
FINISH_DEFAULTS = {
    "x_queryid_mode": "off", "x_queryid_static_budget_per_day": 6,
    "x_cookie_harvest_enabled": False, "browser_path": None, "browser_profiles_dir": None,
    "x_account_profiles": {}, "x_surface_path": None, "x_cookie_refresh_age_days": None,
    "x_harvest_timeout_s": 120, "browser_memory_floor_mb": 1536, "browser_rss_ceiling_mb": 1200,
    "x_quiet_hours_enabled": False, "x_mixed_traffic_enabled": False, "x_variation_enabled": False,
    "x_adaptive_cooldown_enabled": False, "x_warmup_enabled": False, "x_account_quiet_hours": {},
    "x_mixed_targets": (), "facts_retention_days": 180,
    "reddit_live_methods": (), "reddit_surface_path": None, "reddit_live_probe_max_age_days": 7,
    "reddit_live_polls_per_day": 6, "reddit_live_threads_per_poll": 30, "reddit_live_min_thread_coverage": 0.8,
    "reddit_live_canary_min_items": 15, "reddit_zero_min_history_days": 7,
    "reddit_browser_accounts": (), "reddit_browser_daily_navigation_cap": 400,
    "reddit_browser_account_daily_cap": 200, "reddit_browser_account_rest_days": 7,
    "reddit_browser_daily_minutes": 90, "reddit_session_check_enabled": False,
    "reddit_live_gql_daily_request_cap": 600,
}
NEW_ORDER = ("reddit_live_browser", "reddit_live_gql", "reddit_web", "reddit_stream")
# Rollback contract G, checkpoint "B2" (state before Stage 1): the exact key set the older validator accepted.
B2_KEYS = frozenset({
    "x_query_delay_min_s", "x_query_delay_max_s", "x_page_gap_min_s", "x_page_gap_max_s", "x_daily_post_budget",
    "x_sample_n", "x_sample_min", "x_page_cap", "x_backfill_days", "reddit_request_delay_min_s",
    "reddit_request_delay_max_s", "reddit_daily_request_budget", "reddit_sample_min", "x_lang", "x_window_syntax",
    "x_min_account_age_days", "x_min_followers", "x_max_cashtags", "x_raw_retention_days", "x_canary_query",
    "x_canary_min_results", "x_unit_max_restarts", "x_canary_tolerance", "x_canary_min_overlap",
    "x_parse_drop_threshold", "x_allow_curl_backend", "x_accounts_db_path", "x_pinned_commit", "x_pinned_version",
    "x_accounts", "x_pool_max", "reddit_degraded_request_budget", "reddit_author_cap", "reddit_min_mentions",
    "reddit_search_time_filter", "reddit_stream_subreddits", "reddit_comments_poll_interval_s",
    "reddit_posts_poll_interval_s", "reddit_stream_polls_per_day_cap", "reddit_stream_min_coverage",
    "reddit_comments_paging", "reddit_impl_order", "reddit_stream_poll_retention_days",
    "reddit_stream_max_pages_per_poll", "reddit_stream_budget_share", "x_account_daily_cap", "x_account_rest_days",
    "x_connection_style", "x_identity_enabled", "x_account_identities", "x_proxy_required", "x_proxy_list_path",
    "x_proxy_assignments_path", "x_proxy_policy_path", "x_proxy_admission_max_age_seconds",
    "x_proxy_health_interval_seconds", "x_proxy_quarantine_seconds",
})
ABS = "C:\\private\\collector" if __import__("os").name == "nt" else "/private/collector"


def _abs(*parts):
    import os
    return os.path.join(ABS, *parts)


def _browser_ready(block):
    block.update(browser_path=_abs("edge.exe"), browser_profiles_dir=_abs("profiles"))


def test_finish_keys_declared_optional_with_contract_defaults(doc):
    assert {k: wq.FINISH_OPTIONAL_DEFAULTS[k] for k in FINISH_DEFAULTS} == {
        k: (list(v) if isinstance(v, tuple) else v) for k, v in FINISH_DEFAULTS.items()}
    assert set(wq.FINISH_OPTIONAL_DEFAULTS) == set(FINISH_DEFAULTS)
    assert not set(FINISH_DEFAULTS) & set(wq.X_DEFAULTS)
    assert set(wq.DEFAULTS) == B2_KEYS | set(FINISH_DEFAULTS) | set(wq.ROUTE_SOURCE_OPTIONAL_DEFAULTS)
    for key in FINISH_DEFAULTS:
        doc["collector"].pop(key, None)
    c = wq.validate(doc).config
    for key, value in FINISH_DEFAULTS.items():
        assert getattr(c, key) == value, key


def test_reddit_method_enum_and_new_impl_order_default(doc):
    assert set(wq.REDDIT_METHODS) == set(NEW_ORDER)
    assert tuple(wq.REDDIT_STREAM_DEFAULTS["reddit_impl_order"]) == NEW_ORDER
    assert wq.REDDIT_LIVE_METHODS == ("browser", "gql_anon")
    del doc["collector"]["reddit_impl_order"]
    assert wq.validate(doc).config.reddit_impl_order == NEW_ORDER
    doc["collector"]["reddit_impl_order"] = ["reddit_live_gql", "reddit_web"]
    assert wq.validate(doc).config.reddit_impl_order == ("reddit_live_gql", "reddit_web")


def test_committed_file_carries_the_live_first_order():
    c = wq.load(placed_symbols=wq.placed_symbols()).config
    assert c.reddit_impl_order == NEW_ORDER   # S-RDisc (contract C1) changed the committed key to the new order
    assert all(getattr(c, k) == v for k, v in FINISH_DEFAULTS.items())


def test_all_off_baseline_equals_b2_optional_behaviour(doc):
    """AC12: an all-defaults config leaves every new switch off and every B2 value unchanged."""
    c = wq.validate(doc).config
    b2 = {k: v for k, v in c.as_dict().items() if k in B2_KEYS}
    stripped = copy.deepcopy(doc)
    for key in FINISH_DEFAULTS:
        stripped["collector"].pop(key, None)
    assert {k: v for k, v in wq.validate(stripped).config.as_dict().items() if k in B2_KEYS} == b2
    assert not any(getattr(c, k) for k in FINISH_DEFAULTS if k.endswith("_enabled"))
    assert c.x_queryid_mode == "off" and c.reddit_live_methods == () and c.reddit_browser_accounts == ()


def test_rollback_to_b2_checkpoint_older_validator_rejects_each_new_key(doc):
    """Contract G stage-1 row: every key is declared; stripping them yields a document the B2 key set accepts."""
    def b2_validator(block):  # fixture copy of the older unknown-key rule
        unknown = set(block) - B2_KEYS
        if unknown:
            raise wq.QueriesError("collector: unknown key(s)")
    for key, value in FINISH_DEFAULTS.items():
        block = {**doc["collector"], key: list(value) if isinstance(value, tuple) else value}
        wq.validate_config(block)
        with pytest.raises(wq.QueriesError):
            b2_validator(block)
    b2_validator({k: v for k, v in doc["collector"].items() if k not in FINISH_DEFAULTS})


def _full_finish_block(doc):
    block = doc["collector"]
    block.update(x_accounts=["xa", "xb"], x_cookie_harvest_enabled=True, x_queryid_mode="sentinel",
                 x_queryid_static_budget_per_day=12, x_account_profiles={"xa": "prof_xa", "xb": "prof_xb"},
                 x_surface_path=_abs("x_surface.json"), x_cookie_refresh_age_days=3, x_harvest_timeout_s=30,
                 browser_memory_floor_mb=512, browser_rss_ceiling_mb=400, x_quiet_hours_enabled=True,
                 x_mixed_traffic_enabled=True, x_variation_enabled=True, x_adaptive_cooldown_enabled=True,
                 x_warmup_enabled=True,
                 x_account_quiet_hours={"xa": {"timezone": "Europe/Amsterdam", "start": "23:00", "end": "06:30"}},
                 x_mixed_targets=["jack", "20"], facts_retention_days=30,
                 reddit_live_methods=["gql_anon", "browser"], reddit_surface_path=_abs("reddit_surface.json"),
                 reddit_live_probe_max_age_days=3, reddit_live_polls_per_day=24, reddit_live_threads_per_poll=100,
                 reddit_live_min_thread_coverage=1, reddit_live_canary_min_items=1, reddit_zero_min_history_days=1,
                 reddit_browser_accounts=[{"label": "ra", "profile": "prof_ra"}],
                 reddit_browser_daily_navigation_cap=10, reddit_browser_account_daily_cap=5,
                 reddit_browser_account_rest_days=0, reddit_browser_daily_minutes=240,
                 reddit_session_check_enabled=True, reddit_live_gql_daily_request_cap=50)
    _browser_ready(block)
    return block


def test_every_finish_key_accepts_valid_values_and_round_trips(doc):
    _full_finish_block(doc)
    c = wq.validate(doc).config
    assert c.reddit_live_methods == ("gql_anon", "browser") and c.x_mixed_targets == ("jack", "20")
    assert c.reddit_browser_accounts == ({"label": "ra", "profile": "prof_ra"},)
    again = wq.validate_config(c.as_dict())
    assert again == c and again.as_dict() == c.as_dict()
    json.dumps(c.as_dict())  # nonsecret, serialisable


@pytest.mark.parametrize("key,bad", [
    ("x_queryid_mode", "on"), ("x_queryid_mode", None), ("x_queryid_static_budget_per_day", 0),
    ("x_queryid_static_budget_per_day", 13), ("x_queryid_static_budget_per_day", True),
    ("x_cookie_harvest_enabled", 1), ("browser_path", "relative\\edge.exe"), ("browser_path", ""),
    ("browser_profiles_dir", 5), ("x_account_profiles", []), ("x_account_profiles", {"xa": "Bad-Name"}),
    ("x_account_profiles", {"nobody": "p"}), ("x_surface_path", "x_surface.json"),
    ("x_cookie_refresh_age_days", 0), ("x_cookie_refresh_age_days", 1.5), ("x_harvest_timeout_s", 29),
    ("x_harvest_timeout_s", 301), ("browser_memory_floor_mb", 511), ("browser_rss_ceiling_mb", 399),
    ("x_quiet_hours_enabled", "false"), ("x_mixed_traffic_enabled", 0), ("x_variation_enabled", None),
    ("x_adaptive_cooldown_enabled", 1), ("x_warmup_enabled", "yes"),
    ("x_account_quiet_hours", {"nobody": {"timezone": "UTC", "start": "01:00", "end": "02:00"}}),
    ("x_account_quiet_hours", {"xa": {"timezone": "Not/AZone", "start": "01:00", "end": "02:00"}}),
    ("x_account_quiet_hours", {"xa": {"timezone": "UTC", "start": "01:00", "end": "01:00"}}),
    ("x_account_quiet_hours", {"xa": {"timezone": "UTC", "start": "24:00", "end": "01:00"}}),
    ("x_account_quiet_hours", {"xa": {"timezone": "UTC", "start": "01:00", "end": "02:00", "x": 1}}),
    ("x_account_quiet_hours", []),
    ("x_mixed_targets", "jack"), ("x_mixed_targets", ["jack", "jack"]), ("x_mixed_targets", ["bad name"]),
    ("x_mixed_targets", [1]), ("facts_retention_days", 29), ("facts_retention_days", True),
    ("reddit_live_methods", ["browser", "browser"]), ("reddit_live_methods", ["web"]),
    ("reddit_live_methods", "browser"), ("reddit_surface_path", "rel.json"),
    ("reddit_live_probe_max_age_days", 0), ("reddit_live_polls_per_day", 1), ("reddit_live_polls_per_day", 25),
    ("reddit_live_threads_per_poll", 0), ("reddit_live_threads_per_poll", 101),
    ("reddit_live_min_thread_coverage", 0), ("reddit_live_min_thread_coverage", 1.1),
    ("reddit_live_canary_min_items", 0), ("reddit_zero_min_history_days", 0),
    ("reddit_browser_accounts", [{"label": "ra"}]), ("reddit_browser_accounts", [{"label": "RA", "profile": "p"}]),
    ("reddit_browser_accounts", [{"label": f"r{i}", "profile": f"p{i}"} for i in range(4)]),
    ("reddit_browser_accounts", [{"label": "ra", "profile": "p1"}, {"label": "ra", "profile": "p2"}]),
    ("reddit_browser_accounts", [{"label": "xa", "profile": "p1"}]),
    ("reddit_browser_daily_navigation_cap", 0), ("reddit_browser_account_daily_cap", 0),
    ("reddit_browser_account_rest_days", -1), ("reddit_browser_daily_minutes", 9),
    ("reddit_browser_daily_minutes", 241), ("reddit_session_check_enabled", 1),
    ("reddit_live_gql_daily_request_cap", 49), ("reddit_impl_order", ["reddit_live_api"]),
])
def test_every_finish_key_rejects_invalid_values(doc, key, bad):
    _full_finish_block(doc)
    wq.validate(doc)
    doc["collector"][key] = bad
    with pytest.raises(wq.QueriesError):
        wq.validate(doc)


@pytest.mark.parametrize("switch", [
    {"x_cookie_harvest_enabled": True, "x_account_profiles": {"xa": "pa"}},
    {"reddit_session_check_enabled": True},
    {"reddit_live_methods": ["browser"], "reddit_surface_path": _abs("s.json")},
])
@pytest.mark.parametrize("missing", ["browser_path", "browser_profiles_dir"])
def test_any_browser_use_requires_browser_path_and_profiles_dir(doc, switch, missing):
    block = doc["collector"]
    block.update(x_accounts=["xa"], **switch)
    _browser_ready(block)
    wq.validate(doc)
    block[missing] = None
    with pytest.raises(wq.QueriesError, match="browser"):
        wq.validate(doc)


def test_gql_only_live_method_needs_no_browser(doc):
    doc["collector"].update(reddit_live_methods=["gql_anon"], reddit_surface_path=_abs("s.json"))
    assert wq.validate(doc).config.reddit_live_methods == ("gql_anon",)


def test_x_harvest_requires_a_profile_per_x_account(doc):
    block = doc["collector"]
    block.update(x_accounts=["xa", "xb"], x_cookie_harvest_enabled=True, x_account_profiles={"xa": "pa"})
    _browser_ready(block)
    with pytest.raises(wq.QueriesError, match="profile"):
        wq.validate(doc)
    block["x_account_profiles"]["xb"] = "pb"
    wq.validate(doc)


def test_reddit_live_methods_require_surface_path(doc):
    doc["collector"]["reddit_live_methods"] = ["gql_anon"]
    with pytest.raises(wq.QueriesError, match="reddit_surface_path"):
        wq.validate(doc)


def test_x_surface_path_must_be_outside_the_repository(doc):
    doc["collector"]["x_surface_path"] = str(wq.REPO_ROOT / "private" / "x_surface.json")
    with pytest.raises(wq.QueriesError, match="x_surface_path"):
        wq.validate(doc)
    doc["collector"]["x_surface_path"] = _abs("x_surface.json")
    wq.validate(doc)


def test_reddit_labels_disjoint_from_x_labels(doc):
    block = doc["collector"]
    block.update(x_accounts=["shared"], reddit_browser_accounts=[{"label": "shared", "profile": "p"}])
    with pytest.raises(wq.QueriesError, match="disjoint"):
        wq.validate(doc)


@pytest.mark.parametrize("x_profiles,reddit_profile", [
    ({"xa": "same"}, "same"),
    ({"xa": "one", "xb": "one"}, "other"),
])
def test_profile_directory_identity_unique_across_both_sites(doc, x_profiles, reddit_profile):
    block = doc["collector"]
    block.update(x_accounts=["xa", "xb"], x_account_profiles=x_profiles,
                 reddit_browser_accounts=[{"label": "ra", "profile": reddit_profile}])
    with pytest.raises(wq.QueriesError, match="profile"):
        wq.validate(doc)


def test_profile_identity_normalizes_windows_path_identity():
    norm = wq.profile_identity
    assert norm("prof_a") == norm("PROF_A") == norm("prof_a.") == norm("prof_a ") == norm("prof_a. .")
    assert norm("prof_a") != norm("prof_b")


def test_quiet_hours_may_cross_midnight_and_need_configured_labels(doc):
    block = doc["collector"]
    block.update(x_accounts=["xa"], x_account_quiet_hours={
        "xa": {"timezone": "America/New_York", "start": "22:00", "end": "05:00"}})
    assert wq.validate(doc).config.x_account_quiet_hours["xa"]["end"] == "05:00"
