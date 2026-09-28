---
name: note:mapping-tripwire-gap
description: "Backlog: test_trigger_tripwire.py hashes trigger.py's whole file but only spot-checks mapping.py's frozen surface, and never touches map_coin_to_narrative_category at all"
date: 28-09-26
feature: narrative-mindshare
---

# mapping.py tripwire coverage gap (backlog note)

**TL;DR:** The RFC-7 tripwire test is a strong, whole-file guard for `trigger.py` but a weak,
partial guard for `mapping.py`. Today's git diff against the pre-plan base commit happens to prove
`mapping.py` is untouched, but the tripwire test itself would not catch a future accidental edit.
Found and recorded, not fixed, during the `narrative-v2_25-09-26` UPDATE PROCESS closeout (28-09-26,
2nd session).

## Finding

`api/tests/analytics/narrative/test_trigger_tripwire.py`:

- For `trigger.py`: SHA-256-hashes the whole file, and separately pins all 6 function signatures,
  module names, constants, and `TriggerResult` fields, plus the seed file name and seed ids. This is
  a strong, whole-file guard.
- For `mapping.py`: no file hash at all. Only checks `LEGACY_COIN_CATEGORY_MAP`'s value, that
  `COIN_CATEGORY_MAP` still points to it, and `map_coin_to_category`'s signature. It does **not**
  cover `map_coin_to_narrative_category` — which this plan's own Non-Goals section explicitly lists
  as frozen — at all.

Today's `git diff a86a2f05d0ab6c62f65aeafe12d92c34fa4eb4e0 HEAD -- api/analytics/narrative/mapping.py`
is empty, independently confirming `mapping.py` is byte-unchanged across all of narrative-v2's 7
RFCs plus this session's scale-drift fix — but that's a git-diff proof for TODAY only. The tripwire
test would not catch a future accidental edit to `map_coin_to_narrative_category` or any other part
of `mapping.py` the way it would immediately catch one in `trigger.py`.

## Why not fixed now

Strengthening the tripwire test (adding a file hash for `mapping.py`, adding coverage for
`map_coin_to_narrative_category`) is a real, scoped code change to a test file — doing it as a side
effect of this UPDATE PROCESS documentation/process closeout would be scope creep beyond what this
session was asked to do.

## Suggested follow-up (small, scoped fix)

- Extend `test_trigger_tripwire.py` (or add a sibling test) to SHA-256-hash `mapping.py` the same
  way `trigger.py` is hashed, and to pin `map_coin_to_narrative_category`'s signature alongside
  `map_coin_to_category`'s.
- Small, mechanical, low-risk — a good first-session task for whoever next touches
  `narrative-mindshare` test infra.
