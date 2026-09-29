import { visibleRangeAttribute } from "../lib/regime-chart-sync";

/**
 * Shared state for the seven synced /regime panels.
 *
 * The panels are interleaved with React-owned chrome (header, meta, notices,
 * drill-down), so each plot is mounted as its own island. An island boundary
 * must never bisect coupled state, so the coupling lives here instead: one
 * store, created once by React and handed to every panel mount. The panels
 * do not talk to each other at all — they read the same range and the same
 * hover index, so "sync" is just shared state rather than a fan-out.
 *
 * That is the whole reason this file is ~80 lines where lib/regime-chart-sync.ts
 * is 184: lightweight-charts is imperative, so it needs a registration fan-out
 * and re-entrancy guards to stop panels echoing changes at each other. Nothing
 * echoes here, so there is nothing to guard.
 *
 * The range is kept in LOGICAL grid indices, not dates, because that is the
 * existing observable contract: every panel is fed the same grid, so index i
 * means the same date everywhere, and panels starting on different dates still
 * line up. `data-visible-range` is written through the very same
 * `visibleRangeAttribute` the lightweight-charts path uses, so the attribute
 * an end-to-end test reads is byte-identical between the two implementations.
 */
export function createRegimeChartSync({ gridDates, gridTimes, initialRange, onHover }) {
  const lastIndex = Math.max(0, gridDates.length - 1);

  const state = $state({
    from: initialRange ? initialRange.from : 0,
    to: initialRange ? initialRange.to : lastIndex,
    hoverIndex: null,
  });

  /** Panel host elements that carry `data-visible-range`. */
  const elements = new Map();

  function markAll() {
    const attr = visibleRangeAttribute(gridTimes, { from: state.from, to: state.to });
    for (const el of elements.values()) el.setAttribute("data-visible-range", attr);
  }

  function setRange(from, to) {
    // Never invert, and never zoom past a couple of bars.
    if (!(Number.isFinite(from) && Number.isFinite(to)) || to - from < 2) return;
    state.from = from;
    state.to = to;
    markAll();
  }

  return {
    state,

    registerElement(id, el) {
      elements.set(id, el);
      el.setAttribute("data-visible-range", visibleRangeAttribute(gridTimes, { from: state.from, to: state.to }));
      return () => elements.delete(id);
    },

    /**
     * Wheel zoom, anchored on the pointer so the date under the cursor stays
     * put — the behaviour lightweight-charts gave for free.
     * `fraction` is the pointer's position across the plot area, 0..1.
     */
    zoomAt(fraction, deltaY) {
      const span = state.to - state.from;
      const factor = deltaY < 0 ? 0.8 : 1.25;
      const nextSpan = span * factor;
      if (nextSpan < 2) return;
      const anchor = state.from + span * fraction;
      setRange(anchor - nextSpan * fraction, anchor + nextSpan * (1 - fraction));
    },

    setHover(index) {
      state.hoverIndex = index;
      onHover?.(index);
    },

    /** The grid indices currently in view, clamped to the real grid. */
    visibleBounds() {
      return {
        lo: Math.max(0, Math.floor(state.from)),
        hi: Math.min(lastIndex, Math.ceil(state.to)),
      };
    },
  };
}
