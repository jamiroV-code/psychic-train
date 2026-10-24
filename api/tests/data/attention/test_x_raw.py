"""W8d1 AC45, AC54: raw page archive (gzipped, scrubbed, versioned), retention, re-parse, evidence rows.

Fake raw pages and a fake parser stand in for the library; pure file I/O under the test cache root; no network.
"""
from __future__ import annotations

import gzip
import json
from datetime import date, datetime, timedelta, timezone

import pytest

from api.data.attention import web_queries as wq
from api.data.attention import x_filters as xf
from api.data.attention import x_raw as xr

DAY = date(2026, 10, 20)
END = datetime(2026, 10, 21, tzinfo=timezone.utc)
AT = END + timedelta(hours=3)
CFG = wq.load().config
SOL = xf.Coin("SOL", "Solana")
PLANTED = "planted-secret-0123456789"


@pytest.fixture(autouse=True)
def _isolated(attention_cache):
    return attention_cache


def entry(i: int, hours_back: float, text: str | None = None) -> dict:
    when = END - timedelta(hours=hours_back)
    return {"entryId": f"tweet-{i}", "id": i, "date": when.isoformat(), "text": text or f"Solana post {i}",
            "uid": 1000 + i}


def fake_parse(body: dict) -> list[xf.Tweet]:
    out = []
    for e in body["entries"]:
        if e.get("broken"):
            continue  # the library drops a tweet it cannot parse and continues
        u = xf.XUser(e["uid"], datetime(2024, 1, 1, tzinfo=timezone.utc), 100, 100, "https://img/p.jpg", False)
        out.append(xf.Tweet(e["id"], datetime.fromisoformat(e["date"]), e["text"], u, "en", ("SOL",)))
    return out


def write(attempt: int, page: int, entries: list[dict], *, retries: int = 0, headers=None, parser="x-parse-1"):
    body = {"entries": entries}
    return xr.write_page("SOL", DAY, attempt=attempt, page=page, body=body,
                         entry_ids=tuple(e["entryId"] for e in entries), retries=retries,
                         headers=headers or {"x-rate-limit-remaining": "48", "x-rate-limit-limit": "50"},
                         collected_at=AT, parser_version=parser, reader_version="fake-1")


def meta(**over) -> dict:
    return {"attempt": 1, "label": "acct_a", "attempts": 1, "restarts": 0, "backend_events": [],
            "overhead_requests": 7, **over}


def test_raw_page_gzipped_with_versions_and_no_cookies():
    headers = {"x-rate-limit-remaining": "48", "x-rate-limit-limit": "50", "set-cookie": f"ct0={PLANTED}",
               "authorization": f"Bearer {PLANTED}", "x-csrf-token": PLANTED}
    body_entries = [entry(1, 1), {**entry(2, 2), "auth_token": PLANTED, "nested": {"Cookie": PLANTED}}]
    path = write(1, 0, body_entries, headers=headers)
    assert path.suffixes[-2:] == [".json", ".gz"]
    assert path.parent == xr.raw_dir(DAY, "SOL")
    assert "xsearch_raw" in path.parts and "2026-10-20" in path.parts
    raw = gzip.decompress(path.read_bytes()).decode("utf-8")
    assert PLANTED not in raw
    rec = json.loads(raw)
    assert rec["collected_at"] == AT.isoformat()
    assert (rec["parser_version"], rec["reader_version"]) == ("x-parse-1", "fake-1")
    assert (rec["rate_limit_remaining"], rec["rate_limit_limit"]) == (48, 50)
    assert rec["entries"] == 2 and "headers" not in rec


def test_raw_archive_keeps_dropped_entries():
    write(1, 0, [entry(1, 1), {**entry(2, 2), "broken": True}])
    rec = xr.read_pages("SOL", DAY)[0]
    assert len(rec["body"]["entries"]) == 2 and rec["entries"] == 2
    assert len(fake_parse(rec["body"])) == 1


def test_reparse_identical_same_parser_version():
    write(1, 0, [entry(i, 0.5 + i * 0.1) for i in range(20)])
    write(1, 1, [entry(20 + i, 2.5 + i * 0.1) for i in range(20)], retries=1)
    xr.mark_complete("SOL", DAY, meta())
    row1 = xr.reparse("SOL", DAY, parse=fake_parse, coin=SOL, cfg=CFG, parser_version="x-parse-1")
    row2 = xr.reparse("SOL", DAY, parse=fake_parse, coin=SOL, cfg=CFG, parser_version="x-parse-1")
    assert row1 == row2
    assert row1["n_read"] == 40 and row1["pages"] == 3 and row1["capped"] is True
    assert row1["account"] == "acct_a" and row1["collected_at"] == AT.isoformat()
    assert row1["overhead_requests"] == 7 and row1["window_syntax"] == CFG.x_window_syntax
    assert xr.write_x_row("SOL", row1) is True
    assert xr.write_x_row("SOL", row2) is False
    assert xr.read_x_rows("SOL") == [row1]


def test_new_parser_version_new_evidence_row_never_overwrites():
    write(1, 0, [entry(i, 0.5 + i * 0.1) for i in range(20)])
    write(1, 1, [entry(20 + i, 2.5 + i * 0.1) for i in range(20)])
    xr.mark_complete("SOL", DAY, meta())
    row1 = xr.reparse("SOL", DAY, parse=fake_parse, coin=SOL, cfg=CFG, parser_version="x-parse-1")
    assert xr.write_x_row("SOL", row1)
    tampered = {**row1, "value": 1.0}
    assert xr.write_x_row("SOL", tampered) is False  # first wins for the same (date, parser_version)
    row2 = xr.reparse("SOL", DAY, parse=lambda b: fake_parse(b)[:10], coin=SOL, cfg=CFG, parser_version="x-parse-2")
    assert xr.write_x_row("SOL", row2) is True
    rows = xr.read_x_rows("SOL")
    assert [r["parser_version"] for r in rows] == ["x-parse-1", "x-parse-2"]
    assert rows[0] == row1 and rows[0]["value"] != 1.0


def test_reparse_uses_completed_attempt_only_and_none_without_manifest():
    write(1, 0, [entry(900 + i, 0.2 + i * 0.01, "aborted Solana") for i in range(20)])
    assert xr.reparse("SOL", DAY, parse=fake_parse, coin=SOL, cfg=CFG, parser_version="x-parse-1") is None
    write(2, 0, [entry(i, 0.5 + i * 0.1) for i in range(20)])
    write(2, 1, [entry(20 + i, 2.5 + i * 0.1) for i in range(20)])
    xr.mark_complete("SOL", DAY, meta(attempt=2, attempts=2, restarts=1, label="acct_b"))
    row = xr.reparse("SOL", DAY, parse=fake_parse, coin=SOL, cfg=CFG, parser_version="x-parse-1")
    assert row["n_read"] == 40 and row["restarts"] == 1 and row["account"] == "acct_b"
    assert row["n_counted"] == 40  # no aborted tweet merged


def test_raw_retention_deletes_old_pages():
    old_day = DAY - timedelta(days=181)
    keep_day = DAY - timedelta(days=179)
    for d in (old_day, keep_day, DAY):
        xr.write_page("SOL", d, attempt=1, page=0, body={"entries": []}, entry_ids=(), retries=0, headers={},
                      collected_at=AT, parser_version="x-parse-1", reader_version="fake-1")
    assert xr.prune(now=AT, retention_days=180) == 1
    assert not xr.raw_dir(old_day, "SOL").exists()
    assert xr.raw_dir(keep_day, "SOL").exists() and xr.raw_dir(DAY, "SOL").exists()
    # A stray non-date folder is never deleted.
    stray = xr.raw_root() / "notes"
    stray.mkdir()
    assert xr.prune(now=AT, retention_days=1) == 1 and stray.exists()
    assert xr.raw_dir(DAY, "SOL").exists()  # one day old: kept with a one-day retention
    with pytest.raises(ValueError):
        xr.prune(now=AT, retention_days=0)


def test_mark_suspect_flags_earlier_rows_of_that_account_only():
    write(1, 0, [entry(i, 0.5 + i * 0.1) for i in range(20)])
    write(1, 1, [entry(20 + i, 2.5 + i * 0.1) for i in range(20)])
    xr.mark_complete("SOL", DAY, meta())
    xr.write_x_row("SOL", xr.reparse("SOL", DAY, parse=fake_parse, coin=SOL, cfg=CFG, parser_version="x-parse-1"))
    since = AT + timedelta(days=1)
    assert xr.mark_suspect("acct_b", since) == 0
    assert xr.mark_suspect("acct_a", since) == 1
    assert xr.read_x_rows("SOL")[0]["suspect_since"] == since.isoformat()
    assert xr.mark_suspect("acct_a", since + timedelta(days=1)) == 0  # first flag kept
