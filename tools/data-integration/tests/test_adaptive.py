"""adaptive.py: machine-local SQLite baseline; lost store = uncertain; relocated = changed; nothing guessed."""
from __future__ import annotations

import sysconfig
from pathlib import Path

import pytest

from data_integration import adaptive, paths, status

FIX = Path(__file__).parent / "fixtures"
URL = "https://a.example.test/data/prices"
SEL = "table.prices"


def _h(name):
    return (FIX / name).read_text()


@pytest.fixture
def db(tmp_path):
    return tmp_path / "scrape" / "adaptive.sqlite"


def test_store_path_outside_repo_and_site_packages(monkeypatch):
    monkeypatch.delenv("DIT_SCRAPE_DIR", raising=False)
    p = adaptive.store_path().resolve()
    root = paths._repo_root().resolve()
    assert root not in p.parents
    for key in ("purelib", "platlib"):
        assert Path(sysconfig.get_paths()[key]).resolve() not in p.parents
    assert "site-packages" not in p.parts


def test_store_path_follows_scrape_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("DIT_SCRAPE_DIR", str(tmp_path / "s"))
    assert adaptive.store_path().parent == tmp_path / "s"


def test_lost_store_is_uncertain_and_creates_nothing(db):
    r = adaptive.assess(_h("ok.html"), SEL, url=URL, path=db)
    assert r.status == status.UNCERTAIN
    assert not db.exists()


def test_remember_then_same_page_ok(db):
    adaptive.remember(_h("ok.html"), SEL, url=URL, path=db)
    assert db.is_file()
    assert adaptive.assess(_h("ok.html"), SEL, url=URL, path=db).status == status.OK


def test_relocated_layout_is_changed(db):
    adaptive.remember(_h("ok.html"), SEL, url=URL, path=db)
    r = adaptive.assess(_h("changed.html"), SEL, url=URL, path=db)
    assert r.status == status.CHANGED


def test_unmatched_is_uncertain(db):
    adaptive.remember(_h("ok.html"), SEL, url=URL, path=db)
    r = adaptive.assess(_h("no_table.html"), SEL, url=URL, path=db)
    assert r.status == status.UNCERTAIN


def test_assess_never_writes_baseline(db):
    adaptive.remember(_h("ok.html"), SEL, url=URL, path=db)
    before = db.read_bytes()
    adaptive.assess(_h("changed.html"), SEL, url=URL, path=db)
    assert db.read_bytes() == before


def test_baseline_for_other_selector_is_uncertain(db):
    adaptive.remember(_h("ok.html"), SEL, url=URL, path=db)
    assert adaptive.assess(_h("ok.html"), "table", url=URL, path=db).status == status.UNCERTAIN
