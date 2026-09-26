/**
 * /onchain vitest mock (RFC-5): the shared `lightweight-charts` mock plus the
 * three exports the onchain charts use that it lacks (AreaSeries,
 * PriceScaleMode, createSeriesMarkers). Additive; the shared mock is untouched.
 */
import { vi } from "vitest";
import type { MockSeries } from "@/test/mocks/lightweight-charts";

export * from "@/test/mocks/lightweight-charts";

export const AreaSeries = "AreaSeries";
export const PriceScaleMode = { Normal: 0, Logarithmic: 1, Percentage: 2, IndexedTo100: 3 } as const;

export const markerCalls: { series: MockSeries; markers: unknown[] }[] = [];

export const createSeriesMarkers = vi.fn((series: MockSeries, markers: unknown[] = []) => {
  markerCalls.push({ series, markers });
  return { setMarkers: vi.fn(), markers: () => markers, detach: vi.fn() };
});

export function resetMarkerCalls(): void {
  markerCalls.length = 0;
  createSeriesMarkers.mockClear();
}
