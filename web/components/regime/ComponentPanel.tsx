"use client";

import { memo, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { createChart, LineSeries, type ISeriesApi } from "lightweight-charts";
import { DeadDataNotice } from "@/components/screener/DeadDataNotice";
import type { ChartSync } from "@/lib/regime-chart-sync";
import { formatRegimeValue } from "@/lib/format-regime-value";
import { lineBreakIndices, toSegmentedSeriesData } from "@/lib/regime-line-segments";

export interface PanelLine {
  key: string;
  label: string;
  color: string;
  /** One entry per grid date; null = whitespace (no value). */
  values: (number | null)[];
  /** API `gap_before` per grid date: no line is drawn into a flagged point. */
  gapBefore?: boolean[];
}

export interface PanelNotice {
  testId: string;
  text: string;
  /** Stale data still draws; the notice is a badge, not a replacement. */
  kind: "badge" | "gap";
}

export interface ComponentPanelProps {
  panelId: string;
  title: string;
  /** Header facts, rendered as "k: v" pairs. */
  meta: { label: string; value: string }[];
  notices: PanelNotice[];
  notes: string[];
  attribution?: string;
  unit: string;
  gridTimes: number[];
  lines: PanelLine[];
  sync: ChartSync | null;
  /** Inline drill-down; receives a close callback. */
  renderDrillDown: (close: () => void) => ReactNode;
  height?: number;
}

/**
 * One regime panel: one `createChart` (MiniChart lifecycle), fed the shared
 * grid with whitespace where this panel has no value, registered with the
 * dashboard's sync group. No markers, bands or annotations (plan §2):
 * price lines and last-value labels are off, the horizontal crosshair line is
 * hidden so only the shared date line shows.
 */
function ComponentPanelImpl({
  panelId,
  title,
  meta,
  notices,
  notes,
  attribution,
  unit,
  gridTimes,
  lines,
  sync,
  renderDrillDown,
  height = 140,
}: ComponentPanelProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  // Grid dates where a line is broken by a real data gap (`gap_before`),
  // surfaced as `data-gap-dates` for end-to-end tests. Display-only.
  const gapDates = useMemo(() => {
    const dates = new Set<string>();
    for (const line of lines) {
      for (const i of lineBreakIndices(line.values, line.gapBefore)) {
        dates.add(new Date(gridTimes[i] * 1000).toISOString().slice(0, 10));
      }
    }
    return [...dates].sort();
  }, [lines, gridTimes]);

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
      crosshair: { horzLine: { visible: false, labelVisible: false } },
      localization: { priceFormatter: (price: number) => formatRegimeValue(price, unit) },
    });

    // One line series per PanelLine (these drive crosshair sync). Real data
    // holes (API `gap_before`) are not bridged; isolated points get a
    // dots-only companion series — see lib/regime-line-segments.ts.
    const seriesList: ISeriesApi<"Line">[] = lines.map((line) => {
      const { line: lineData, dots } = toSegmentedSeriesData(gridTimes, line.values, line.gapBefore);
      const series = chart.addSeries(LineSeries, {
        color: line.color,
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      series.setData(lineData);
      if (dots) {
        const dotSeries = chart.addSeries(LineSeries, {
          color: line.color,
          lineVisible: false,
          pointMarkersVisible: true,
          pointMarkersRadius: 2,
          crosshairMarkerVisible: false,
          priceLineVisible: false,
          lastValueVisible: false,
        });
        dotSeries.setData(dots);
      }
      return series;
    });

    const unregister =
      sync && seriesList.length > 0
        ? sync.register(panelId, {
            chart,
            series: seriesList[0],
            element: container,
            valueAt: (i) => {
              for (const line of lines) {
                const v = line.values[i];
                if (v !== null && v !== undefined) return v;
              }
              return null;
            },
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
  }, [panelId, gridTimes, lines, sync, unit, height]);

  return (
    <section data-testid={`regime-panel-${panelId}`} style={{ borderTop: "1px solid #2a2e39", padding: "6px 0" }}>
      <button
        type="button"
        data-testid={`regime-panel-header-${panelId}`}
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        style={{ all: "unset", cursor: "pointer", display: "block", width: "100%" }}
      >
        <strong>{title}</strong>{" "}
        {meta.map((m) => (
          <span key={m.label} style={{ color: "#8a8f98", marginLeft: 10, fontSize: 12 }}>
            {m.label}: {m.value}
          </span>
        ))}
        {lines.length > 1 && (
          <span style={{ display: "block", fontSize: 12 }}>
            {lines.map((l) => (
              <span key={l.key} data-testid={`regime-legend-${l.key}`} style={{ color: l.color, marginRight: 12 }}>
                ― {l.label}
              </span>
            ))}
          </span>
        )}
      </button>

      {notices.map((n) => (
        <DeadDataNotice
          key={n.testId}
          testId={n.testId}
          message={n.text}
          className={n.kind === "badge" ? "regime-notice regime-notice--stale" : "regime-notice"}
        />
      ))}
      {notes.length > 0 && (
        <ul data-testid={`regime-panel-notes-${panelId}`} style={{ margin: "2px 0", paddingLeft: 16, fontSize: 12, color: "#8a8f98" }}>
          {notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      )}
      {attribution && (
        <div data-testid={`regime-attribution-${panelId}`} style={{ fontSize: 11, color: "#8a8f98" }}>
          {attribution}
        </div>
      )}

      <div
        ref={containerRef}
        data-testid={`regime-chart-${panelId}`}
        data-gap-count={gapDates.length}
        data-gap-dates={gapDates.join(",")}
      />

      {open && renderDrillDown(() => setOpen(false))}
    </section>
  );
}

export const ComponentPanel = memo(ComponentPanelImpl);
