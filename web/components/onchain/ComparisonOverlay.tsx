"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { loadIslands, type IslandApi, type PanelSyncStore } from "@/lib/island-loader";
import { ComparisonReadout } from "@/components/onchain/ComparisonReadout";
import { overlayLines } from "@/lib/onchain-overlay-lines";
import {
  INK,
  chainColor,
  comparisonValues,
  formatComparison,
  latestValue,
  visibleRangeFrom,
  type ComparisonMode,
} from "@/lib/onchain-view-model";
import { visibleRangeAttribute } from "@/lib/regime-chart-sync";
import type { ComparisonSeries } from "@/lib/types/onchain";

/**
 * AC-13, frontend half: the overlay only accepts normalised series. Any raw
 * value field is typed `never`, so passing raw points fails `tsc`.
 */
export type NormalisedOnly = ComparisonSeries & {
  points?: never;
  value?: never;
  values?: never;
  raw?: never;
};

export interface ComparisonOverlayProps {
  series: readonly NormalisedOnly[];
  labels: Record<string, string>;
  /** Per-chain `gap_before` on the shared grid, so real holes are not bridged. */
  gapBefore: Record<string, boolean[]>;
  gridDates: string[];
  gridTimes: number[];
  startDate: string;
  logScaleDefault: boolean;
  normalizationMethod: string;
  alternativeMethod: string;
  windowDays: number;
  height?: number;
}

const METHOD_COPY: Record<string, string> = {
  "index-100-at-start-ema28": "28-day EMA of each chain, indexed to 100 at the range start",
  "pct-above-180d-low-ema28": "28-day EMA of each chain, % above its own trailing 180-day low",
};

/**
 * One normalised overlay, one y-axis (no dual axis). Index = 100 at the
 * range start (log scale by default, D5) or % above the 180-day low. Both
 * value sets come from Python; toggling only switches which array is drawn.
 */
export function ComparisonOverlay({
  series,
  labels,
  gapBefore,
  gridDates,
  gridTimes,
  startDate,
  logScaleDefault,
  normalizationMethod,
  alternativeMethod,
  windowDays,
  height = 320,
}: ComparisonOverlayProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [mode, setMode] = useState<ComparisonMode>("index");
  const [logScale, setLogScale] = useState<boolean>(logScaleDefault);
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const effectiveLog = mode === "index" && logScale;
  const range = useMemo(() => visibleRangeFrom(gridDates, startDate), [gridDates, startDate]);

  // Its own store, deliberately not the chain panels' — the overlay has its
  // own range and its own readout, exactly as before.
  const [island, setIsland] = useState<IslandApi | null>(null);
  useEffect(() => {
    let cancelled = false;
    loadIslands()
      .then((api) => {
        if (!cancelled) setIsland(api);
      })
      .catch(() => {
        // The legend, readout and table view still carry every number.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const store: PanelSyncStore | null = useMemo(
    () =>
      island
        ? island.createPanelSync({
            gridDates,
            gridTimes,
            initialRange: range,
            onHover: setHoverIndex,
          })
        : null,
    [island, gridDates, gridTimes, range]
  );

  useEffect(() => {
    const container = containerRef.current;
    if (!container || !island || !store) return;

    const unregister = store.registerElement("comparison", container);
    const dispose = island.mountOnchainOverlay(container, {
      store,
      gridDates,
      lines: overlayLines(series, mode, gapBefore),
      logScale: effectiveLog,
      format: (v: number) => formatComparison(v, mode),
      height,
      label: `Normalised comparison — ${METHOD_COPY[mode === "index" ? normalizationMethod : alternativeMethod] ?? "every chain on one axis"}`,
    });

    return () => {
      dispose();
      unregister();
    };
  }, [island, store, series, gapBefore, gridDates, mode, effectiveLog, height]);

  const method = mode === "index" ? normalizationMethod : alternativeMethod;

  return (
    <section data-testid="onchain-comparison" data-mode={mode} data-log-scale={effectiveLog ? "true" : "false"}>
      <h2 style={{ fontSize: 16, color: INK.primary, margin: "8px 0 4px" }}>Normalised comparison</h2>
      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap", fontSize: 13 }}>
        <div role="radiogroup" aria-label="Comparison mode" style={{ display: "inline-flex", gap: 4 }}>
          <button
            type="button"
            role="radio"
            aria-checked={mode === "index"}
            data-testid="onchain-comparison-mode-index"
            onClick={() => setMode("index")}
            style={{ fontWeight: mode === "index" ? 700 : 400 }}
          >
            Index = 100 at range start
          </button>
          <button
            type="button"
            role="radio"
            aria-checked={mode === "pct"}
            data-testid="onchain-comparison-mode-pct"
            onClick={() => setMode("pct")}
            style={{ fontWeight: mode === "pct" ? 700 : 400 }}
          >
            % above {windowDays}-day low
          </button>
        </div>
        <label style={{ color: INK.secondary }}>
          <input
            type="checkbox"
            data-testid="onchain-comparison-log-toggle"
            checked={effectiveLog}
            disabled={mode !== "index"}
            onChange={(e) => setLogScale(e.target.checked)}
          />{" "}
          Log scale{mode !== "index" ? " (index view only)" : ""}
        </label>
      </div>
      <p data-testid="onchain-comparison-method" style={{ fontSize: 12, color: INK.secondary, margin: "4px 0" }}>
        {METHOD_COPY[method] ?? method}. Range start: {startDate}. Raw counts are never plotted on this chart.
      </p>

      <ul data-testid="onchain-comparison-legend" className="plot-legend plot-legend--list">
        {series.map((s) => {
          const latest = latestValue(comparisonValues(s, mode));
          return (
            <li key={s.chain_id} data-testid={`onchain-legend-${s.chain_id}`}>
              <span aria-hidden="true" className="legend-glyph" style={{ color: chainColor(s.chain_id) }}>
                ―
              </span>{" "}
              <span className="plot-legend__label">{labels[s.chain_id] ?? s.chain_id}</span>{" "}
              {latest ? formatComparison(latest.value, mode) : "no data in range"}
              {s.rebased_late && (
                <span
                  data-testid={`onchain-rebased-late-${s.chain_id}`}
                  style={{ marginLeft: 4, border: `1px solid ${INK.baseline}`, borderRadius: 3, padding: "0 4px" }}
                >
                  late start{s.rebase_date ? ` (${s.rebase_date})` : ""}
                </span>
              )}
            </li>
          );
        })}
      </ul>

      {/* Written here rather than only by the store, so the range is on the
          DOM from first paint instead of appearing once the island loads. The
          store rewrites it on zoom. */}
      <div
        ref={containerRef}
        data-testid="onchain-comparison-chart"
        data-visible-range={range ? visibleRangeAttribute(gridTimes, range) : undefined}
      />

      <ComparisonReadout
        series={series}
        labels={labels}
        gridDates={gridDates}
        mode={mode}
        hoverIndex={hoverIndex}
      />

      <details>
        <summary style={{ fontSize: 12, color: INK.secondary }}>Table view</summary>
        <table data-testid="onchain-comparison-table" style={{ fontSize: 12, fontVariantNumeric: "tabular-nums", color: INK.primary }}>
          <thead>
            <tr>
              <th align="left">Chain</th>
              <th align="left">Rebased on</th>
              <th align="right">Latest index</th>
              <th align="right">Latest % above low</th>
            </tr>
          </thead>
          <tbody>
            {series.map((s) => (
              <tr key={s.chain_id}>
                <td>{labels[s.chain_id] ?? s.chain_id}</td>
                <td>
                  {s.rebase_date ?? "—"}
                  {s.rebased_late ? " (late start)" : ""}
                </td>
                <td align="right">{formatComparison(latestValue(s.index_values)?.value ?? null, "index")}</td>
                <td align="right">{formatComparison(latestValue(s.pct_above_low_values)?.value ?? null, "pct")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </section>
  );
}
