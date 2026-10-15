"""S-T8: approvals and scrape folders must sit outside the checkout; evidence_dir is unchanged."""
from __future__ import annotations

import sys

import pytest

from data_integration import paths


@pytest.fixture
def inside():
    return paths._repo_root() / "never-created"


def test_approvals_dir_inside_repo_raises(monkeypatch, inside):
    monkeypatch.setenv("DIT_APPROVALS_DIR", str(inside))
    with pytest.raises(paths.PathInRepo) as e:
        paths.approvals_dir()
    assert str(inside) not in str(e.value)


def test_scrape_dir_inside_repo_raises(monkeypatch, inside):
    monkeypatch.setenv("DIT_SCRAPE_DIR", str(inside))
    with pytest.raises(paths.PathInRepo):
        paths.scrape_dir()


def test_symlink_into_repo_raises(monkeypatch, tmp_path):
    link = tmp_path / "link"
    link.symlink_to(paths._repo_root(), target_is_directory=True)
    monkeypatch.setenv("DIT_APPROVALS_DIR", str(link / "x"))
    with pytest.raises(paths.PathInRepo):
        paths.approvals_dir()


def test_outside_works_and_evidence_unchanged(monkeypatch, tmp_path, inside):
    monkeypatch.setenv("DIT_APPROVALS_DIR", str(tmp_path / "a"))
    monkeypatch.setenv("DIT_SCRAPE_DIR", str(tmp_path / "s"))
    monkeypatch.setenv("DIT_EVIDENCE_DIR", str(inside))
    assert paths.approvals_dir() == tmp_path / "a"
    assert paths.scrape_dir() == tmp_path / "s"
    assert paths.evidence_dir() == inside


def test_guard_does_not_touch_sys_path(monkeypatch, tmp_path):
    before = list(sys.path)
    monkeypatch.setenv("DIT_APPROVALS_DIR", str(tmp_path / "a"))
    paths.approvals_dir()
    assert sys.path == before
