"use client";

import { useEffect, useRef } from "react";
import { createChart, LineSeries, type IChartApi, type ISeriesApi, type UTCTimestamp } from "lightweight-charts";
import type { ChartBar } from "@/lib/types/screener";

// lightweight-charts v5: `createChart(container, options)` returns an
// independent `IChartApi`; series are added via `chart.addSeries(LineSeries,
// options)` (v4's `addLineSeries` was removed in v5). One `createChart`
// instance per panel, disposed via `chart.remove()` on unmount — confirmed
// v5 pattern (Component Details, PLAN.md RFC-001 Stage 0).

function toLineData(bars: ChartBar[]) {
  return bars.map((bar) => ({
    time: Math.floor(new Date(bar.timestamp).getTime() / 1000) as UTCTimestamp,
    value: bar.close,
  }));
}

export interface MiniChartProps {
  price: ChartBar[];
  sma: ChartBar[];
  height?: number;
}

export function MiniChart({ price, sma, height = 120 }: MiniChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const priceSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const smaSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);

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
      handleScroll: false,
      handleScale: false,
    });
    chartRef.current = chart;
    priceSeriesRef.current = chart.addSeries(LineSeries, { color: "#2962ff", lineWidth: 2 });
    smaSeriesRef.current = chart.addSeries(LineSeries, { color: "#ff9800", lineWidth: 1 });

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
      chartRef.current = null;
      priceSeriesRef.current = null;
      smaSeriesRef.current = null;
    };
  }, [height]);

  useEffect(() => {
    priceSeriesRef.current?.setData(toLineData(price));
  }, [price]);

  useEffect(() => {
    smaSeriesRef.current?.setData(toLineData(sma));
  }, [sma]);

  return <div ref={containerRef} data-testid="mini-chart" />;
}
