"use client";

import { useEffect, useRef, useState } from "react";
import { createChart, LineSeries, type IChartApi, type ISeriesApi, type UTCTimestamp } from "lightweight-charts";
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

// Watchlist-coins-only palette — cycled by index. The active benchmark is
// deliberately not plotted on this chart (SPEC Constraints, user-confirmed).
const PALETTE = ["#2962ff", "#ff9800", "#26a69a", "#ef5350", "#ab47bc", "#8d6e63", "#26c6da", "#9ccc65"];

export interface RelativePerformanceChartProps {
  fetchData?: (timeframe: RelativePerformanceTimeframe) => Promise<RelativePerformanceResponse>;
  initialTimeframe?: RelativePerformanceTimeframe;
}

/**
 * Amendment 1 (SPEC US-8, AC-14/AC-15). This is the one deliberate exception
 * to the small-multiples pattern: a SINGLE `createChart` instance (not one
 * per coin), with one line series per watchlist coin added via
 * `chart.addSeries(LineSeries, ...)` on that same instance (v5's confirmed
 * multi-series-on-one-instance API — re-confirmed here per the VALIDATE
 * finding on item 29d, distinct from `MiniChart`'s one-instance-per-panel
 * pattern).
 */
export function RelativePerformanceChart({
  fetchData = fetchRelativePerformance,
  initialTimeframe = "30d",
}: RelativePerformanceChartProps) {
  const [timeframe, setTimeframe] = useState<RelativePerformanceTimeframe>(initialTimeframe);
  const [data, setData] = useState<RelativePerformanceResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<Map<string, ISeriesApi<"Line">>>(new Map());

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

  // Exactly one createChart call per mount, regardless of watchlist size
  // (the mechanical guard from item 29d).
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const chart = createChart(container, {
      height: 320,
      width: container.clientWidth,
      layout: { background: { color: "transparent" }, textColor: "#8a8f98" },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
    });
    chartRef.current = chart;

    const handleResize = () => {
      if (containerRef.current) chart.applyOptions({ width: containerRef.current.clientWidth });
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
      chartRef.current = null;
      seriesRef.current.clear();
    };
  }, []);

  // One line series per available coin, added to the single shared instance.
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !data) return;

    for (const series of seriesRef.current.values()) {
      chart.removeSeries(series);
    }
    seriesRef.current.clear();

    data.series
      .filter((s) => s.available)
      .forEach((s, idx) => {
        const line = chart.addSeries(LineSeries, {
          color: PALETTE[idx % PALETTE.length],
          lineWidth: 2,
          title: s.symbol,
        });
        line.setData(
          s.points.map((p) => ({
            time: Math.floor(new Date(p.timestamp).getTime() / 1000) as UTCTimestamp,
            value: p.close,
          }))
        );
        seriesRef.current.set(s.symbol, line);
      });
  }, [data]);

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
