import type { RegimeComponent, RegimeComponentsResponse } from "@/lib/types/regime";
import { isoDateToUtcSeconds } from "@/lib/regime-chart-sync";

/**
 * Lays the API's point lists onto the shared `grid_dates` (plan ADR-7 / P3).
 * Pure re-indexing: a date the API did not send becomes `null` (rendered as a
 * whitespace point / "no value"), never 0 and never interpolated. No value is
 * computed here.
 */

export interface ComponentRow {
  component: RegimeComponent;
  values: (number | null)[];
  raws: (number | null)[];
  contributions: (number | null)[];
  /** API `gap_before` per grid date (false where the series has no point). */
  gapBefore: boolean[];
}

export interface RegimeGridModel {
  gridDates: string[];
  gridTimes: number[];
  components: ComponentRow[];
  reproduced: { values: (number | null)[]; coverage: (number | null)[]; gapBefore: boolean[] };
  published: { values: (number | null)[]; labels: (string | null)[]; gapBefore: boolean[] };
}

function align<P extends { date: string }, V>(
  points: P[],
  indexByDate: Map<string, number>,
  length: number,
  pick: (p: P) => V
): (V | null)[] {
  const out: (V | null)[] = new Array(length).fill(null);
  for (const p of points) {
    const i = indexByDate.get(p.date);
    if (i !== undefined) out[i] = pick(p);
  }
  return out;
}

function alignGaps<P extends { date: string; gap_before?: boolean }>(
  points: P[],
  indexByDate: Map<string, number>,
  length: number
): boolean[] {
  return align(points, indexByDate, length, (p) => p.gap_before === true).map((g) => g === true);
}

export function buildRegimeGridModel(data: RegimeComponentsResponse): RegimeGridModel {
  const gridDates = data.grid_dates;
  const n = gridDates.length;
  const indexByDate = new Map<string, number>();
  gridDates.forEach((d, i) => indexByDate.set(d, i));

  const { reproduced, published } = data.composite;
  return {
    gridDates,
    gridTimes: gridDates.map(isoDateToUtcSeconds),
    components: data.components.map((component) => ({
      component,
      values: align(component.points, indexByDate, n, (p) => p.value),
      raws: align(component.points, indexByDate, n, (p) => p.raw),
      contributions: align(component.points, indexByDate, n, (p) => p.contribution),
      gapBefore: alignGaps(component.points, indexByDate, n),
    })),
    reproduced: {
      values: align(reproduced.points, indexByDate, n, (p) => p.value),
      coverage: align(reproduced.points, indexByDate, n, (p) => p.coverage),
      gapBefore: alignGaps(reproduced.points, indexByDate, n),
    },
    published: {
      values: align(published.points, indexByDate, n, (p) => p.value),
      labels: align(published.points, indexByDate, n, (p) => p.regime_label),
      gapBefore: alignGaps(published.points, indexByDate, n),
    },
  };
}
