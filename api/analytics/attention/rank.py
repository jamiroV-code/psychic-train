"""Percentile of a ratio against the reference universe's ratios (D-3)."""
from __future__ import annotations


def percentile(value: float, refs: list[float]) -> float | None:
    """0-100; ties count half. `refs` is never modified: outside coins are placed, not added."""
    if not refs:
        return None
    below = sum(1 for r in refs if r < value)
    equal = sum(1 for r in refs if r == value)
    return (below + 0.5 * equal) / len(refs) * 100.0
