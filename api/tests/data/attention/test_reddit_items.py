"""W8c AC29: Reddit item ledger by Reddit id, salted author hash, no username stored or logged. No network."""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone

import pytest

from api.data import cache
from api.data.attention import reddit_items as ri

D = date(2026, 10, 26)
SALT = b"0123456789abcdef0123456789abcdef"
NOW = datetime(2026, 10, 27, 10, 0, tzinfo=timezone.utc)


def row(rid="t3_abc1", user="PlantedUser", feed="search", coins=("SOL",), hasher=None, created=None, sub="CryptoCurrency"):
    h = hasher or ri.AuthorHasher(SALT)
    return ri.LedgerRow(id=rid, author_hash=h(user), subreddit=sub,
                        created=created or datetime(2026, 10, 26, 12, tzinfo=timezone.utc), collected_at=NOW,
                        feed_kind=feed, coins=tuple(coins))


def all_cache_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in cache.CACHE_ROOT.rglob("*") if p.is_file())


def test_ledger_dedupes_by_reddit_id_across_feeds_and_polls(attention_cache):
    led = ri.Ledger()
    assert led.add([row(), row(feed="new"), row(coins=("ETH",))]) == 1
    assert led.add([row(feed="comments")]) == 0
    assert led.add([row(rid="t1_xyz9", feed="comments")]) == 1
    rows = led.read_day(D)
    assert sorted(rows) == ["t1_xyz9", "t3_abc1"]
    first = rows["t3_abc1"]
    assert first.feed_kind == "search" and first.collected_at == NOW  # the first sighting is kept
    assert first.coins == ("ETH", "SOL")  # matched coins merge across sightings


def test_ledger_row_has_id_author_hash_subreddit_created_collected_feed_kind_coins(attention_cache):
    ri.Ledger().add([row()])
    doc = json.loads(ri.ledger_path(D).read_text(encoding="utf-8"))
    (stored,) = doc["rows"]
    assert set(stored) == {"id", "kind", "author_hash", "subreddit", "created", "collected_at", "feed_kind", "coins"}
    assert stored["kind"] == "t3" and stored["subreddit"] == "CryptoCurrency" and stored["coins"] == ["SOL"]
    assert len(stored["author_hash"]) == 32 and stored["feed_kind"] == "search"
    assert row(rid="t1_q").kind == "t1"


def test_username_never_stored_or_logged(attention_cache, caplog):
    caplog.set_level(logging.DEBUG)
    h = ri.AuthorHasher(SALT)
    ri.Ledger().add([row(user="PlantedUser", hasher=h), row(rid="t3_z", user="/u/PlantedUser", hasher=h)])
    text = all_cache_text() + caplog.text
    assert "planteduser" not in text.lower()
    assert h("PlantedUser") == h("/u/planteduser") == h("u/PLANTEDUSER")  # lower-cased, prefix dropped
    assert h("[deleted]") is None and h("") is None
    assert "PlantedUser" not in repr(row())


def test_hash_depends_on_salt_and_salt_must_be_long():
    assert ri.AuthorHasher(SALT)("x") != ri.AuthorHasher(SALT[::-1])("x")
    with pytest.raises(ValueError):
        ri.AuthorHasher(b"short")


def test_salt_kept_outside_the_repo(tmp_path, monkeypatch):
    inside = ri.REPO_ROOT / "api" / "salt.bin"
    monkeypatch.setenv(ri.SALT_ENV, str(inside))
    with pytest.raises(ri.SaltError):
        ri.salt_path()
    outside = tmp_path / "salt.bin"
    monkeypatch.setenv(ri.SALT_ENV, str(outside))
    assert ri.salt_path() == outside
    salt = ri.load_salt(create=True)
    assert len(salt) >= 32 and outside.exists() and ri.load_salt() == salt
    outside.write_bytes(b"x")
    with pytest.raises(ri.SaltError):
        ri.load_salt()


def test_missing_salt_without_create_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv(ri.SALT_ENV, str(tmp_path / "none.bin"))
    with pytest.raises(ri.SaltError):
        ri.load_salt()


def test_bad_rows_refused(attention_cache):
    with pytest.raises(ValueError):
        row(rid="t5_bad")
    with pytest.raises(ValueError):
        row(feed="json")
    with pytest.raises(ValueError):
        row(sub="bad/sub")


def test_ledger_rows_to_metric_items(attention_cache):
    ri.Ledger().add([row(), row(rid="t1_c1", feed="comments", coins=())])
    items = ri.to_items(ri.Ledger().read_day(D).values())
    assert {i.id for i in items} == {"t3_abc1", "t1_c1"}
    assert all(i.score is None for i in items)  # votes arrive only with the archive enrichment (W8c3)
