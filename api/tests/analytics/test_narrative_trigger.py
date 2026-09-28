"""Fork B narrative trigger/confirmation tests (items 51-53, 47a).

`test_unconfirmed_candidate_still_visible` is the Risk-#2 hard gate;
`test_trigger_degrades_with_reduced_sources` and
`test_presumed_dead_pytrends_caps_trust_even_with_other_sources_healthy`
are the Risk-#4 / item 47a gates; the `TestPytrendsStaleness` class is
item 47a's staleness test, mirroring RFC-002's LiqTide staleness gate
(item 30) but at the adapter level (`pytrends_adapter.fetch_trend`).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from api.analytics.narrative import trigger
from api.data import cache, coingecko_adapter, pytrends_adapter, reddit_adapter


def _flat_series(n: int = 30, value: float = 0.5) -> pd.Series:
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    return pd.Series(value, index=dates)


def _spiking_series(n: int = 30, spike_at: int = 25, base: float = 0.3, spike_value: float = 0.9) -> pd.Series:
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    vals = np.full(n, base)
    vals[spike_at:] = spike_value
    return pd.Series(vals, index=dates)


_HEALTHY_STATUS = {"pytrends": "ok", "reddit": "ok", "coingecko": "ok"}


class TestComputeTrigger:
    def test_flat_series_produces_no_trigger(self):
        flat = _flat_series()
        result = trigger.compute_trigger("ai", {"pytrends": flat, "reddit": flat, "coingecko": flat}, _HEALTHY_STATUS)
        assert result.triggered is False
        assert result.trust_weight == 0.0

    def test_zero_available_sources_returns_untriggered_not_a_crash(self):
        result = trigger.compute_trigger(
            "ai",
            {"pytrends": None, "reddit": None, "coingecko": None},
            {"pytrends": "unavailable", "reddit": "unavailable", "coingecko": "unavailable"},
        )
        assert result.triggered is False
        assert result.trust_weight == 0.0

    def test_unconfirmed_candidate_still_visible(self):
        """Risk-#2 hard gate: a triggered-but-unconfirmed category is
        returned with triggered=True (never suppressed) and a nonzero
        trust_weight — ADR-3's "confirmation never collapses into silence"
        applies to narrative candidates exactly as it does to leg
        boundaries.
        """
        spiking = _spiking_series()
        result = trigger.compute_trigger(
            "ai", {"pytrends": spiking, "reddit": spiking, "coingecko": spiking}, _HEALTHY_STATUS
        )
        assert result.triggered is True
        assert result.confirmed is False
        assert result.trigger_date is not None
        assert result.trust_weight > 0.0

    def test_trigger_degrades_with_reduced_sources(self):
        """Risk-#4 / item 47a: trigger still fires on the remaining
        sources when one is entirely unavailable, but trust_weight is
        visibly capped, never computed as if all sources were healthy.
        """
        spiking = _spiking_series()
        result = trigger.compute_trigger(
            "ai",
            {"pytrends": None, "reddit": spiking, "coingecko": spiking},
            {"pytrends": "unavailable", "reddit": "ok", "coingecko": "ok"},
        )
        assert result.triggered is True
        assert result.trust_weight <= trigger.REDUCED_SOURCE_TRUST_CAP
        assert result.trust_weight > 0.0  # degraded, never a silent zero/neutral drop

    def test_presumed_dead_pytrends_caps_trust_even_with_other_sources_healthy(self):
        spiking = _spiking_series()
        result = trigger.compute_trigger(
            "ai",
            {"pytrends": None, "reddit": spiking, "coingecko": spiking},
            {"pytrends": "presumed-dead", "reddit": "ok", "coingecko": "ok"},
        )
        assert result.triggered is True
        assert result.trust_weight <= trigger.REDUCED_SOURCE_TRUST_CAP


class TestApplyConfirmation:
    def _base_state(self, **overrides) -> trigger.TriggerResult:
        defaults = dict(
            category_id="ai", triggered=True, confirmed=False, trust_weight=trigger.BASE_TRUST_WEIGHT,
            trigger_date="2024-06-01", confirmed_date=None, source_availability=_HEALTHY_STATUS,
        )
        defaults.update(overrides)
        return trigger.TriggerResult(**defaults)

    def test_explicit_user_action_confirms_immediately(self):
        state = self._base_state()
        result = trigger.apply_confirmation(state, as_of="2024-06-02", user_action=True)
        assert result.confirmed is True
        assert result.confirmed_date == "2024-06-02"
        assert result.trust_weight == trigger.CONFIRMED_TRUST_WEIGHT

    def test_sustained_duration_confirms_without_user_action(self):
        state = self._base_state()
        result = trigger.apply_confirmation(state, as_of="2024-06-11")  # 10 days after trigger_date
        assert result.confirmed is True

    def test_insufficient_duration_does_not_confirm_but_stays_fully_visible(self):
        state = self._base_state()
        result = trigger.apply_confirmation(state, as_of="2024-06-05")
        assert result.confirmed is False
        # ADR-3: still fully visible, not hidden or nulled out.
        assert result.triggered is True
        assert result.trust_weight == trigger.BASE_TRUST_WEIGHT

    def test_reduced_confidence_trigger_stays_capped_even_once_confirmed(self):
        state = self._base_state(
            trust_weight=trigger.REDUCED_SOURCE_TRUST_CAP,
            source_availability={"pytrends": "presumed-dead", "reddit": "ok", "coingecko": "ok"},
        )
        result = trigger.apply_confirmation(state, as_of="2024-06-11")
        assert result.confirmed is True
        # Confirmation cannot launder a partial-source reading into full confidence.
        assert result.trust_weight == trigger.REDUCED_SOURCE_TRUST_CAP

    def test_untriggered_state_is_a_noop(self):
        state = self._base_state(triggered=False, trigger_date=None, trust_weight=0.0)
        result = trigger.apply_confirmation(state, as_of="2024-06-11")
        assert result.confirmed is False
        assert result.confirmed_date is None


class TestPytrendsStaleness:
    """Item 47a: mirrors RFC-002's LiqTide staleness test (item 30) — a
    `presumed-dead` pytrends record is never treated as a fresh reading.

    SANDBOX NOTE: monkeypatches `cache.read_narrative_series`/
    `write_narrative_point` directly rather than exercising the real
    DuckDB-backed cache functions through a `CACHE_ROOT` tmp_path (as
    `test_adapter_contracts.py` does) — same "monkeypatch at the
    adapter-call boundary instead" technique RFC-002's tests use throughout
    this session (see EXECUTE Deviations), since real DuckDB is not
    installable in this sandbox.
    """

    def test_transient_failure_returns_unavailable_not_a_stale_value(self, monkeypatch):
        recent_date = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d")
        fake_history = pd.DataFrame(
            [{"date": recent_date, "raw_value": 42.0, "normalized_value": None, "source_status": "fresh"}]
        )
        monkeypatch.setattr(pytrends_adapter.cache, "read_narrative_series", lambda source, category: fake_history)
        monkeypatch.setattr(pytrends_adapter, "_fetch_live", lambda keyword: (None, None))

        result = pytrends_adapter.fetch_trend("ai crypto")
        assert result.status == "unavailable"
        assert result.value is None  # never silently serves the 2-day-old value as current

    def test_sustained_failure_past_threshold_flags_presumed_dead(self, monkeypatch):
        old_date = (
            datetime.now(timezone.utc) - timedelta(days=pytrends_adapter.PYTRENDS_DEAD_THRESHOLD_DAYS + 1)
        ).strftime("%Y-%m-%d")
        fake_history = pd.DataFrame(
            [{"date": old_date, "raw_value": 42.0, "normalized_value": None, "source_status": "fresh"}]
        )
        monkeypatch.setattr(pytrends_adapter.cache, "read_narrative_series", lambda source, category: fake_history)
        monkeypatch.setattr(pytrends_adapter, "_fetch_live", lambda keyword: (None, None))

        result = pytrends_adapter.fetch_trend("ai crypto")
        assert result.status == "presumed-dead"
        assert result.value is None  # a presumed-dead record is never treated as a fresh reading

    def test_no_cache_at_all_is_plain_unavailable_not_presumed_dead(self, monkeypatch):
        monkeypatch.setattr(pytrends_adapter.cache, "read_narrative_series", lambda source, category: pd.DataFrame())
        monkeypatch.setattr(pytrends_adapter, "_fetch_live", lambda keyword: (None, None))
        result = pytrends_adapter.fetch_trend("never seen before")
        assert result.status == "unavailable"

    def test_successful_live_fetch_returns_ok_and_archives(self, monkeypatch):
        written: dict = {}
        monkeypatch.setattr(
            pytrends_adapter.cache,
            "write_narrative_point",
            lambda source, category, date, value, **kw: written.update(
                source=source, category=category, date=date, value=value
            ),
        )
        monkeypatch.setattr(pytrends_adapter, "_fetch_live", lambda keyword: (77.0, "2024-06-01"))
        result = pytrends_adapter.fetch_trend("ai crypto")
        assert result.status == "ok"
        assert result.value == 77.0
        assert written["value"] == 77.0


class TestHistoryKeying:
    """pytrends/reddit history is archived under the search keyword
    (`keywords[0]`), not the category id — `compute_narrative_categories`
    must read it back under that same key. Real cache writers/readers under
    `isolated_cache`; `cache.read_narrative_series` is deliberately NOT
    stubbed (stubbing the read is what originally hid this bug).
    """

    AS_OF = "2024-06-30"
    DECOY_DATE = "2024-05-01"

    def _stub_fetchers(self, monkeypatch):
        monkeypatch.setattr(
            coingecko_adapter, "fetch_trending",
            lambda *a, **k: coingecko_adapter.TrendingResult(symbols=[], as_of=None, status="unavailable"),
        )
        monkeypatch.setattr(
            pytrends_adapter, "fetch_trend",
            lambda kw: pytrends_adapter.TrendResult(keyword=kw, value=None, as_of=None, status="ok"),
        )
        monkeypatch.setattr(
            reddit_adapter, "fetch_mentions",
            lambda q, *a, **k: reddit_adapter.MentionResult(query=q, mention_count=None, as_of=None, status="ok"),
        )

    def _spy_series(self, monkeypatch) -> dict[str, dict]:
        seen: dict[str, dict] = {}
        real = trigger.compute_trigger

        def spy(category_id, series_by_source, source_status):
            seen[category_id] = dict(series_by_source)
            return real(category_id, series_by_source, source_status)

        monkeypatch.setattr(trigger, "compute_trigger", spy)
        return seen

    def _ai_keyword(self) -> str:
        return next(c for c in trigger.load_seed_categories() if c["id"] == "ai")["keywords"][0]

    def test_keyword_keyed_rows_seen_and_category_id_decoy_ignored(self, isolated_cache, monkeypatch):
        keyword = self._ai_keyword()
        start = datetime.fromisoformat(self.AS_OF) - timedelta(days=20)
        for i in range(20):
            d = (start + timedelta(days=i)).strftime("%Y-%m-%d")
            spike = 18.0 if i >= 16 else 0.0
            cache.write_narrative_point("pytrends", keyword, d, 10.0 + (i % 3) + spike)
            cache.write_narrative_point("reddit", keyword, d, 5.0 + (i % 2) + spike / 3)
        cache.write_narrative_point("pytrends", "ai", self.DECOY_DATE, 999.0)  # wrong key: must be ignored
        cache.write_narrative_point("reddit", "ai", self.DECOY_DATE, 999.0)

        self._stub_fetchers(monkeypatch)
        seen = self._spy_series(monkeypatch)
        result = next(r for r in trigger.compute_narrative_categories(as_of=self.AS_OF) if r.category_id == "ai")

        ai = seen["ai"]
        assert ai["coingecko"] is None
        for source in ("pytrends", "reddit"):
            series = ai[source]
            assert series is not None and len(series) == 20
            assert pd.Timestamp(self.DECOY_DATE) not in series.index
        assert sum(s is not None for s in ai.values()) == 2  # n_available
        assert result.triggered is True
        assert result.trust_weight == trigger.BASE_TRUST_WEIGHT

    def test_only_category_id_keyed_rows_are_not_read(self, isolated_cache, monkeypatch):
        for i in range(20):
            d = (datetime.fromisoformat(self.AS_OF) - timedelta(days=20 - i)).strftime("%Y-%m-%d")
            cache.write_narrative_point("pytrends", "ai", d, 10.0 + i * i)
            cache.write_narrative_point("reddit", "ai", d, 5.0 + i * i)

        self._stub_fetchers(monkeypatch)
        seen = self._spy_series(monkeypatch)
        result = next(r for r in trigger.compute_narrative_categories(as_of=self.AS_OF) if r.category_id == "ai")

        assert all(s is None for s in seen["ai"].values())
        assert result.triggered is False
        assert result.trust_weight == 0.0

    def test_coingecko_still_read_by_category_id(self, isolated_cache, monkeypatch):
        cache.write_narrative_point("coingecko", "ai", self.DECOY_DATE, 3.0)
        cache.write_narrative_point("coingecko", self._ai_keyword(), self.DECOY_DATE, 7.0)  # wrong key for coingecko

        self._stub_fetchers(monkeypatch)
        seen = self._spy_series(monkeypatch)
        trigger.compute_narrative_categories(as_of=self.AS_OF)

        cg = seen["ai"]["coingecko"]
        assert cg is not None and len(cg) == 1
