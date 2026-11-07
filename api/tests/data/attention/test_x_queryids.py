"""S-XProto XP-1: pure query-id registry, bundle parsing and honest check states (synthetic data only)."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from api.data.attention import x_queryids as q

NOW = datetime(2026, 11, 7, 6, tzinfo=UTC)
NEW = "vLHjqbDv7TPFMBkIIO1nOA"
HASH = "7e80395699a4329fa"


def bundle(mapping):
    return ";".join(f'e.exports={{queryId:"{i}",operationName:"{op}",operationType:"query"}}' for op, i in mapping)


def evidence(candidate=NEW, result="passed", evidence_id="ev1"):
    return {"evidence_id": evidence_id, "operation": "SearchTimeline", "candidate_id": candidate,
            "account_label": "alpha", "evaluated_at": NOW.isoformat(), "result": result, "entries": 20, "parse_ok": True}


def test_pinned_table_matches_the_pinned_library_constants():
    api = pytest.importorskip("twscrape.api")
    for op, value in q.PINNED.items():
        assert getattr(api, "OP_" + op).split("/", 1) == [value, op]
    assert q.TRACKED == "SearchTimeline" and set(q.OPERATIONS) == set(q.PINNED)


def test_initial_state_is_pinned_and_matches_the_status_reader_shape():
    state = q.initial_state()
    assert state["version"] == 1 and state["check_state"] == "unknown" and state["last_check"] is None
    for op in q.OPERATIONS:
        entry = state["operations"][op]
        assert entry["active"]["source"] == "pinned" and entry["active"]["id"] == q.PINNED[op]
        assert entry["candidate"] is None and entry["observed"] is None
    assert q.active_id(state, "SearchTimeline") == q.PINNED["SearchTimeline"]
    assert q.validate(json.loads(json.dumps(state))) == state


@pytest.mark.parametrize("mutate", [
    lambda s: s.update(version=2), lambda s: s.update(extra=1), lambda s: s.pop("evidence"),
    lambda s: s["operations"].pop("TweetDetail"), lambda s: s["operations"].update(Other=s["operations"]["UserTweets"]),
    lambda s: s["operations"]["SearchTimeline"]["active"].update(id="short"),
    lambda s: s["operations"]["SearchTimeline"]["active"].update(id="x" * 33),
    lambda s: s["operations"]["SearchTimeline"]["active"].update(source="network"),
    lambda s: s["operations"]["SearchTimeline"].update(candidate={"id": "bad id!", "seen_at": "x"}),
    lambda s: s.update(evidence=[evidence(evidence_id=str(i)) for i in range(q.EVIDENCE_LIMIT + 1)]),
    lambda s: s.update(check_state="great"), lambda s: s.update(bundle_sha256="zz"),
    lambda s: s.update(budget={"day": "2026-11-07", "used": -1}),
])
def test_invalid_state_is_replaced_by_the_pinned_initial_state(mutate):
    state = q.initial_state()
    mutate(state)
    assert q.validate(state) == q.initial_state()


def test_bundle_active_without_matching_passed_evidence_is_treated_as_pinned():
    state = q.initial_state()
    state["operations"]["SearchTimeline"]["active"] = {"id": NEW, "source": "bundle",
                                                       "adopted_at": NOW.isoformat(), "evidence_id": "ev1"}
    assert q.active_id(q.validate(state), "SearchTimeline") == q.PINNED["SearchTimeline"]
    for wrong in (evidence(result="inconclusive"), evidence(candidate="A" * 22), evidence(evidence_id="ev2")):
        state["evidence"] = [wrong]
        assert q.active_id(q.validate(state), "SearchTimeline") == q.PINNED["SearchTimeline"]
    state["evidence"] = [evidence()]
    assert q.active_id(q.validate(state), "SearchTimeline") == NEW


def test_load_and_save_round_trip_atomically_and_tolerate_missing_or_garbage(tmp_path):
    path = q.state_path(tmp_path)
    assert path == tmp_path / "attention" / "_pc_state" / "x_queryids.json"
    assert q.load(path) == q.initial_state() and not path.exists()
    state = q.initial_state()
    state["last_check"] = NOW.isoformat()
    q.save(path, state)
    assert q.load(path) == state and not list(path.parent.glob("*.tmp"))
    path.write_text("{not json", encoding="utf-8")
    assert q.load(path) == q.initial_state()
    path.write_bytes(b" " * (q.STATE_LIMIT + 1))
    assert q.load(path) == q.initial_state()


def test_bundle_name_discovery_requires_exactly_one_hash_and_rebuilds_the_url_from_constants():
    html = f'<script src="https://abs.twimg.com/responsive-web/client-web/main.{HASH}.js"></script>'
    assert q.bundle_hash(html) == HASH
    assert q.bundle_url(HASH) == f"https://abs.twimg.com/responsive-web/client-web/main.{HASH}.js"
    assert q.bundle_hash(html + html) == HASH
    assert q.bundle_hash(html + html.replace(HASH, "0123456789abcdef")) is None
    assert q.bundle_hash("<html></html>") is None
    assert q.bundle_hash('src="https://evil.example/responsive-web/client-web/main.' + HASH + '.js"') is None
    with pytest.raises(ValueError):
        q.bundle_url("../x")


def test_bundle_parse_exact_names_and_whole_set_rejection():
    good = bundle([("SearchTimeline", NEW), ("UserTweets", "D6z-FJI2pKuwEeYYxVIGbg"),
                   ("SearchTimelineV2", "Q" * 22), ("Other", "R" * 22)])
    assert q.parse_bundle(good) == {"SearchTimeline": NEW, "UserTweets": "D6z-FJI2pKuwEeYYxVIGbg"}
    assert q.parse_bundle(good + ";" + bundle([("SearchTimeline", "Z" * 22)])) is None  # conflicting
    assert q.parse_bundle(good + ";" + bundle([("SearchTimeline", NEW)])) is None  # duplicate
    assert q.parse_bundle(good + ";" + bundle([("TweetDetail", NEW)])) is None  # one id, two operations
    assert q.parse_bundle(bundle([("SearchTimeline", "bad id")])) is None
    assert q.parse_bundle(bundle([("UserTweets", "D6z-FJI2pKuwEeYYxVIGbg")])) is None  # tracked op absent


def test_check_ok_candidate_stale_and_failure_states_are_honest():
    state = q.initial_state()
    same = {"SearchTimeline": q.PINNED["SearchTimeline"], "UserTweets": "D6z-FJI2pKuwEeYYxVIGbg"}
    ok = q.apply_check(state, NOW, outcome="ok", mapping=same, sha256="a" * 64)
    assert ok["check_state"] == "ok" and ok["last_check"] == NOW.isoformat() and ok["bundle_sha256"] == "a" * 64
    assert ok["operations"]["UserTweets"]["observed"] == {"id": "D6z-FJI2pKuwEeYYxVIGbg", "seen_at": NOW.isoformat()}
    assert ok["operations"]["UserTweets"]["candidate"] is None  # ordinary operations are observation only
    assert q.active_id(ok, "UserTweets") == q.PINNED["UserTweets"]
    cand = q.apply_check(ok, NOW, outcome="ok", mapping={"SearchTimeline": NEW}, sha256="b" * 64)
    assert cand["check_state"] == "candidate" and q.active_id(cand, "SearchTimeline") == q.PINNED["SearchTimeline"]
    assert cand["operations"]["SearchTimeline"]["candidate"] == {"id": NEW, "seen_at": NOW.isoformat(),
                                                                 "rejected_until": None, "reason": None}
    later = q.apply_check(cand, NOW + timedelta(hours=4), outcome="ok", mapping={"SearchTimeline": NEW}, sha256="b" * 64)
    assert later["operations"]["SearchTimeline"]["candidate"]["seen_at"] == NOW.isoformat()
    rejected = json.loads(json.dumps(later))
    rejected["operations"]["SearchTimeline"]["candidate"].update(
        rejected_until=(NOW + timedelta(days=1)).isoformat(), reason="evaluation_failed")
    assert q.apply_check(rejected, NOW + timedelta(hours=5), outcome="ok", mapping={"SearchTimeline": NEW},
                         sha256="b" * 64)["check_state"] == "stale"
    for outcome, expected in (("blocked", "blocked"), ("malformed", "unknown"), ("refused_by_policy", "refused_by_policy")):
        failed = q.apply_check(cand, NOW, outcome=outcome)
        assert failed["check_state"] == expected and failed["operations"] == cand["operations"]
        assert failed["bundle_sha256"] == cand["bundle_sha256"]
    with pytest.raises(ValueError):
        q.apply_check(state, NOW, outcome="ok")
    assert state == q.initial_state()  # pure: inputs never mutated
