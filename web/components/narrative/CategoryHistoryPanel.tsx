"use client";

import { memo, useEffect, useMemo, useRef } from "react";
import { createChart, LineSeries, type UTCTimestamp } from "lightweight-charts";
import { DeadDataNotice } from "@/components/screener/DeadDataNotice";
import { RedistributionBadge } from "@/components/narrative/RedistributionBadge";
import { formatNarrativeReason } from "@/lib/format-unavailable-reason";
import { buildPanelAxis, isPlottedSeries, seriesKey } from "@/lib/narrative-view-model";
import { toSegmentedSeriesData, type SeriesPoint } from "@/lib/regime-line-segments";
import type { NarrativeHistoryCategory, NarrativeHistorySeries } from "@/lib/types/narrative";

const COMPOSITE_COLOR = "#2962ff";
const MIXED_SCALE_COLOR = "#ff9800";
const SOURCE_COLORS: Record<string, string> = {
  "pytrends-nightly-7d": "#26a69a",
  "pytrends-backfill-269d": "#80cbc4",
  reddit: "#ef5350",
  "coingecko-narrative": "#ab47bc",
  exchange_volume_share: "#fdd835",
};
const FALLBACK_COLOR = "#8a8f98";

function seriesStatusText(s: NarrativeHistorySeries): string | null {
  if (s.status === "ok") return null;
  const reason = formatNarrativeReason(s.reason ?? s.status);
  return `${s.label}${s.variant ? ` (${s.variant})` : ""} [${s.status}]: ${reason}`;
}

function latestPoint(s: NarrativeHistorySeries) {
  return s.points.length > 0 ? s.points[s.points.length - 1] : null;
}

/**
 * One narrative category: its own chart (independent — not synced with other
 * panels, ADR-9 body / Stage 0 C2), full history, composite plus each
 * normalised source. `gap_before` breaks lines exactly as on /regime.
 * Mixed-scale composite points get orange marker dots. Counts that are not on
 * the 0..1 scale (legacy CoinGecko map count, Hyperliquid new listings) are
 * shown as text, not plotted. Renders only: every number comes from the API.
 */
function CategoryHistoryPanelImpl({ category, height = 160 }: { category: NarrativeHistoryCategory; height?: number }) {
  const id = category.category_id;
  const containerRef = useRef<HTMLDivElement>(null);
  const axis = useMemo(() => buildPanelAxis(category), [category]);
  const plotted = category.series.filter(isPlottedSeries);
  const legacy = category.series.find((s) => s.source === "coingecko");
  const listings = category.series.find((s) => s.source === "exchange_new_listings");

  useEffect(() => {
    const container = containerRef.current;
    if (!container || axis.dates.length === 0) return;
    const chart = createChart(container, {
      height,
      width: container.clientWidth,
      layout: { background: { color: "transparent" }, textColor: "#8a8f98" },
      grid: { vertLines: { visible: false }, horzLines: { visible: false } },
      timeScale: { borderVisible: false },
      rightPriceScale: { borderVisible: false },
      crosshair: { horzLine: { visible: false, labelVisible: false } },
      localization: { priceFormatter: (p: number) => p.toFixed(2) },
    });

    const addLine = (values: (number | null)[], gapBefore: boolean[], color: string, width: 1 | 2 | 3, dashed: boolean) => {
      const { line, dots } = toSegmentedSeriesData(axis.times, values, gapBefore);
      const s = chart.addSeries(LineSeries, {
        color,
        lineWidth: width,
        lineStyle: dashed ? 2 : 0,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      s.setData(line);
      if (dots) {
        const d = chart.addSeries(LineSeries, {
          color,
          lineVisible: false,
          pointMarkersVisible: true,
          pointMarkersRadius: 2,
          crosshairMarkerVisible: false,
          priceLineVisible: false,
          lastValueVisible: false,
        });
        d.setData(dots);
      }
    };

    axis.series.forEach((line) => {
      addLine(line.values, line.gapBefore, SOURCE_COLORS[line.key] ?? FALLBACK_COLOR, 1, line.key === "pytrends-backfill-269d");
    });
    addLine(axis.composite.values, axis.composite.gapBefore, COMPOSITE_COLOR, 3, false);

    if (axis.mixedScaleCount > 0) {
      const m = chart.addSeries(LineSeries, {
        color: MIXED_SCALE_COLOR,
        lineVisible: false,
        pointMarkersVisible: true,
        pointMarkersRadius: 3,
        crosshairMarkerVisible: false,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      m.setData(axis.times.map((t, i): SeriesPoint => { const v = axis.mixedScale[i]; return v === null ? { time: t as UTCTimestamp } : { time: t as UTCTimestamp, value: v }; }) as SeriesPoint[]);
    }

    chart.timeScale().fitContent(); // full history by default (user decision)
    const onResize = () => {
      if (containerRef.current) chart.applyOptions({ width: containerRef.current.clientWidth });
    };
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      chart.remove();
    };
  }, [axis, height]);

  const compositeReason =
    category.composite.status === "unavailable"
      ? formatNarrativeReason(category.composite.reason ?? "unavailable")
      : null;
  const legacyPoint = legacy ? latestPoint(legacy) : null;
  const listingPoint = listings ? latestPoint(listings) : null;
  const anyNotRedistributable = category.series.some((s) => !s.redistributable);

  return (
    <section data-testid={`narrative-panel-${id}`} style={{ borderTop: "1px solid #2a2e39", padding: "6px 0" }}>
      <div>
        <strong>{category.label}</strong>
        <span style={{ color: "#8a8f98", marginLeft: 10, fontSize: 12 }}>composite: {category.composite.status}</span>
        <RedistributionBadge redistributable={!anyNotRedistributable} testId={`narrative-redistribution-${id}`} />
      </div>

      {category.coins.length > 0 && (
        <div style={{ fontSize: 12 }}>
          coins:{" "}
          {category.coins.map((c) => (
            <span
              key={c.symbol}
              data-testid={`narrative-coin-${id}-${c.symbol}`}
              data-narrative-only={c.narrative_only ? "true" : "false"}
              style={{ marginRight: 8 }}
            >
              {c.symbol}
              {c.narrative_only && <em style={{ color: "#8a8f98" }}> (narrative-only)</em>}
            </span>
          ))}
        </div>
      )}

      <div style={{ fontSize: 12 }}>
        <span data-testid={`narrative-legend-${id}-composite`} style={{ color: COMPOSITE_COLOR, marginRight: 12 }}>
          ▬ composite
        </span>
        {plotted.map((s) => {
          const key = seriesKey(s);
          return (
            <span key={key} data-testid={`narrative-legend-${id}-${key}`} style={{ color: SOURCE_COLORS[key] ?? FALLBACK_COLOR, marginRight: 12 }}>
              {key === "pytrends-backfill-269d" ? "┄" : "―"} {s.label}
              {s.variant ? ` (${s.variant})` : ""}
            </span>
          );
        })}
      </div>

      {compositeReason && (
        <DeadDataNotice testId={`narrative-composite-notice-${id}`} message={`Composite unavailable — ${compositeReason}`} className="narrative-notice" />
      )}
      {category.series.map((s) => {
        const text = seriesStatusText(s);
        if (!text) return null;
        return (
          <DeadDataNotice
            key={seriesKey(s)}
            testId={`narrative-notice-${id}-${seriesKey(s)}`}
            message={text}
            className={s.status === "stale" ? "narrative-notice narrative-notice--stale" : "narrative-notice"}
          />
        );
      })}

      {axis.mixedScaleCount > 0 && (
        <div data-testid={`narrative-mixed-scale-${id}`} data-count={axis.mixedScaleCount} style={{ fontSize: 12, color: MIXED_SCALE_COLOR }}>
          ● {axis.mixedScaleCount} composite point{axis.mixedScaleCount === 1 ? "" : "s"} use backfilled pytrends (269-day
          window, different scale) — marked in orange
        </div>
      )}

      {legacy && (
        <div data-testid={`narrative-legacy-count-${id}`} style={{ fontSize: 12, color: "#8a8f98" }}>
          legacy-map count:{" "}
          {legacyPoint && legacyPoint.raw_value !== null
            ? `${legacyPoint.raw_value} (as of ${legacyPoint.date})`
            : formatNarrativeReason(legacy.reason ?? "no-archived-data")}{" "}
          — excluded from the composite
        </div>
      )}

      {listings && (
        <div data-testid={`narrative-new-listings-${id}`} style={{ fontSize: 12, color: "#8a8f98" }}>
          Hyperliquid new listings (display only):{" "}
          {listingPoint && listingPoint.raw_value !== null
            ? `${listingPoint.raw_value} (as of ${listingPoint.date})`
            : formatNarrativeReason(listingPoint?.reason ?? listings.reason ?? "no-archived-data")}
        </div>
      )}

      {axis.dates.length === 0 ? (
        <DeadDataNotice testId={`narrative-chart-empty-${id}`} message="No history to chart for this category yet" />
      ) : (
        <div ref={containerRef} data-testid={`narrative-chart-${id}`} data-points={axis.dates.length} />
      )}
    </section>
  );
}

export const CategoryHistoryPanel = memo(CategoryHistoryPanelImpl);
