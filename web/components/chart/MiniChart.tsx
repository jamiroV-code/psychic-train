"use client";

import { useMemo, useRef } from "react";
import { SERIES } from "@/lib/chart-palette";
import type { ChartRange, SimpleLinesProps } from "@/lib/island-loader";
import { useSimpleLines } from "@/lib/use-simple-lines";
import type { ChartBar, Timeframe } from "@/lib/types/screener";

/**
 * The drill-down sparkline: close price with its SMA over the top.
 *
 * A Svelte/LayerChart island (ADR-1), like every other chart in the app. It
 * syncs with nothing and has no crosshair, so it takes no store — it is the
 * simplest use of the shared simple-lines island.
 *
 * T43 / S11b: mounted once per timeframe and height; new bars go to the
 * mounted chart in place, so its zoom survives a refresh. Unchanged bars
 * (the same arrays, kept by the board's structural sharing) touch nothing.
 */

export interface MiniChartProps {
  price: ChartBar[];
  sma: ChartBar[];
  height?: number;
  // T34 / S2: optional; when given the time axis is Brussels time for that timeframe.
  timeframe?: Timeframe;
  // T44: linked zoom (the board's small charts). Both or neither.
  range?: ChartRange | null;
  onRangeChange?: (range: ChartRange | null) => void;
}

function points(bars: ChartBar[]) {
  return bars.map((bar) => ({ timestamp: bar.timestamp, value: bar.close }));
}

export function MiniChart({ price, sma, height = 120, timeframe, range, onRangeChange }: MiniChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  const props = useMemo<SimpleLinesProps>(
    () => ({
      series: [
        { key: "price", color: SERIES.primary, width: 2, points: points(price) },
        { key: "sma", color: SERIES.secondary, width: 1, points: points(sma) },
      ],
      height,
      label: "Close price with its moving average",
      ...(timeframe ? { timeframe } : {}),
      ...(onRangeChange ? { linkedRange: range ?? null, onRangeChange } : {}),
    }),
    [price, sma, height, timeframe, range, onRangeChange],
  );

  useSimpleLines(containerRef, props, `${timeframe ?? ""}|${height}`);

  return <div ref={containerRef} data-testid="mini-chart" />;
}
