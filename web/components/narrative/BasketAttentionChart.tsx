"use client";

import { useMemo, useRef, useState } from "react";
import Link from "next/link";
import { buildAttentionLines, basketColor } from "@/lib/attention-lines";
import { useSimpleLines } from "@/lib/use-simple-lines";
import type { SimpleLinesProps } from "@/lib/island-loader";
import type { AttentionResponse, AttentionWindow } from "@/lib/types/attention";

const WINDOWS: readonly AttentionWindow[] = [7, 30, 90];
const CHART_HEIGHT = 280;

export interface BasketAttentionChartProps {
  /** Injected; this component never fetches. null = not loaded yet. */
  data: AttentionResponse | null;
  window: AttentionWindow;
  onWindowChange: (window: AttentionWindow) => void;
  error?: string | null;
}

/**
 * Mindshare momentum (attention, never price): a short header with the
 * 7d/30d/90d selector, then one line per basket. The legend is the filter.
 */
export function BasketAttentionChart({ data, window, onWindowChange, error = null }: BasketAttentionChartProps) {
  const [hidden, setHidden] = useState<ReadonlySet<string>>(() => new Set());
  const containerRef = useRef<HTMLDivElement>(null);
  const baskets = data?.baskets ?? [];

  const lines = useMemo(() => buildAttentionLines(baskets, hidden), [baskets, hidden]);
  const props = useMemo<SimpleLinesProps | null>(
    () => (lines.length > 0 ? { series: lines, height: CHART_HEIGHT, label: "Attention score by basket" } : null),
    [lines],
  );
  useSimpleLines(containerRef, props, `attention-${window}`);

  const toggle = (id: string) =>
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const noData = baskets.filter((b) => b.status !== "ok");
  const rankingOff = baskets.some((b) => b.reason === "reference-missing");

  return (
    <section data-testid="attention-chart" aria-label="Basket attention" className="spaghetti-chart">
      <header className="spaghetti-chart__span">
        <span>Attention by basket</span>{" "}
        <span role="group" aria-label="Window">
          {WINDOWS.map((w) => (
            <button
              key={w}
              type="button"
              aria-pressed={w === window}
              data-testid={`attention-window-${w}`}
              onClick={() => onWindowChange(w)}
            >
              {`${w}d`}
            </button>
          ))}
        </span>
      </header>

      {error && <p data-testid="attention-error">{error}</p>}
      {!data && !error && <p data-testid="attention-loading">Loading</p>}
      {data && baskets.length === 0 && (
        <p data-testid="attention-empty">
          No baskets yet. <Link href="/screener">Open the screener</Link>
        </p>
      )}

      {baskets.length > 0 && (
        <>
          <div className="plot-legend" role="group" aria-label="Baskets shown">
            {baskets.map((b, i) => (
              <button
                key={b.id}
                type="button"
                className="spaghetti-chart__toggle"
                aria-pressed={!hidden.has(b.id)}
                data-testid={`attention-toggle-${b.id}`}
                onClick={() => toggle(b.id)}
              >
                <span className="legend-glyph" style={{ color: basketColor(i) }} aria-hidden="true">
                  ―
                </span>{" "}
                <span className="plot-legend__label">{b.name}</span>
              </button>
            ))}
          </div>
          <div ref={containerRef} data-testid="attention-chart-container" />
          <p data-testid="attention-membership" className="plot-legend__note">
            {`membership as of ${data?.membership_as_of}`}
          </p>
          {rankingOff && (
            <p data-testid="attention-ranking-off" className="plot-legend__note">
              Ranking is off: the reference is missing.
            </p>
          )}
          {noData.length > 0 && !rankingOff && (
            <p data-testid="attention-partial" className="plot-legend__note">
              {`no data: ${noData.map((b) => b.name).join(", ")}`}
            </p>
          )}
        </>
      )}
    </section>
  );
}
