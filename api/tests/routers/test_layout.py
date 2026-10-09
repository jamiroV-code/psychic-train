"""T40 / S5a: GET/POST/DELETE /api/layout/{section} (C4) and the
`layout.ts` mirror. The autouse fixture keeps every request in tmp_path.
"""
from __future__ import annotations

import json
import re
import typing
from pathlib import Path

import pytest

fastapi_testclient = pytest.importorskip("fastapi.testclient")

from api.data import layout as layout_store  # noqa: E402
from api.data import watchlist as watchlist_store  # noqa: E402
from api.main import app  # noqa: E402
from api.models.layout import Layout, LayoutGroup, LayoutUpdate  # noqa: E402

_TS_PATH = Path(__file__).resolve().parents[3] / "web" / "lib" / "types" / "layout.ts"


@pytest.fixture(autouse=True)
def _redirect(tmp_path, monkeypatch):
    monkeypatch.setattr(watchlist_store, "DEFAULT_WATCHLIST_PATH", tmp_path / "watchlist.json")
    monkeypatch.delenv("SCREENER_LAYOUT_PATH", raising=False)
    return tmp_path


@pytest.fixture
def client():
    for s in ("BTC", "ETH", "SOL"):
        watchlist_store.add_coin(s)
    return fastapi_testclient.TestClient(app)


def _body(revision=0, groups=None, hidden=None):
    groups = groups if groups is not None else [{"id": "main", "name": "Main", "coins": ["SOL", "BTC", "ETH"]}]
    return {"revision": revision, "groups": groups, "hidden_lines": hidden or []}


def test_get_returns_default_for_current_watchlist(client):
    resp = client.get("/api/layout/crypto")
    assert resp.status_code == 200
    assert resp.json() == {
        "version": 1,
        "section": "crypto",
        "revision": 0,
        "saved_at": None,
        "source": "default",
        "groups": [{"id": "main", "name": "Main", "coins": ["BTC", "ETH", "SOL"]}],
        "hidden_lines": [],
    }


def test_get_never_writes(client, tmp_path):
    client.get("/api/layout/crypto")
    assert not (tmp_path / "layout.json").exists()
    (tmp_path / "layout.json").write_text("{broken")
    assert client.get("/api/layout/crypto").json()["source"] == "recovered"
    assert (tmp_path / "layout.json").read_text() == "{broken"
    assert not (tmp_path / "layout.json.bad").exists()


def test_post_then_get_returns_saved_layout(client):
    groups = [{"id": "majors", "name": "Majors", "coins": ["BTC", "ETH"]}, {"id": "alts", "name": "Alts", "coins": ["SOL"]}]
    resp = client.post("/api/layout/crypto", json=_body(0, groups, ["HYPE"]))
    assert resp.status_code == 200
    saved = resp.json()
    assert saved["revision"] == 1 and saved["source"] == "file"
    assert saved["groups"] == groups and saved["hidden_lines"] == ["HYPE"]
    assert client.get("/api/layout/crypto").json() == saved


def test_stale_post_is_409_and_file_unchanged(client, tmp_path):
    client.post("/api/layout/crypto", json=_body(0))
    before = (tmp_path / "layout.json").read_bytes()
    resp = client.post("/api/layout/crypto", json=_body(0))
    assert resp.status_code == 409
    assert resp.json()["detail"] == "layout changed elsewhere"
    assert (tmp_path / "layout.json").read_bytes() == before


def test_invalid_bodies_are_422(client, tmp_path):
    bodies = [
        _body(0, [{"id": "a", "name": "A", "coins": ["BTC"]}, {"id": "b", "name": "B", "coins": ["BTC"]}]),
        _body(0, []),
        _body(0, [{"id": "-bad", "name": "A", "coins": []}]),
        _body(0, [{"id": "a", "name": "A", "coins": [f"C{i}" for i in range(65)]}]),
        _body(0, hidden=["X"] * 65),
        _body(0, [{"id": "a", "name": "A", "coins": ["A" * 16]}]),
    ]
    for body in bodies:
        assert client.post("/api/layout/crypto", json=body).status_code == 422, body
    assert not (tmp_path / "layout.json").exists()


def test_unknown_section_is_404_on_every_method(client, tmp_path):
    assert client.get("/api/layout/stocks").status_code == 404
    assert client.post("/api/layout/stocks", json=_body(0)).status_code == 404
    assert client.delete("/api/layout/stocks").status_code == 404
    assert not (tmp_path / "layout.json").exists()


def test_delete_resets_only_crypto_and_is_idempotent(client, tmp_path):
    path = tmp_path / "layout.json"
    client.post("/api/layout/crypto", json=_body(0))
    data = json.loads(path.read_text())
    data["sections"]["equities"] = {"revision": 1, "saved_at": None, "groups": [], "hidden_lines": []}
    path.write_text(json.dumps(data))
    resp = client.delete("/api/layout/crypto")
    assert resp.status_code == 200 and resp.json()["source"] == "default" and resp.json()["revision"] == 0
    assert list(json.loads(path.read_text())["sections"]) == ["equities"]
    data["sections"].pop("crypto")
    data["sections"].pop("equities")
    path.write_text(json.dumps(data))
    client.post("/api/layout/crypto", json=_body(0))
    assert client.delete("/api/layout/crypto").status_code == 200
    assert not path.exists()
    second = client.delete("/api/layout/crypto")
    assert second.status_code == 200 and second.json()["source"] == "default"
    # An unreadable file is moved aside to `.bad` and the default comes back.
    path.write_text("{broken")
    third = client.delete("/api/layout/crypto")
    assert third.status_code == 200 and third.json()["source"] == "default"
    assert not path.exists() and (tmp_path / "layout.json.bad").read_text() == "{broken"


def test_saved_at_is_z(client):
    saved_at = client.post("/api/layout/crypto", json=_body(0)).json()["saved_at"]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", saved_at)
    assert client.get("/api/layout/crypto").json()["saved_at"] == saved_at


def _ts_type(annotation) -> str:
    if annotation is int:
        return "number"
    if annotation is str:
        return "string"
    origin, args = typing.get_origin(annotation), typing.get_args(annotation)
    if origin is list:
        inner = args[0]
        inner = typing.get_args(inner)[0] if typing.get_origin(inner) is typing.Annotated else inner
        return f"{_ts_type(inner)}[]"
    if origin is typing.Literal:
        return " | ".join(f'"{a}"' for a in args)
    if args and type(None) in args:
        return f"{_ts_type(next(a for a in args if a is not type(None)))} | null"
    if annotation is LayoutGroup:
        return "LayoutGroup"
    raise AssertionError(f"unmapped annotation {annotation!r}")


def _ts_interface(source: str, name: str) -> dict[str, str]:
    match = re.search(rf"export interface {name} \{{(.*?)\n\}}", source, re.S)
    assert match is not None, name
    return dict(re.findall(r"^\s*(\w+\??):\s*([^;]+);", match.group(1), re.M))


def test_layout_models_match_typescript():
    source = _TS_PATH.read_text()
    for model in (LayoutGroup, Layout, LayoutUpdate):
        ts = _ts_interface(source, model.__name__)
        py = {}
        for name, field in model.model_fields.items():
            annotation = field.annotation
            py[name] = "LayoutSource" if name == "source" else _ts_type(annotation)
        assert ts == py, model.__name__
    source_type = re.search(r"export type LayoutSource = ([^;]+);", source).group(1)
    assert source_type == _ts_type(Layout.model_fields["source"].annotation)


def test_layout_routes_use_only_get_post_delete():
    paths = {p: ops for p, ops in app.openapi()["paths"].items() if p.startswith("/api/layout")}
    assert list(paths) == ["/api/layout/{section}"]
    assert set(paths["/api/layout/{section}"]) == {"get", "post", "delete"}
    assert layout_store.SECTIONS == ("crypto",)
