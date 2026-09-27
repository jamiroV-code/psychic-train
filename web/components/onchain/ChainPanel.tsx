"use client";

import { memo, useEffect, useMemo, useRef } from "react";
import { AreaSeries, createChart, createSeriesMarkers, LineSeries, type ISeriesApi } from "lightweight-charts";
import { RedistributionBadge } from "@/components/narrative/RedistributionBadge";
import { CrossCheckNote } from "@/components/onchain/CrossCheckNote";
import { FloorRampStateLabel } from "@/components/onchain/FloorRampStateLabel";
import { LimitedHistoryFlag } from "@/components/onchain/LimitedHistoryFlag";
import { SourceMethodBadge } from "@/components/onchain/SourceMethodBadge";
import type { ChartSync } from "@/lib/regime-chart-sync";
import { isoDateToUtcSeconds } from "@/lib/regime-chart-sync";
import { lineBreakIndices, toSegmentedSeriesData } from "@/lib/regime-line-segments";
import { INK, formatCount, staleDays, type PanelModel } from "@/lib/onchain-view-model";
import type { ChainGrowth } from "@/lib/types/onchain";

export interface ChainPanelProps {
  chain: ChainGrowth;
  model: PanelModel;
  gridDates: string[];
  gridTimes: number[];
  generatedUtc: string;
  sync: ChartSync | null;
  /** Shared hover index from the sync group; null = show the latest point. */
  hoverIndex: number | null;
  height?: number;
}

function withAlpha(hex: string, alpha: number): string {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}

function lastIndexWithValue(model: PanelModel): number | null {
  for (let i = model.value.length - 1; i >= 0; i--) {
    if (model.value[i] !== null || model.preLaunchValue[i] !== null) return i;
  }
  return null;
}

/**
 * One chain's raw panel: daily value (thin) + EMA28 (2px) in the chain's
 * colour on its own y-axis, pre-launch points as a muted shaded area (D2),
 * floor/ramp markers from the API, honest gaps (`gap_before`), and a hover
 * readout synced with the other panels. No value is computed here.
 */
function ChainPanelImpl({ chain, model, gridDates, gridTimes, generatedUtc, sync, hoverIndex, height = 180 }: ChainPanelProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const series = chain.series;
  const gapDates = useMemo(
    () => lineBreakIndices(model.value, model.gapBefore).map((i) => gridDates[i]),
    [model, gridDates]
  );

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const chart = createChart(container, {
      height,
      width: container.clientWidth,
      layout: { background: { color: "transparent" }, textColor: INK.muted },
      grid: { vertLines: { visible: false }, horzLines: { color: INK.gridline } },
      timeScale: { borderColor: INK.baseline },
      rightPriceScale: { borderVisible: false },
      crosshair: { horzLine: { visible: false, labelVisible: false } },
      localization: { priceFormatter: (p: number) => formatCount(p) },
    });

    if (model.hasPreLaunch) {
      const pre = chart.addSeries(AreaSeries, {
        lineColor: INK.preLaunch,
        topColor: INK.preLaunchFill,
        bottomColor: INK.preLaunchFill,
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
      pre.setData(toSegmentedSeriesData(gridTimes, model.preLaunchValue, model.gapBefore).line);
    }

    const raw: ISeriesApi<"Line"> = chart.addSeries(LineSeries, {
      color: withAlpha(model.color, 0.45),
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    const rawData = toSegmentedSeriesData(gridTimes, model.value, model.gapBefore);
    raw.setData(rawData.line);
    if (rawData.dots) {
      const dots = chart.addSeries(LineSeries, {
        color: model.color,
        lineVisible: false,
        pointMarkersVisible: true,
        pointMarkersRadius: 2,
        crosshairMarkerVisible: false,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      dots.setData(rawData.dots);
    }

    const ema = chart.addSeries(LineSeries, {
      color: model.color,
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    ema.setData(toSegmentedSeriesData(gridTimes, model.ema28, model.gapBefore).line);
    if (model.markers.length > 0) {
      createSeriesMarkers(
        ema,
        model.markers.map((m) => ({
          time: isoDateToUtcSeconds(m.date) as never,
          position: m.kind === "floor" ? ("belowBar" as const) : ("aboveBar" as const),
          shape: m.kind === "floor" ? ("arrowUp" as const) : ("circle" as const),
          color: INK.secondary,
          text: m.kind,
        }))
      );
    }

    const unregister = sync
      ? sync.register(chain.id, {
          chart,
          series: raw,
          element: container,
          valueAt: (i) => model.value[i] ?? model.preLaunchValue[i] ?? null,
        })
      : () => {};

    const handleResize = () => {
      if (containerRef.current) chart.applyOptions({ width: containerRef.current.clientWidth });
    };
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      unregister();
      chart.remove();
    };
  }, [chain.id, model, gridTimes, sync, height]);

  const readoutIndex = hoverIndex ?? lastIndexWithValue(model);
  const readoutRaw = readoutIndex === null ? null : model.value[readoutIndex] ?? model.preLaunchValue[readoutIndex];
  const isPreLaunch = readoutIndex !== null && model.preLaunchValue[readoutIndex] !== null;
  const days = chain.status === "stale" ? staleDays(series?.last_as_of_utc ?? null, generatedUtc) : null;

  return (
    <section
      data-testid={`onchain-panel-${chain.id}`}
      style={{ borderTop: `2px solid ${model.color}`, padding: "6px 0", minWidth: 0 }}
    >
      <div>
        <strong style={{ color: INK.primary }}>{chain.label}</strong>
        {chain.floor_ramp && <FloorRampStateLabel chainId={chain.id} state={chain.floor_ramp.state} />}
        {chain.status === "stale" && (
          <span
            data-testid={`onchain-panel-${chain.id}-stale`}
            style={{ fontSize: 11, color: INK.primary, border: "1px solid #fab219", borderRadius: 3, padding: "0 4px", marginLeft: 6 }}
          >
            ⚠ Stale — last updated {days === null ? "an unknown number of" : days} day{days === 1 ? "" : "s"} ago
          </span>
        )}
        {series && (
          <RedistributionBadge redistributable={series.redistributable} testId={`onchain-panel-${chain.id}-redistribution`} />
        )}
      </div>
      {series && <SourceMethodBadge chainId={chain.id} source={series.source} method={series.method} />}
      <LimitedHistoryFlag chain={chain} />
      <div style={{ fontSize: 11, color: INK.secondary }}>
        <span style={{ color: model.color }}>―</span> 28-day EMA{"  "}
        <span style={{ color: withAlpha(model.color, 0.45) }}>―</span> daily value
        {model.hasPreLaunch && chain.launch_date && (
          <span data-testid={`onchain-panel-${chain.id}-prelaunch`}>
            {"  "}
            <span style={{ color: INK.preLaunch }}>▇</span> before launch ({chain.launch_date}), not used in analytics
          </span>
        )}
        {model.markers.length > 0 && <span>{"  "}▲ floor · ● ramp</span>}
      </div>
      <div
        ref={containerRef}
        data-testid={`onchain-chart-${chain.id}`}
        data-gap-count={gapDates.length}
        data-gap-dates={gapDates.join(",")}
        data-marker-count={model.markers.length}
      />
      <div data-testid={`onchain-panel-${chain.id}-readout`} style={{ fontSize: 12, color: INK.secondary }}>
        {readoutIndex === null ? (
          "No data"
        ) : (
          <>
            <strong style={{ color: INK.primary }}>{formatCount(readoutRaw ?? null)}</strong> on {gridDates[readoutIndex]}
            {isPreLaunch
              ? " (before launch)"
              : ` · EMA7 ${formatCount(model.ema7[readoutIndex])} · EMA28 ${formatCount(model.ema28[readoutIndex])}`}
          </>
        )}
      </div>
      <CrossCheckNote chainId={chain.id} check={chain.cross_check} />
    </section>
  );
}

export const ChainPanel = memo(ChainPanelImpl);
