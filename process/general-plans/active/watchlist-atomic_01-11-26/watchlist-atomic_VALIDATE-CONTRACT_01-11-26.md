# watchlist-atomic — validate contract (direct lane)
Gates:
1. Red test committed first: mid-write failure (json.dump / os.replace raising) leaves previous watchlist.json byte-identical, no stray temp file.
2. Successful save is byte-identical to pre-change format (indent=2, trailing newline, key order).
3. Behaviours kept: parent dir created; missing file -> {'coins': []}; NO example-file fallback; cap + 409 untouched.
4. cache.py untouched (PR #213 owns it); cache._atomic_write_json uses compact separators, so a local temp+fsync+os.replace helper is used.
5. pytest: api/tests/data + watchlist-importing tests green except known host failures; Linux CI green on draft PR.
Out of scope: pairs_response spreads.tmp, lse_adapter (follow-ups after #213).
