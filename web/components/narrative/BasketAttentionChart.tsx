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
    <section data-testid="attention-chart" aria-label="Basket attention" className="spaghetti-chart basket-chart">
      <header className="basket-chart__head">
        <h2 className="basket-chart__title">Attention by basket</h2>
        <span className="basket-seg" role="group" aria-label="Window">
          {WINDOWS.map((w) => (
            <button
              key={w}
              type="button"
              className="basket-seg__btn"
              aria-pressed={w === window}
              data-testid={`attention-window-${w}`}
              onClick={() => onWindowChange(w)}
            >
              {`${w}d`}
            </button>
          ))}
        </span>
      </header>

      {error && <p data-testid="attention-error" className="basket-note basket-note--error" role="alert">{error}</p>}
      {!data && !error && <p data-testid="attention-loading" className="basket-note" role="status">Loading</p>}
      {data && baskets.length === 0 && (
        <p data-testid="attention-empty" className="basket-note">
          No baskets yet. <Link href="/screener">Open the screener</Link>
        </p>
      )}

      {baskets.length > 0 && (
        <>
          <div className="plot-legend basket-legend" role="group" aria-label="Baskets shown">
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
          <p data-testid="attention-membership" className="basket-note">
            {`membership as of ${data?.membership_as_of.slice(0, 10)}`}
          </p>
          {rankingOff && (
            <p data-testid="attention-ranking-off" className="basket-note">
              Ranking is off: the reference is missing.
            </p>
          )}
          {noData.length > 0 && !rankingOff && (
            <p data-testid="attention-partial" className="basket-note">
              {`no data: ${noData.map((b) => b.name).join(", ")}`}
            </p>
          )}
        </>
      )}
    </section>
  );
}
