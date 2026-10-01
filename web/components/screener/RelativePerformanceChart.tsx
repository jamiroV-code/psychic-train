"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { loadIslands } from "@/lib/island-loader";
import { buildRelativeLines, formatPercentChange } from "@/lib/relative-performance-lines";
import { DeadDataNotice } from "@/components/screener/DeadDataNotice";
import { fetchRelativePerformance } from "@/lib/api/screener";
import type { RelativePerformanceResponse, RelativePerformanceTimeframe } from "@/lib/types/screener";

const TIMEFRAME_OPTIONS: RelativePerformanceTimeframe[] = ["7d", "30d", "90d", "ytd"];
const TIMEFRAME_LABELS: Record<RelativePerformanceTimeframe, string> = {
  "7d": "7D",
  "30d": "30D",
  "90d": "90D",
  ytd: "YTD",
};

export interface RelativePerformanceChartProps {
  fetchData?: (timeframe: RelativePerformanceTimeframe) => Promise<RelativePerformanceResponse>;
  initialTimeframe?: RelativePerformanceTimeframe;
}

/**
 * Amendment 1 (SPEC US-8, AC-14/AC-15). This is the one deliberate exception
 * to the small-multiples pattern: a SINGLE plot (not one per coin), with one
 * line per available watchlist coin, all handed to one island mount. Line
 * building and colour assignment live in lib/relative-performance-lines.ts,
 * where they are unit-tested (the watchlist coins only, cycling the validated
 * categorical palette; the active benchmark is deliberately not plotted, per
 * SPEC Constraints, user-confirmed).
 */
export function RelativePerformanceChart({
  fetchData = fetchRelativePerformance,
  initialTimeframe = "30d",
}: RelativePerformanceChartProps) {
  const [timeframe, setTimeframe] = useState<RelativePerformanceTimeframe>(initialTimeframe);
  const [data, setData] = useState<RelativePerformanceResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    fetchData(timeframe)
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [timeframe, fetchData]);

  // One plot for the whole watchlist, not one per coin — the deliberate
  // exception to the small-multiples pattern (SPEC US-8, AC-14/AC-15). The
  // island takes every line at once, so that guard is now structural rather
  // than a rule about how many times createChart may be called.
  const lines = useMemo(() => buildRelativeLines(data?.series ?? []), [data]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let disposed = false;
    let dispose: (() => void) | undefined;

    loadIslands()
      .then((api) => {
        if (disposed) return;
        dispose = api.mountSimpleLines(container, {
          series: lines,
          height: 320,
          // `close` is the API's % change from the window start, so the axis
          // says so rather than showing a bare number.
          format: formatPercentChange,
          label: `Relative performance over ${TIMEFRAME_LABELS[timeframe]}`,
        });
      })
      .catch(() => {
        // The unavailable-coin notes still explain what is missing and why.
      });

    return () => {
      disposed = true;
      dispose?.();
    };
  }, [lines, timeframe]);

  const unavailableCoins = data?.series.filter((s) => !s.available) ?? [];

  return (
    <section data-testid="relative-performance-chart" aria-label="Relative performance">
      <div role="group" aria-label="Relative performance timeframe" data-testid="rp-timeframe-toggle">
        {TIMEFRAME_OPTIONS.map((tf) => (
          <button
            key={tf}
            type="button"
            data-testid={`rp-timeframe-button-${tf}`}
            aria-pressed={tf === timeframe}
            onClick={() => setTimeframe(tf)}
          >
            {TIMEFRAME_LABELS[tf]}
          </button>
        ))}
      </div>

      {error && <DeadDataNotice testId="rp-error" message={error} />}

      {/* Which line is which. Before the conversion each coin's symbol rode its
          own price-axis title; without this a multi-coin chart cannot be read.
          On the light strip, because the glyph colours are plot colours. */}
      {lines.length > 0 && (
        <div className="plot-legend" data-testid="rp-legend">
          {lines.map((l) => (
            <span key={l.key} data-testid={`rp-legend-${l.key}`}>
              <span className="legend-glyph" style={{ color: l.color }} aria-hidden="true">
                ―
              </span>{" "}
              <span className="plot-legend__label">{l.key}</span>
            </span>
          ))}
        </div>
      )}

      <div ref={containerRef} data-testid="rp-chart-container" />

      {unavailableCoins.length > 0 && (
        <div data-testid="rp-unavailable-note" className="relative-performance-chart__note">
          {unavailableCoins.map((s) => (
            <span key={s.symbol}>
              {s.symbol}:{" "}
              <DeadDataNotice testId={`rp-unavailable-${s.symbol}`} reason={s.reason} context="window" />
            </span>
          ))}
        </div>
      )}
    </section>
  );
}
