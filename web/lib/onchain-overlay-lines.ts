import { chainColor, comparisonValues, type ComparisonMode } from "@/lib/onchain-view-model";
import type { ComparisonSeries } from "@/lib/types/onchain";

export interface OverlayLine {
  key: string;
  color: string;
  values: (number | null)[];
  gapBefore?: boolean[];
}

/**
 * The lines the comparison overlay draws: one per chain, in the API's order,
 * each in its own fixed slot colour, carrying whichever normalised array the
 * current mode selects.
 *
 * Pulled out of the component so it survives the move to an island — jsdom
 * does not mount the plot, so "one line per chain in its fixed colour" has
 * nothing to read in the DOM and is asserted here instead. Colour follows the
 * chain, never its rank or the current mode.
 */
export function overlayLines(
  series: readonly ComparisonSeries[],
  mode: ComparisonMode,
  gapBefore: Record<string, boolean[]>,
): OverlayLine[] {
  return series.map((s) => ({
    key: s.chain_id,
    color: chainColor(s.chain_id),
    values: comparisonValues(s, mode),
    gapBefore: gapBefore[s.chain_id],
  }));
}
