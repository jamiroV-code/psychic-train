import {
  NARRATIVE_FALLBACK_COLOR,
  NARRATIVE_SERIES,
} from "@/lib/chart-palette";

export interface NarrativeAxisSeries {
  key: string;
  values: (number | null)[];
  gapBefore: boolean[];
}

export interface NarrativeLine {
  key: string;
  color: string;
  values: (number | null)[];
  gapBefore: boolean[];
  dashed: boolean;
}

/** The two pytrends windows share a hue and are told apart by the dash. */
export const DASHED_KEY = "pytrends-backfill-269d";

/**
 * Chooses which of a category's series are actually drawn, and how.
 *
 * Pulled out of the panel so the rule survives the move to an island: the plot
 * is now Svelte and jsdom never mounts it, so a test asserting "an insufficient
 * series is not plotted" has nothing to read in the DOM. It reads this instead.
 *
 * Insufficient series (narrative-v2 ADR-1) are excluded here — they are
 * reported as an explicit marker in the panel's markup, never as a line.
 */
export function buildNarrativeLines(
  series: readonly NarrativeAxisSeries[],
  hiddenKeys: ReadonlySet<string>,
): NarrativeLine[] {
  return series
    .filter((line) => !hiddenKeys.has(line.key))
    .map((line) => ({
      key: line.key,
      color: NARRATIVE_SERIES[line.key] ?? NARRATIVE_FALLBACK_COLOR,
      values: line.values,
      gapBefore: line.gapBefore,
      dashed: line.key === DASHED_KEY,
    }));
}
