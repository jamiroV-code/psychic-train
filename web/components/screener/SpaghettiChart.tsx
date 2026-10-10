"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useLiveData } from "@/components/screener/LiveProvider";
import type { SimpleLinesProps } from "@/lib/island-loader";
import { shareStructure, VOLATILE } from "@/lib/same-data";
import { useSimpleLines } from "@/lib/use-simple-lines";
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
  // T41 / S5b: given `hidden`, the toggles are controlled by the parent
  // (the saved layout); without it they stay in memory as before.
  hidden?: readonly string[];
  onToggle?: (symbol: string) => void;
  // A change refetches at once (a coin was added or removed).
  reloadToken?: number;
}

/**
 * T37 / S6: one plot with every watchlist coin as percent change from the
 * start of its own window, so every line starts at 0, plus BTC and HYPE as
 * thicker reference lines. Each legend entry toggles its line (in memory
 * only, unless the parent controls them: T41 / S5b). Line building and colours live in
 * lib/spaghetti-lines.ts, where they are unit-tested.
 *
 * T43 / S11b: refetches when the server's data changes (`dataVersion`),
 * keeps the last data and shows the error on a failure, and hands new lines
 * to the mounted chart in place (re-mounted only for a new timeframe).
 */
export function SpaghettiChart({
  timeframe,
  fetchSpaghetti = fetchSpaghettiDefault,
  hidden: controlled,
  onToggle,
  reloadToken = 0,
}: SpaghettiChartProps) {
  const [data, setData] = useState<SpaghettiResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [localHidden, setLocalHidden] = useState<ReadonlySet<string>>(() => new Set());
  // Keyed on the SORTED list: an equal list in any order keeps the same Set,
  // so `lines` and the island props stay and the chart is not touched.
  const controlledKey = controlled ? [...controlled].sort().join(",") : null;
  const controlledSet = useMemo<ReadonlySet<string> | null>(
    () => (controlledKey === null ? null : new Set(controlledKey ? controlledKey.split(",") : [])),
    [controlledKey],
  );
  const hidden = controlledSet ?? localHidden;
  const containerRef = useRef<HTMLDivElement>(null);

  const { dataVersion } = useLiveData();

  useEffect(() => {
    let cancelled = false;
    fetchSpaghetti(timeframe)
      .then((res) => {
        if (cancelled) return;
        setData((prev) => shareStructure(prev, res, VOLATILE));
        setError(null);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [timeframe, fetchSpaghetti, dataVersion, reloadToken]);

  const lines = useMemo(() => (data ? buildSpaghettiLines(data, hidden) : []), [data, hidden]);
  const legend = useMemo(() => (data ? spaghettiLegend(data) : []), [data]);
  const span = data ? spaghettiSpanText(data) : null;
  const chartTimeframe = data?.timeframe ?? timeframe;

  const islandProps = useMemo<SimpleLinesProps>(
    () => ({
      series: lines,
      height: 320,
      format: formatPercentChange,
      label: span ? `Percent change from the window start. ${span}` : "Percent change from the window start",
      timeframe: chartTimeframe,
      highlight: true,
    }),
    [lines, span, chartTimeframe],
  );
  useSimpleLines(containerRef, islandProps, chartTimeframe);

  const toggle = (symbol: string) => {
    onToggle?.(symbol);
    if (controlledSet) return;
    setLocalHidden((prev) => {
      const next = new Set(prev);
      if (next.has(symbol)) next.delete(symbol);
      else next.add(symbol);
      return next;
    });
  };

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
