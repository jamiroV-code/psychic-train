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
}

export interface RegimeGridModel {
  gridDates: string[];
  gridTimes: number[];
  components: ComponentRow[];
  reproduced: { values: (number | null)[]; coverage: (number | null)[] };
  published: { values: (number | null)[]; labels: (string | null)[] };
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
    })),
    reproduced: {
      values: align(reproduced.points, indexByDate, n, (p) => p.value),
      coverage: align(reproduced.points, indexByDate, n, (p) => p.coverage),
    },
    published: {
      values: align(published.points, indexByDate, n, (p) => p.value),
      labels: align(published.points, indexByDate, n, (p) => p.regime_label),
    },
  };
}
