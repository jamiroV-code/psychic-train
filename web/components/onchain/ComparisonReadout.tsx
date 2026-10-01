"use client";

import { INK, chainColor, comparisonValues, formatComparison, type ComparisonMode } from "@/lib/onchain-view-model";
import type { ComparisonSeries } from "@/lib/types/onchain";

export interface ComparisonReadoutProps {
  series: readonly ComparisonSeries[];
  labels: Record<string, string>;
  gridDates: string[];
  mode: ComparisonMode;
  /** Hovered grid index from the plot; null shows the prompt instead. */
  hoverIndex: number | null;
}

/**
 * Every chain's value on the hovered date.
 *
 * Its own component so that hovering stays directly testable: the plot is now
 * a Svelte/LayerChart island that jsdom never mounts, so a test can no longer
 * fire a crosshair at a mocked chart. It passes a hoverIndex here instead,
 * which is both simpler and independent of whichever chart library reports the
 * hover. That a real hover reaches this is covered by e2e.
 */
export function ComparisonReadout({ series, labels, gridDates, mode, hoverIndex }: ComparisonReadoutProps) {
  return (
    <div
      data-testid="onchain-comparison-readout"
      data-hovering={hoverIndex === null ? "false" : "true"}
      style={{ fontSize: 12, color: INK.secondary, minHeight: 18 }}
    >
      {hoverIndex === null ? (
        "Hover the chart for every chain's value on a date."
      ) : (
        <>
          <span style={{ color: INK.primary }}>{gridDates[hoverIndex]}</span>
          {series.map((s) => (
            <span key={s.chain_id} style={{ marginLeft: 12 }}>
              <span aria-hidden="true" style={{ color: chainColor(s.chain_id) }}>
                ―
              </span>{" "}
              <strong style={{ color: INK.primary }}>
                {formatComparison(comparisonValues(s, mode)[hoverIndex] ?? null, mode)}
              </strong>{" "}
              {labels[s.chain_id] ?? s.chain_id}
            </span>
          ))}
        </>
      )}
    </div>
  );
}
