"""S-OpsProbe: deterministic surface proposal (B3), per-section publication (B6), owner approval only."""
from __future__ import annotations

import io
import json

import pytest

from api.data.attention import reddit_surface as rs
from api.scripts import surface_tool as st
from api.tests.scripts.reddit_probe_fixtures import SECRET_MARK, bootstrap_captures, capture, listing, listing_url

SUBS = ("bitcoin", "ethereum")


def _propose(captures=None, **kw):
    return st.propose("browser", bootstrap_captures() if captures is None else captures, subreddits=SUBS,
                      refused_hosts=kw.pop("refused_hosts", {}), **kw)


def test_valid_proposal_maps_both_lanes_and_validates_against_bodies():
    p = _propose()
    assert p.ok, p.reasons
    section = p.section
    sec = rs.load_section("browser", section)  # grammar v1 valid
    assert section["sha256"] == rs.section_sha256(section) and section["revision"] == 1
    assert section["hosts"] == ["www.reddit.com"]
    lanes = {e.lane: e for e in sec.endpoints}
    assert set(lanes) == {"posts", "comments"}
    posts = next(e for e in section["endpoints"] if e["lane"] == "posts")
    assert posts["match"]["url"] == "/svc/r/*/new.json*"
    assert posts["items"]["path"] == "/data/children/[*]"
    f = posts["fields"]
    assert f["id"] == {"pointer": "/data/name"} and f["kind"] == {"const": "post"}
    assert f["subreddit"] == {"pointer": "/data/subreddit"} and f["created"]["transform"] == "epoch_s"
    assert f["text"] == {"pointer": "/data/selftext"}
    assert f["text_complete"] == {"flag": {"pointer": "/data/is_truncated", "transform": "bool_not"}}
    assert f["num_comments"] == {"pointer": "/data/num_comments"}
    assert posts["continuation"] == {"next_cursor": "/data/after", "has_more": None, "request_cursor": "query:after"}
    com = next(e for e in section["endpoints"] if e["lane"] == "comments")
    assert com["items"] == {"path": "/1/data/children/[*]", "where": {"pointer": "/kind", "op": "eq", "value": "t1"}}
    assert com["fields"]["parent_id"] == {"pointer": "/data/parent_id"}
    assert com["continuation"]["next_cursor"] == "/1/data/after"
    assert p.stats == {"posts": 72, "comments": 2, "chain_pages": 3}


def test_proposal_is_deterministic_and_holds_no_values():
    a, b = _propose(), _propose()
    assert a.section == b.section
    assert SECRET_MARK not in json.dumps(a.public()) and "user3" not in json.dumps(a.public())


def test_too_few_items_refuses():
    caps = [capture(listing_url("bitcoin", p), listing("bitcoin", p, per_page=4)) for p in range(3)]
    p = _propose(caps)
    assert not p.ok and "too_few_items" in p.reasons and p.section is None


def test_missing_cursor_chain_refuses():
    caps = [c for c in bootstrap_captures() if "after=" not in c.url]
    p = _propose(caps)
    assert not p.ok and "no_cursor_chain" in p.reasons


def test_missing_comments_lane_refuses():
    caps = [c for c in bootstrap_captures() if "/comments/" not in c.url]
    assert "no_comments_lane" in _propose(caps).reasons


def test_ambiguous_field_refuses():
    caps = bootstrap_captures()
    for c in caps:  # a second `author` key at equal depth: tie on name and length
        doc = json.loads(c.body)
        for lst in (doc if isinstance(doc, list) else [doc]):
            for ch in lst["data"]["children"]:
                if ch["kind"] == "t3":
                    ch["meta"] = {"author": ch["data"]["author"]}
                    ch["data"]["sub"] = {"x": 1}
        object.__setattr__(c, "body", json.dumps(doc).encode())
    p = _propose(caps)
    assert not p.ok and "ambiguous:author" in p.reasons


def test_no_full_text_proof_is_unsupported_format():
    caps = bootstrap_captures()
    for c in caps:
        object.__setattr__(c, "body", c.body.replace(b'"is_truncated": false, ', b""))
    p = _propose(caps)
    assert not p.ok and "unsupported_format" in p.reasons


def test_non_json_bodies_are_unsupported_format():
    caps = [capture(c.url, {}, ctype="text/html") for c in bootstrap_captures()]
    assert "unsupported_format" in _propose(caps).reasons


def test_refused_hosts_become_candidate_hosts_never_background():
    p = _propose(refused_hosts={"gql.reddit.com": 3, "BAD host": 1})
    assert p.ok and p.section["hosts"] == ["www.reddit.com", "gql.reddit.com"]


def test_x_session_proposal_is_hosts_only():
    p = st.propose("x_session", [], subreddits=(), refused_hosts={"abs.twimg.com": 2, "api.x.com": 1})
    assert p.ok and p.section == {"revision": 1, "hosts": ["abs.twimg.com", "api.x.com"],
                                  "sha256": rs.section_sha256({"revision": 1, "hosts": ["abs.twimg.com", "api.x.com"]})}


def _published(tmp_path, cache_root):
    surface = tmp_path / "surface.json"
    p = _propose()
    st.write_candidate(cache_root, p)
    assert st.main(["--approve-surface", "browser"], cache_root=cache_root, surface_path=surface,
                   out=io.StringIO()) == 0
    return surface


def test_approve_publishes_only_the_candidate_section(tmp_path):
    cache_root = tmp_path / "cache"
    surface = tmp_path / "surface.json"
    surface.write_text(json.dumps({"sections": {"gql_anon": {"keep": 1}}}))
    st.write_candidate(cache_root, _propose())
    out = io.StringIO()
    assert st.main(["--approve-surface", "browser"], cache_root=cache_root, surface_path=surface, out=out) == 0
    doc = json.loads(surface.read_text())
    assert doc["sections"]["gql_anon"] == {"keep": 1}
    sec = rs.load_surface(surface, "browser")
    assert json.loads(out.getvalue()) == {"section": "browser", "state": "published", "revision": 1,
                                          "section_sha256": sec.sha256}
    assert not st.candidate_path(cache_root, "browser").exists()


def test_second_approval_bumps_revision_and_changes_hash(tmp_path):
    cache_root = tmp_path / "cache"
    surface = _published(tmp_path, cache_root)
    first = rs.load_surface(surface, "browser")
    p = st.propose("browser", bootstrap_captures(), subreddits=SUBS, refused_hosts={"gql.reddit.com": 1},
                   current=json.loads(surface.read_text())["sections"]["browser"])
    assert p.section["revision"] == 2
    st.write_candidate(cache_root, p)
    assert st.main(["--approve-surface", "browser"], cache_root=cache_root, surface_path=surface,
                   out=io.StringIO()) == 0
    second = rs.load_surface(surface, "browser")
    assert second.revision == 2 and second.sha256 != first.sha256


def test_approve_without_candidate_or_surface_path_refuses(tmp_path):
    out = io.StringIO()
    assert st.main(["--approve-surface", "browser"], cache_root=tmp_path, surface_path=tmp_path / "s.json",
                   out=out) == 2
    assert json.loads(out.getvalue())["reason"] == "no_candidate"
    out = io.StringIO()
    assert st.main(["--approve-surface", "browser"], cache_root=tmp_path, surface_path=None, out=out) == 2
    assert json.loads(out.getvalue())["reason"] == "surface_path_unset"


def test_tampered_candidate_is_refused(tmp_path):
    st.write_candidate(tmp_path, _propose())
    path = st.candidate_path(tmp_path, "browser")
    doc = json.loads(path.read_text())
    doc["section"]["hosts"].append("evil.example")
    path.write_text(json.dumps(doc))
    out = io.StringIO()
    assert st.main(["--approve-surface", "browser"], cache_root=tmp_path, surface_path=tmp_path / "s.json",
                   out=out) == 2
    assert json.loads(out.getvalue())["reason"] == "candidate_invalid"


def test_surface_propose_lists_the_candidate_without_values(tmp_path):
    st.write_candidate(tmp_path, _propose(refused_hosts={"gql.reddit.com": 1}))
    out = io.StringIO()
    assert st.main(["surface-propose", "--section", "browser"], cache_root=tmp_path, surface_path=None, out=out) == 0
    view = json.loads(out.getvalue())
    assert view["section"] == "browser" and view["ok"] is True and "gql.reddit.com" in view["candidate_hosts"]
    assert SECRET_MARK not in out.getvalue()
    out = io.StringIO()
    assert st.main(["surface-propose", "--section", "gql_anon"], cache_root=tmp_path, surface_path=None, out=out) == 2


def test_refused_proposal_writes_no_candidate(tmp_path):
    p = _propose([c for c in bootstrap_captures() if "/comments/" not in c.url])
    with pytest.raises(ValueError):
        st.write_candidate(tmp_path, p)
    assert not st.candidate_path(tmp_path, "browser").exists()
