"""Equity ticker store (S3). Every test points SCREENER_EQUITIES_PATH at a tmp
file, so the real `api/data/equities.json` is never read or written."""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

from api.data import equities_store


@pytest.fixture
def store_path(tmp_path, monkeypatch):
    path = tmp_path / "equities.json"
    monkeypatch.setenv("SCREENER_EQUITIES_PATH", str(path))
    return path


def test_add_uppercases_and_persists(store_path):
    assert equities_store.add_ticker("aapl") == ["AAPL"]
    assert equities_store.add_ticker(" brk.b ") == ["AAPL", "BRK.B"]
    assert json.loads(store_path.read_text()) == {"tickers": ["AAPL", "BRK.B"]}
    assert equities_store.load_tickers() == ["AAPL", "BRK.B"]


def test_add_is_idempotent(store_path):
    equities_store.add_ticker("MSFT")
    before = store_path.stat().st_mtime_ns
    assert equities_store.add_ticker("msft") == ["MSFT"]
    assert store_path.stat().st_mtime_ns == before  # no rewrite


def test_remove_and_remove_missing_raises(store_path):
    equities_store.add_ticker("KO")
    equities_store.add_ticker("XOM")
    assert equities_store.remove_ticker("ko") == ["XOM"]
    with pytest.raises(equities_store.TickerNotFoundError):
        equities_store.remove_ticker("KO")
    assert equities_store.load_tickers() == ["XOM"]


@pytest.mark.parametrize("bad", ["", "1ABC", "TOOLONGTICKER", "AA PL", "A/B", "$SPY", None])
def test_invalid_ticker_rejected(store_path, bad):
    with pytest.raises(equities_store.InvalidTickerError):
        equities_store.add_ticker(bad)
    assert not store_path.exists()


def test_thirty_first_refused(store_path):
    tickers = [f"T{i:03d}" for i in range(30)]
    for t in tickers:
        equities_store.add_ticker(t)
    with pytest.raises(equities_store.TickerLimitError):
        equities_store.add_ticker("LATE")
    assert equities_store.load_tickers() == tickers
    assert equities_store.MAX_TICKERS == 30
    assert equities_store.CAP_MESSAGE == (
        "Equities list is full: 30 tickers maximum. Remove a ticker to add another."
    )


def test_over_cap_file_is_kept_new_refused_existing_readds(store_path):
    tickers = [f"T{i:03d}" for i in range(31)]
    store_path.write_text(json.dumps({"tickers": tickers}))
    with pytest.raises(equities_store.TickerLimitError):
        equities_store.add_ticker("NEW")
    assert equities_store.add_ticker("t005") == tickers
    assert equities_store.load_tickers() == tickers


def test_at_thirty_new_refused_then_accepted_after_remove(store_path):
    for i in range(30):
        equities_store.add_ticker(f"T{i:03d}")
    with pytest.raises(equities_store.TickerLimitError):
        equities_store.add_ticker("NEW")
    equities_store.remove_ticker("T000")
    assert equities_store.add_ticker("NEW")[-1] == "NEW"
    assert len(equities_store.load_tickers()) == 30


def test_interrupted_write_keeps_old_file(store_path, monkeypatch):
    equities_store.add_ticker("NVDA")
    original = store_path.read_text()

    def boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(equities_store.os, "replace", boom)
    with pytest.raises(OSError):
        equities_store.add_ticker("SPY")
    assert store_path.read_text() == original
    assert [p.name for p in store_path.parent.iterdir()] == [store_path.name]  # temp removed


def test_path_override_honoured_at_call_time(tmp_path, monkeypatch):
    first, second = tmp_path / "a.json", tmp_path / "b.json"
    monkeypatch.setenv("SCREENER_EQUITIES_PATH", str(first))
    equities_store.add_ticker("AAPL")
    monkeypatch.setenv("SCREENER_EQUITIES_PATH", str(second))
    assert equities_store.load_tickers() == []
    equities_store.add_ticker("MSFT")
    assert json.loads(first.read_text())["tickers"] == ["AAPL"]
    assert json.loads(second.read_text())["tickers"] == ["MSFT"]
    monkeypatch.delenv("SCREENER_EQUITIES_PATH")
    assert equities_store.equities_path() == equities_store.DEFAULT_EQUITIES_PATH


@pytest.mark.parametrize("operation, expected", [
    ("add", ["AAPL", "MSFT"]), ("remove", []),
])
def test_open_reader_excludes_atomic_replacement(store_path, monkeypatch, operation, expected):
    equities_store.add_ticker("AAPL")
    opened, release, contended = (threading.Event() for _ in range(3))
    real_lock = equities_store._LOCK
    real_read = Path.read_text
    real_replace = equities_store.os.replace
    errors, snapshots, replacements = [], [], []

    class ObservedLock:
        def __enter__(self):
            if not real_lock.acquire(blocking=False):
                contended.set()
                real_lock.acquire()
            return self

        def __exit__(self, *args):
            real_lock.release()

    def held_read(path, *args, **kwargs):
        if path != store_path or threading.current_thread().name != "store-reader":
            return real_read(path, *args, **kwargs)
        with path.open("r") as reader:
            opened.set()
            if not release.wait(10):
                raise TimeoutError("reader release not signaled")
            return reader.read()

    def replace(src, dst):
        assert release.is_set()
        real_replace(src, dst)
        replacements.append(dst)

    def read():
        try:
            snapshots.append(equities_store.load_tickers())
        except BaseException as exc:
            errors.append(exc)

    def mutate():
        try:
            if operation == "add":
                equities_store.add_ticker("MSFT")
            else:
                equities_store.remove_ticker("AAPL")
        except BaseException as exc:
            errors.append(exc)

    monkeypatch.setattr(equities_store, "_LOCK", ObservedLock())
    monkeypatch.setattr(Path, "read_text", held_read)
    monkeypatch.setattr(equities_store.os, "replace", replace)
    reader = threading.Thread(target=read, name="store-reader", daemon=True)
    writer = threading.Thread(target=mutate, daemon=True)
    reader.start()
    try:
        assert opened.wait(5)
        writer.start()
        assert contended.wait(5), "writer never contended on the reader's store lock"
        assert replacements == []
    finally:
        release.set()
        deadline = time.monotonic() + 10
        for worker in (reader, writer):
            if worker.ident is not None:
                worker.join(max(0, deadline - time.monotonic()))
    assert not reader.is_alive() and not writer.is_alive()
    assert errors == []
    assert snapshots == [["AAPL"]]
    assert replacements == [store_path]
    assert equities_store.load_tickers() == expected


def test_public_read_error_releases_lock_for_another_thread(store_path, monkeypatch):
    equities_store.add_ticker("AAPL")
    real_read = Path.read_text

    def fail(path, *args, **kwargs):
        if path == store_path:
            raise OSError("controlled read failure")
        return real_read(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "read_text", fail)
        with pytest.raises(OSError, match="controlled read failure"):
            equities_store.load_tickers()
    results, errors = [], []

    def read():
        try:
            results.append(equities_store.load_tickers())
        except BaseException as exc:
            errors.append(exc)

    worker = threading.Thread(target=read, daemon=True)
    worker.start()
    worker.join(5)
    assert not worker.is_alive(), "public read leaked its lock"
    assert errors == [] and results == [["AAPL"]]
