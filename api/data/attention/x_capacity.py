"""Collector identity pool, Part A (SPEC AC5): can the X accounts finish the day's coin-days? Pure arithmetic over
numbers the X stream already holds; no network, no X library, no file access.

- per-unit reads: the pages a unit needs for the sample size, at most the page cap, times the page size;
- capacity: the smaller of the global budget's room and the remaining per-account caps (no cap: the room);
- need: the target day's queued coin-days times the per-unit reads plus the pending canary pages;
- the older backlog is reported on its own (it is read only after the target day).
"""
from __future__ import annotations

import math


def per_unit_reads(*, sample_n: int, page_cap: int, page_size: int) -> int:
    return min(page_cap, max(1, math.ceil(sample_n / page_size))) * page_size


def sizing(*, global_room: int, remaining_caps: int | None, queued_target: int, backlog: int, per_unit: int,
           canary_pages: int, page_size: int) -> dict:
    capacity = max(0, global_room if remaining_caps is None else min(global_room, remaining_caps))
    need = queued_target * per_unit + canary_pages * page_size
    return {"capacity_reads": capacity, "need_reads": need, "shortfall_reads": max(0, need - capacity),
            "backlog_reads": backlog * per_unit}
