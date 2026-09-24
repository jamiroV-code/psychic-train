"use client";

import type { RegimeComponentsResponse } from "@/lib/types/regime";
import type { RegimeGridModel } from "@/lib/regime-view-model";
import { formatContribution, formatCoverage, formatRegimeRaw, formatRegimeValue } from "@/lib/format-regime-value";

export interface ReadoutProps {
  model: RegimeGridModel;
  composite: RegimeComponentsResponse["composite"];
  /** Hovered grid index; null = not hovering → latest grid date. */
  hoverIndex: number | null;
}

interface Cell {
  id: string;
  label: string;
  lines: string[];
}

/**
 * Single row above the stack, 8 cells (6 components + reproduced +
 * published). Values are shown for the exact grid date — whitespace reads
 * "no value", never 0 and never carried forward.
 */
export function Readout({ model, composite, hoverIndex }: ReadoutProps) {
  const n = model.gridDates.length;
  if (n === 0) return null;
  const index = hoverIndex !== null && hoverIndex >= 0 && hoverIndex < n ? hoverIndex : n - 1;
  const date = model.gridDates[index];

  const cells: Cell[] = model.components.map(({ component, values, raws, contributions }) => ({
    id: component.id,
    label: component.label,
    lines:
      values[index] === null
        ? ["no value"]
        : [
            formatRegimeValue(values[index], component.unit),
            `level ${formatRegimeRaw(raws[index], component.unit)}`,
            `contribution ${formatContribution(contributions[index])}`,
          ],
  }));

  const reproduced = model.reproduced.values[index];
  cells.push({
    id: "reproduced",
    label: composite.reproduced.label,
    lines:
      reproduced === null
        ? ["no value"]
        : [formatRegimeValue(reproduced, "index"), `coverage ${formatCoverage(model.reproduced.coverage[index])}`],
  });

  const published = model.published.values[index];
  const liqtideLabel = model.published.labels[index];
  cells.push({
    id: "published",
    label: composite.published.label,
    lines:
      published === null
        ? ["no value"]
        : [formatRegimeValue(published, "index"), ...(liqtideLabel ? [`LiqTide's label: ${liqtideLabel}`] : [])],
  });

  return (
    <div
      data-testid="regime-readout"
      data-hovering={hoverIndex !== null ? "true" : "false"}
      style={{ display: "grid", gridTemplateColumns: "repeat(8, minmax(0, 1fr))", gap: 8, fontSize: 12 }}
    >
      {cells.map((cell) => (
        <div key={cell.id} data-testid={`regime-readout-cell-${cell.id}`}>
          <div style={{ color: "#8a8f98" }}>{cell.label}</div>
          {cell.lines.map((line) => (
            <div key={line}>{line}</div>
          ))}
          <div data-testid={`regime-readout-date-${cell.id}`} style={{ color: "#8a8f98" }}>
            as of {date}
          </div>
        </div>
      ))}
    </div>
  );
}
