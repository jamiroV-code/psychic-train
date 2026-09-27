"use client";

import { useEffect, useRef } from "react";
import { createChart, LineSeries } from "lightweight-charts";
import type { SpreadPoint } from "@/lib/types/pairs";

/**
 * One line series over the API's `spread[]` (RFC-004, Stage 0 decision 5:
 * spread only). Points are passed through unchanged — dates as ISO
 * business-day strings, values as sent.
 */
export function SpreadChart({ points, height = 260 }: { points: SpreadPoint[]; height?: number }) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const chart = createChart(container, {
      height,
      width: container.clientWidth,
      layout: { background: { color: "transparent" }, textColor: "#8a8f98" },
      grid: { vertLines: { visible: false }, horzLines: { visible: false } },
      timeScale: { borderVisible: false },
      rightPriceScale: { borderVisible: false },
    });
    const series = chart.addSeries(LineSeries, {
      color: "#2962ff",
      lineWidth: 2,
      priceLineVisible: false,
    });
    series.setData(points.map((p) => ({ time: p.date, value: p.spread })));
    chart.timeScale().fitContent();

    const handleResize = () => {
      if (containerRef.current) chart.applyOptions({ width: containerRef.current.clientWidth });
    };
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [points, height]);

  return <div data-testid="pairs-spread-chart" ref={containerRef} style={{ width: "100%" }} />;
}
