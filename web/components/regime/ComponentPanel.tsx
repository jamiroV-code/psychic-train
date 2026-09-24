"use client";

import { memo, useEffect, useRef, useState, type ReactNode } from "react";
import { createChart, LineSeries, type ISeriesApi, type LineData, type UTCTimestamp, type WhitespaceData } from "lightweight-charts";
import { DeadDataNotice } from "@/components/screener/DeadDataNotice";
import type { ChartSync } from "@/lib/regime-chart-sync";
import { formatRegimeValue } from "@/lib/format-regime-value";

export interface PanelLine {
  key: string;
  label: string;
  color: string;
  /** One entry per grid date; null = whitespace (no value). */
  values: (number | null)[];
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

function toSeriesData(gridTimes: number[], values: (number | null)[]): (LineData | WhitespaceData)[] {
  return gridTimes.map((t, i) => {
    const time = t as UTCTimestamp;
    const v = values[i];
    return v === null || v === undefined ? { time } : { time, value: v };
  });
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

    const seriesList: ISeriesApi<"Line">[] = lines.map((line) => {
      const series = chart.addSeries(LineSeries, {
        color: line.color,
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      series.setData(toSeriesData(gridTimes, line.values));
      return series;
    });

    const unregister =
      sync && seriesList.length > 0
        ? sync.register(panelId, {
            chart,
            series: seriesList[0],
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

      <div ref={containerRef} data-testid={`regime-chart-${panelId}`} />

      {open && renderDrillDown(() => setOpen(false))}
    </section>
  );
}

export const ComponentPanel = memo(ComponentPanelImpl);
