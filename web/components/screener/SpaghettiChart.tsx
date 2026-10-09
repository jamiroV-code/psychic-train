"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { loadIslands } from "@/lib/island-loader";
import {
  buildSpaghettiLines,
  formatPercentChange,
  spaghettiLegend,
  spaghettiSpanText,
} from "@/lib/spaghetti-lines";
import { DeadDataNotice } from "@/components/screener/DeadDataNotice";
import { fetchSpaghetti as fetchSpaghettiDefault } from "@/lib/api/screener";
import type { SpaghettiResponse, Timeframe } from "@/lib/types/screener";

export interface SpaghettiChartProps {
  /** The board's timeframe; the chart follows it and has no control of its own. */
  timeframe: Timeframe;
  // Injectable for tests; defaults to the real API client.
  fetchSpaghetti?: (timeframe: Timeframe) => Promise<SpaghettiResponse>;
}

/**
 * T37 / S6: one plot with every watchlist coin as percent change from the
 * start of its own window, so every line starts at 0, plus BTC and HYPE as
 * thicker reference lines. Each legend entry toggles its line (in memory
 * only; persistence is a later slice). Line building and colours live in
 * lib/spaghetti-lines.ts, where they are unit-tested.
 */
export function SpaghettiChart({ timeframe, fetchSpaghetti = fetchSpaghettiDefault }: SpaghettiChartProps) {
  const [data, setData] = useState<SpaghettiResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [hidden, setHidden] = useState<ReadonlySet<string>>(() => new Set());
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    fetchSpaghetti(timeframe)
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [timeframe, fetchSpaghetti]);

  const lines = useMemo(() => (data ? buildSpaghettiLines(data, hidden) : []), [data, hidden]);
  const legend = useMemo(() => (data ? spaghettiLegend(data) : []), [data]);
  const span = data ? spaghettiSpanText(data) : null;
  const chartTimeframe = data?.timeframe ?? timeframe;

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
          format: formatPercentChange,
          label: span ? `Percent change from the window start. ${span}` : "Percent change from the window start",
          timeframe: chartTimeframe,
          highlight: true,
        });
      })
      .catch(() => {
        // The legend and the per-coin notes still say what is there and what is not.
      });

    return () => {
      disposed = true;
      dispose?.();
    };
  }, [lines, span, chartTimeframe]);

  const toggle = (symbol: string) =>
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(symbol)) next.delete(symbol);
      else next.add(symbol);
      return next;
    });

  const available = legend.filter((e) => e.available);
  const unavailable = legend.filter((e) => !e.available);

  return (
    <section data-testid="spaghetti-chart" aria-label="Percent change from the window start" className="spaghetti-chart">
      {span && (
        <p data-testid="spaghetti-span" className="spaghetti-chart__span">
          {span}
        </p>
      )}

      {error && <DeadDataNotice testId="spaghetti-error" message={error} />}

      {/* Which line is which, and a switch for each. On the light strip
          because the glyph colours are plot colours. */}
      {available.length > 0 && (
        <div className="plot-legend" data-testid="spaghetti-legend" role="group" aria-label="Lines shown">
          {available.map((e) => (
            <button
              key={e.symbol}
              type="button"
              className="spaghetti-chart__toggle"
              data-testid={`spaghetti-toggle-${e.symbol}`}
              data-reference={e.reference ? "true" : undefined}
              aria-pressed={!hidden.has(e.symbol)}
              onClick={() => toggle(e.symbol)}
            >
              <span className="legend-glyph" style={{ color: e.color }} aria-hidden="true">
                {e.reference ? "▬" : "―"}
              </span>{" "}
              <span className="plot-legend__label">{e.symbol}</span>
            </button>
          ))}
        </div>
      )}

      <div ref={containerRef} data-testid="spaghetti-chart-container" />

      {unavailable.length > 0 && (
        <div className="spaghetti-chart__note">
          {unavailable.map((e) => (
            <span key={e.symbol} data-testid={`spaghetti-note-${e.symbol}`}>
              {e.symbol}: <DeadDataNotice testId={`spaghetti-reason-${e.symbol}`} reason={e.reason} context="window" />
            </span>
          ))}
        </div>
      )}
    </section>
  );
}
