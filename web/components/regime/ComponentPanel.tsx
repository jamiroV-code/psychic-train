"use client";

import { memo, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { DeadDataNotice } from "@/components/screener/DeadDataNotice";
import { loadIslands, type PanelSyncStore } from "@/lib/island-loader";
import { lineBreakIndices } from "@/lib/regime-line-segments";

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
  gridDates: string[];
  lines: PanelLine[];
  /** Shared range/hover store for the panel group; null until the island loads. */
  sync: PanelSyncStore | null;
  /** Inline drill-down; receives a close callback. */
  renderDrillDown: (close: () => void) => ReactNode;
  height?: number;
}

/**
 * One regime panel: React owns the header, notices, attribution and drill-down;
 * the plot itself is a Svelte/LayerChart island mounted into the chart node.
 * Every panel shares the one store created by RegimeDashboard, so the visible
 * range and the hovered date stay identical across all seven without any panel
 * addressing another. No markers, bands or annotations (plan §2).
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
  gridDates,
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
    if (!container || !sync) return;

    let disposed = false;
    let dispose: (() => void) | undefined;

    // The plot is a Svelte/LayerChart island. Every panel mounts its own, but
    // they all share the one store created by RegimeDashboard — that is what
    // keeps range and hover synced without the panels knowing about each other,
    // and without the re-entrancy guards the imperative path needed.
    loadIslands()
      .then((api) => {
        if (disposed) return;
        const unregister = sync.registerElement(panelId, container);
        const unmountPanel = api.mountRegimePanel(container, {
          store: sync,
          gridDates,
          lines: lines.map((l) => ({ color: l.color, values: l.values, gapBefore: l.gapBefore })),
          unit,
          height,
        });
        dispose = () => {
          unmountPanel();
          unregister();
        };
      })
      .catch(() => {
        // The panel's header, notices and drill-down still carry every number
        // and reason, so a chart that cannot load stays silent rather than
        // replacing data with an error.
      });

    return () => {
      disposed = true;
      dispose?.();
    };
  }, [panelId, gridDates, lines, sync, unit, height]);

  return (
    <section data-testid={`regime-panel-${panelId}`} className="regime-panel">
      <button
        type="button"
        data-testid={`regime-panel-header-${panelId}`}
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="regime-panel__header"
      >
        <strong className="regime-panel__title">{title}</strong>{" "}
        {meta.map((m) => (
          <span key={m.label} className="regime-panel__meta">
            {m.label}: {m.value}
          </span>
        ))}
        {lines.length > 1 && (
          <span className="regime-panel__legend">
            {lines.map((l) => (
              <span key={l.key} data-testid={`regime-legend-${l.key}`} style={{ color: l.color }}>
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
        <ul data-testid={`regime-panel-notes-${panelId}`} className="regime-panel__notes">
          {notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      )}
      {attribution && (
        <div data-testid={`regime-attribution-${panelId}`} className="regime-panel__attribution">
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
