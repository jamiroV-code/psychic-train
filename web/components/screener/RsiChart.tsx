"use client";

import { useMemo, useRef } from "react";
import { SERIES } from "@/lib/chart-palette";
import type { SimpleLinesProps } from "@/lib/island-loader";
import { useSimpleLines } from "@/lib/use-simple-lines";
import type { RsiPoint, Timeframe } from "@/lib/types/screener";

export interface RsiChartProps {
  points: RsiPoint[];
  timeframe: Timeframe;
  height?: number;
}

function formatValue(v: number): string {
  return v.toFixed(1);
}

/**
 * T41 / S5b: the drill-down's RSI 14 line, one series on the shared
 * simple-lines island. Mounted once per timeframe; new points (a live
 * refresh) go to the mounted chart in place, so it keeps its own zoom. It
 * zooms on its own, not with the price chart above it. The parent mounts it
 * only for a non-empty series.
 */
export function RsiChart({ points, timeframe, height = 120 }: RsiChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  const props = useMemo<SimpleLinesProps>(
    () => ({
      series: [{ key: "rsi", color: SERIES.indigo, width: 1.5, points }],
      height,
      format: formatValue,
      label: `RSI 14 (${timeframe})`,
      timeframe,
    }),
    [points, height, timeframe],
  );

  useSimpleLines(containerRef, props, `${timeframe}|${height}`);

  return <div ref={containerRef} data-testid="drilldown-rsi-chart" className="drilldown-view__rsi-chart" />;
}
