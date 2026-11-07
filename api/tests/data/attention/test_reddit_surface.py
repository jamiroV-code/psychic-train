"""Finish plan B1-B2, B6: the Reddit surface grammar engine over synthetic sections. Pure; no network."""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone

import pytest

from api.data.attention import reddit_surface as rs

T0 = 1_793_000_000  # an absolute epoch-seconds time


def listing_section() -> dict:
    return {
        "revision": 1,
        "hosts": ["www.example.test"],
        "body_format": "json",
        "endpoints": [{
            "name": "sub_new",
            "lane": "posts",
            "match": {"method": "GET", "url": "/r/*/new.api?*"},
            "items": {"path": "/data/children/[*]/data", "where": {"pointer": "/stickied", "op": "eq", "value": "no"}},
            "fields": {
                "id": {"pointer": "/name"},
                "kind": {"const": "post"},
                "subreddit": {"pointer": "/subreddit_prefixed", "transform": "strip_prefix:r/"},
                "created": {"pointer": "/created_utc", "transform": "epoch_s"},
                "author": {"pointer": "/author", "deleted_pointer": "/author_deleted"},
                "text": {"pointers": ["/title", "/selftext"], "transform": "join:\n"},
                "text_complete": {"flag": {"pointer": "/is_truncated", "transform": "bool_not"}},
                "num_comments": {"pointer": "/num_comments", "transform": "to_int"},
            },
            "continuation": {"next_cursor": "/data/after", "has_more": None, "request_cursor": "query:after"},
        }, {
            "name": "thread",
            "lane": "comments",
            "match": {"method": "POST", "url": "/gql", "operation": {"pointer": "/operationName", "equals": "Thread"}},
            "items": {"path": "/data/nodes/[*]", "discriminator": {"pointer": "/__typename", "shapes": {
                "Comment": {
                    "id": {"pointer": "/id"},
                    "kind": {"pointer": "/kind", "transform": "lower"},
                    "subreddit": {"pointer": "/sub"},
                    "created": {"pointer": "/createdAt", "transform": "iso_utc"},
                    "author": {"pointer": "/author"},
                    "text": {"pointer": "/body"},
                    "text_complete": {"declared_length": "/bodyLength"},
                    "parent_id": {"pointer": "/parent"},
                },
                "Deleted": {
                    "id": {"pointer": "/id"},
                    "kind": {"const": "comment"},
                    "subreddit": {"pointer": "/sub"},
                    "created": {"pointer": "/createdMs", "transform": "epoch_ms"},
                    "author": {"pointer": "/author"},
                    "text": {"pointer": "/body"},
                    "text_complete": {"selftext_full": True},
                },
            }}},
            "continuation": {"next_cursor": "/data/cursor", "has_more": "/data/more",
                             "request_cursor": "body:/variables/after"},
        }],
    }


def post(i: int, **over) -> dict:
    d = {"name": f"t3_a{i}", "subreddit_prefixed": "r/CryptoCurrency", "created_utc": T0 - i, "author": f"user{i}",
         "author_deleted": False, "title": "SOL up", "selftext": "body", "is_truncated": False, "num_comments": 3,
         "stickied": "no"}
    d.update(over)
    return d


def listing(*posts, after="t3_next") -> bytes:
    return json.dumps({"data": {"after": after, "children": [{"data": p} for p in posts]}}).encode()


@pytest.fixture
def section() -> rs.Section:
    return rs.load_section("browser", listing_section())


def page(section, body: bytes, *, ep=0, status=200, ctype="application/json; charset=utf-8") -> rs.Page:
    return rs.extract_page(section, section.endpoints[ep], status=status, content_type=ctype, body=body)


def failure(section, body: bytes, **kw) -> str:
    with pytest.raises(rs.SurfaceError) as exc:
        page(section, body, **kw)
    return exc.value.reason


# --- loading ---

def test_section_loads_with_hash_and_defaults(section):
    raw = listing_section()
    assert section.sha256 == rs.section_sha256(raw)
    assert section.max_body_bytes == rs.DEFAULT_MAX_BODY_BYTES
    assert rs.load_section("browser", {**raw, "sha256": rs.section_sha256(raw)}).sha256 == section.sha256


def test_load_surface_file(tmp_path):
    p = tmp_path / "surface.json"
    p.write_text(json.dumps({"sections": {"browser": listing_section()}}))
    assert rs.load_surface(p, "browser").revision == 1
    with pytest.raises(rs.SurfaceInvalid):
        rs.load_surface(p, "gql_anon")
    with pytest.raises(rs.SurfaceInvalid):
        rs.load_surface(tmp_path / "none.json", "browser")


def mutate(fn) -> dict:
    raw = listing_section()
    fn(raw)
    return raw


BAD_SECTIONS = {
    "hash": lambda r: r.update(sha256="0" * 64),
    "unknown key": lambda r: r.update(extra=1),
    "revision": lambda r: r.update(revision=0),
    "hosts": lambda r: r.update(hosts=["*.example.test"]),
    "max body": lambda r: r.update(max_body_bytes=rs.MAX_BODY_BYTES_CAP + 1),
    "transform": lambda r: r["endpoints"][0]["fields"]["created"].update(transform="eval"),
    "long prefix": lambda r: r["endpoints"][0]["fields"]["subreddit"].update(transform="strip_prefix:123456789"),
    "join outside text": lambda r: r["endpoints"][0]["fields"].update(id={"pointers": ["/a"], "transform": "join:,"}),
    "join five": lambda r: r["endpoints"][0]["fields"].update(
        text={"pointers": ["/a", "/b", "/c", "/d", "/e"], "transform": "join:,"}),
    "missing field": lambda r: r["endpoints"][0]["fields"].pop("created"),
    "unknown field": lambda r: r["endpoints"][0]["fields"].update(score={"pointer": "/score"}),
    "where op": lambda r: r["endpoints"][0]["items"]["where"].update(op="regex"),
    "three wildcards": lambda r: r["endpoints"][0]["items"].update(path="/[*]/[*]/[*]"),
    "deep": lambda r: r["endpoints"][0]["items"].update(path="/a" * 13),
    "wildcard in field": lambda r: r["endpoints"][0]["fields"].update(id={"pointer": "/[*]/name"}),
    "cursor placement": lambda r: r["endpoints"][0]["continuation"].update(request_cursor="header:x"),
    "lane": lambda r: r["endpoints"][0].update(lane="search"),
    "method": lambda r: r["endpoints"][0]["match"].update(method="PUT"),
    "duplicate names": lambda r: r["endpoints"][1].update(name="sub_new"),
    "kind const": lambda r: r["endpoints"][0]["fields"].update(kind={"const": "link"}),
}


@pytest.mark.parametrize("name", sorted(BAD_SECTIONS))
def test_invalid_sections_rejected(name):
    with pytest.raises(rs.SurfaceInvalid) as exc:
        rs.load_section("browser", mutate(BAD_SECTIONS[name]))
    assert exc.value.reason == "surface_invalid"


@pytest.mark.parametrize("fn", [
    lambda r: r.update(body_format="html"),
    lambda r: r["endpoints"][0]["fields"].pop("text_complete"),
    lambda r: r["endpoints"][0]["fields"].update(text_complete={"min_length": 10}),
    lambda r: r["endpoints"][0]["fields"].update(text_complete={"flag": {"pointer": "/x"}, "declared_length": "/y"}),
])
def test_unsupported_format_without_json_or_full_text_proof(fn):
    with pytest.raises(rs.SurfaceInvalid) as exc:
        rs.load_section("browser", mutate(fn))
    assert exc.value.reason == "unsupported_format"


def test_bounds_on_pointers_and_size():
    raw = listing_section()
    raw["endpoints"][0]["items"]["path"] = "/" + "x" * (rs.MAX_SECTION_BYTES)
    with pytest.raises(rs.SurfaceInvalid):
        rs.load_section("browser", raw)
    raw = listing_section()
    shapes = raw["endpoints"][1]["items"]["discriminator"]["shapes"]
    base = shapes["Comment"]
    for i in range(30):  # 4 shapes max: too many shapes is invalid
        shapes[f"S{i}"] = copy.deepcopy(base)
    with pytest.raises(rs.SurfaceInvalid):
        rs.load_section("browser", raw)
    c = rs._Count()
    with pytest.raises(rs.SurfaceInvalid):
        for _ in range(rs.MAX_POINTERS + 1):
            c.ptr("/a")


def test_unknown_section_name_rejected():
    with pytest.raises(rs.SurfaceInvalid):
        rs.load_section("x_session", listing_section())


# --- request matching and cursor placement ---

def test_request_match_by_host_glob_and_operation(section):
    assert rs.match_request(section, "GET", "https://www.example.test/r/CryptoCurrency/new.api?limit=100").name == \
        "sub_new"
    assert rs.match_request(section, "GET", "https://other.example.test/r/x/new.api?limit=1") is None
    assert rs.match_request(section, "GET", "http://www.example.test/r/x/new.api?limit=1") is None
    assert rs.match_request(section, "GET", "https://www.example.test/r/x/hot.api?limit=1") is None
    body = json.dumps({"operationName": "Thread", "variables": {}}).encode()
    assert rs.match_request(section, "POST", "https://www.example.test/gql", body).name == "thread"
    assert rs.match_request(section, "POST", "https://www.example.test/gql", b'{"operationName":"Feed"}') is None
    assert rs.match_request(section, "POST", "https://www.example.test/gql", b"not json") is None


def test_cursor_placement_query_body_path(section):
    url, body = rs.place_cursor(section.endpoints[0], "https://www.example.test/r/x/new.api?limit=100&after=old",
                                None, "t3_abc")
    assert url == "https://www.example.test/r/x/new.api?limit=100&after=t3_abc" and body is None
    orig = {"operationName": "Thread", "variables": {"after": None}}
    url, body = rs.place_cursor(section.endpoints[1], "https://www.example.test/gql", orig, "cur1")
    assert body["variables"]["after"] == "cur1" and orig["variables"]["after"] is None
    raw = mutate(lambda r: r["endpoints"][0]["continuation"].update(request_cursor="path:3"))
    ep = rs.load_section("browser", raw).endpoints[0]
    assert rs.place_cursor(ep, "https://www.example.test/r/x/c0/new.api", None, "c9")[0] == \
        "https://www.example.test/r/x/c9/new.api"
    with pytest.raises(rs.SurfaceError):
        rs.place_cursor(section.endpoints[1], "https://www.example.test/gql", {"x": 1}, "c")


# --- extraction: every construct ---

def test_listing_extracts_items_where_join_prefix_epoch_and_cursor(section):
    p = page(section, listing(post(1), post(2, stickied="yes"), post(3, author=None, author_deleted=True)))
    assert [i.id for i in p.items] == ["t3_a1", "t3_a3"]  # the where predicate drops the stickied post
    first = p.items[0]
    assert first.kind == "post" and first.subreddit == "CryptoCurrency" and first.num_comments == 3
    assert first.created == datetime.fromtimestamp(T0 - 1, tz=timezone.utc)
    assert first.text == "SOL up\nbody" and "SOL" not in repr(first) and "user1" == first.author
    assert p.items[1].author is None
    assert p.next_cursor == "t3_next" and p.has_more is None


def test_discriminator_iso_epoch_ms_declared_length_and_has_more(section):
    nodes = [{"__typename": "Comment", "id": "t1_c1", "kind": "COMMENT", "sub": "solana", "author": "u",
              "createdAt": "2026-11-06T10:00:00Z", "body": "hello", "bodyLength": 5, "parent": "t3_a1"},
             {"__typename": "Deleted", "id": "t1_c2", "sub": "solana", "author": None, "createdMs": T0 * 1000,
              "body": ""}]
    body = json.dumps({"data": {"nodes": nodes, "cursor": None, "more": False}}).encode()
    p = page(section, body, ep=1)
    assert [(i.id, i.kind, i.parent_id) for i in p.items] == [("t1_c1", "comment", "t3_a1"), ("t1_c2", "comment", None)]
    assert p.items[0].created == datetime(2026, 11, 6, 10, tzinfo=timezone.utc)
    assert p.has_more is False and p.next_cursor is None
    nodes[0]["__typename"] = "Ad"
    assert failure(section, json.dumps({"data": {"nodes": nodes, "more": False}}).encode(), ep=1) == "schema_mismatch"


# --- extraction: fail closed (B2) ---

@pytest.mark.parametrize("field", ["name", "subreddit_prefixed", "created_utc", "author", "title", "is_truncated"])
def test_every_mandatory_field_missing_is_a_mismatch(section, field):
    p = post(1)
    del p[field]
    assert failure(section, listing(p)) == "schema_mismatch"


@pytest.mark.parametrize("over", [
    {"name": "t5_abc"}, {"name": "t1_abc"}, {"name": "t3_ABC"}, {"name": "t3_" + "a" * 17},
    {"created_utc": "yesterday"}, {"created_utc": True}, {"subreddit_prefixed": "r/a b"},
    {"num_comments": -1}, {"num_comments": "x"}, {"title": 5}, {"author": 7},
])
def test_wrong_types_and_bad_ids_are_mismatches(section, over):
    assert failure(section, listing(post(1, **over))) == "schema_mismatch"


def test_preview_text_rejected(section):
    assert failure(section, listing(post(1, is_truncated=True))) == "schema_mismatch"
    nodes = [{"__typename": "Comment", "id": "t1_c1", "kind": "comment", "sub": "solana", "author": "u",
              "createdAt": "2026-11-06T10:00:00Z", "body": "hello wor", "bodyLength": 40}]
    assert failure(section, json.dumps({"data": {"nodes": nodes, "more": False}}).encode(), ep=1) == "schema_mismatch"


def test_naive_timestamp_rejected(section):
    nodes = [{"__typename": "Comment", "id": "t1_c1", "kind": "comment", "sub": "solana", "author": "u",
              "createdAt": "2026-11-06T10:00:00", "body": "h", "bodyLength": 1}]
    assert failure(section, json.dumps({"data": {"nodes": nodes, "more": False}}).encode(), ep=1) == "schema_mismatch"


@pytest.mark.parametrize("body,reason", [
    (b"", "empty_shell"), (b"   ", "empty_shell"), (b"<html>blocked</html>", "empty_shell"), (b"42", "empty_shell"),
    (b'{"data": {}}', "schema_mismatch"), (b'{"data": {"children": {}}}', "schema_mismatch"),
])
def test_empty_shell_and_missing_container(section, body, reason):
    assert failure(section, body) == reason


def test_unsupported_content_status_and_size(section):
    assert failure(section, listing(post(1)), ctype="text/html") == "unsupported_format"
    assert failure(section, listing(post(1)), ctype="application/x-protobuf") == "unsupported_format"
    assert failure(section, listing(post(1)), status=403) == "error"
    big = listing(*(post(i) for i in range(3000)))
    assert len(big) > section.max_body_bytes
    assert failure(section, big) == "cap"
    assert page(section, listing(post(1)), ctype="application/vnd.example+json").items


def test_empty_listing_is_an_empty_page_not_a_failure(section):
    p = page(section, listing(after=None))
    assert p.items == () and p.next_cursor is None


def test_bad_cursor_type_is_a_mismatch(section):
    assert failure(section, listing(post(1), after=5)) == "schema_mismatch"
