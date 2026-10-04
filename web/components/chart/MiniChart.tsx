"use client";

import { useEffect, useRef } from "react";
import { loadIslands } from "@/lib/island-loader";
import { SERIES } from "@/lib/chart-palette";
import type { ChartBar, Timeframe } from "@/lib/types/screener";

/**
 * The drill-down sparkline: close price with its SMA over the top.
 *
 * A Svelte/LayerChart island (ADR-1), like every other chart in the app. It
 * syncs with nothing and has no crosshair, so it takes no store — it is the
 * simplest use of the shared simple-lines island.
 */

export interface MiniChartProps {
  price: ChartBar[];
  sma: ChartBar[];
  height?: number;
  // T34 / S2: optional; when given the time axis is UTC for that timeframe.
  timeframe?: Timeframe;
}

function points(bars: ChartBar[]) {
  return bars.map((bar) => ({ timestamp: bar.timestamp, value: bar.close }));
}

export function MiniChart({ price, sma, height = 120, timeframe }: MiniChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let disposed = false;
    let dispose: (() => void) | undefined;

    loadIslands()
      .then((api) => {
        if (disposed) return;
        dispose = api.mountSimpleLines(container, {
          series: [
            { key: "price", color: SERIES.primary, width: 2, points: points(price) },
            { key: "sma", color: SERIES.secondary, width: 1, points: points(sma) },
          ],
          height,
          label: "Close price with its moving average",
          ...(timeframe ? { timeframe } : {}),
        });
      })
      .catch(() => {
        // The drill-down's numbers are all in the surrounding markup, so a
        // chart that cannot load stays silent rather than breaking the view.
      });

    return () => {
      disposed = true;
      dispose?.();
    };
  }, [price, sma, height, timeframe]);

  return <div ref={containerRef} data-testid="mini-chart" />;
}
