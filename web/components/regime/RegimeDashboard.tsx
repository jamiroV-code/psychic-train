"use client";

import { useEffect, useMemo, useState } from "react";
import { ComponentPanel, type PanelLine, type PanelNotice } from "@/components/regime/ComponentPanel";
import { DrillDown } from "@/components/regime/DrillDown";
import { Readout } from "@/components/regime/Readout";
import { DeadDataNotice } from "@/components/screener/DeadDataNotice";
import { fetchRegimeComponents } from "@/lib/api/regime";
import { SERIES } from "@/lib/chart-palette";
import { defaultVisibleRange } from "@/lib/regime-chart-sync";
 import { loadIslands, type IslandApi, type RegimeStore } from "@/lib/island-loader";
import { formatRegimeStatus } from "@/lib/format-regime-value";
import { buildRegimeGridModel } from "@/lib/regime-view-model";
import type { RegimeComponentsResponse } from "@/lib/types/regime";

// Canvas marks cannot read a CSS custom property, so the series colours come
// from the shared constants rather than from globals.css directly; a test keeps
// the two in step (lib/__tests__/chart-palette.test.ts). No theme toggle —
// decision 8.
const COMPONENT_COLOR = SERIES.primary;
const REPRODUCED_COLOR = SERIES.primary;
const PUBLISHED_COLOR = SERIES.secondary;

export interface RegimeDashboardProps {
  fetchData?: () => Promise<RegimeComponentsResponse>;
}

function componentNotices(id: string, status: RegimeComponentsResponse["components"][number]["status"], reason: string | null): PanelNotice[] {
  const text = formatRegimeStatus(status, reason);
  if (text === null) return [];
  return [{ testId: `regime-notice-${id}`, text, kind: status === "stale" ? "badge" : "gap" }];
}

/**
 * /regime page body (plan ADR-7, RFC-005): fetch once, lay all seven panels on
 * the shared `grid_dates`, sync range + crosshair, default to the last 3
 * years, readout row above, reserved empty right column for the future
 * insights box. Renders only — every number comes from the API.
 */
export function RegimeDashboard({ fetchData = () => fetchRegimeComponents() }: RegimeDashboardProps) {
  const [data, setData] = useState<RegimeComponentsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchData()
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      cancelled = true;
    };
    // Fetch once on mount (ADR-6: one endpoint, full history).
  }, []);

  const model = useMemo(() => (data ? buildRegimeGridModel(data) : null), [data]);

  // The chart islands are built by Vite and fetched at runtime, so the store
  // they share cannot exist until that module has loaded.
  const [island, setIsland] = useState<IslandApi | null>(null);
  useEffect(() => {
    let cancelled = false;
    loadIslands()
      .then((api) => {
        if (!cancelled) setIsland(api);
      })
      .catch(() => {
        // Panels render their header, notices and drill-down regardless; a
        // chart bundle that cannot load must not blank the page.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const sync: RegimeStore | null = useMemo(
    () =>
      island && model
        ? island.createRegimeChartSync({
            gridDates: model.gridDates,
            gridTimes: model.gridTimes,
            initialRange: defaultVisibleRange(model.gridDates),
            onHover: setHoverIndex,
          })
        : null,
    [island, model]
  );

  const panels = useMemo(() => {
    if (!data || !model) return [];
    const componentPanels = model.components.map(({ component, values, gapBefore }) => ({
      panelId: component.id,
      title: component.label,
      meta: [
        { label: "weight", value: `${Math.round(component.weight * 100)}%` },
        { label: "source", value: component.source },
        { label: "from", value: component.first_date ?? "no data" },
        { label: "as of", value: component.last_date ?? "no data" },
        { label: "status", value: component.status },
      ],
      notices: componentNotices(component.id, component.status, component.reason),
      notes: component.notes,
      attribution: undefined as string | undefined,
      unit: component.unit,
      lines: [{ key: component.id, label: component.label, color: COMPONENT_COLOR, values, gapBefore }] as PanelLine[],
      renderDrillDown: (close: () => void) => <DrillDown kind="component" component={component} onClose={close} />,
    }));

    const { reproduced, published } = data.composite;
    const compositeNotices: PanelNotice[] = [];
    if (reproduced.points.length === 0) {
      compositeNotices.push({
        testId: "regime-notice-reproduced",
        text: "No reproduced values in this range — no date meets the coverage rule (see drill-down).",
        kind: "gap",
      });
    }
    if (published.status !== "ok") {
      compositeNotices.push({
        testId: "regime-notice-published",
        text: "Unavailable — no LiqTide published values in this range.",
        kind: "gap",
      });
    }
    const lastReproduced = reproduced.points.at(-1)?.date ?? "no data";
    const lastPublished = published.points.at(-1)?.date ?? "no data";

    return [
      ...componentPanels,
      {
        panelId: "composite",
        title: "Tide index",
        meta: [
          { label: "reproduced as of", value: lastReproduced },
          { label: "published as of", value: lastPublished },
        ],
        notices: compositeNotices,
        notes: [] as string[],
        attribution: published.attribution,
        unit: "index",
        lines: [
          { key: "reproduced", label: reproduced.label, color: REPRODUCED_COLOR, values: model.reproduced.values, gapBefore: model.reproduced.gapBefore },
          { key: "published", label: published.label, color: PUBLISHED_COLOR, values: model.published.values, gapBefore: model.published.gapBefore },
        ] as PanelLine[],
        renderDrillDown: (close: () => void) => <DrillDown kind="composite" composite={data.composite} onClose={close} />,
      },
    ];
  }, [data, model]);

  if (error) {
    return (
      <DeadDataNotice
        testId="regime-error"
        message={`Regime data could not be loaded: ${error}. Check that the API is running on 127.0.0.1:8000.`}
      />
    );
  }
  if (!data || !model) {
    return <div data-testid="regime-loading">Loading regime components…</div>;
  }
  if (model.gridDates.length === 0) {
    return <DeadDataNotice testId="regime-empty" message="No regime data in this range — every component is empty." />;
  }

  return (
    // Layout moved to CSS (`.regime-layout`) so the reserved column can collapse
    // on narrower viewports. An inline style cannot express a media query, and
    // holding 280px for an empty box squeezes the plot area enough to shorten
    // the default three-year window — see globals.css §8.
    <div data-testid="regime-dashboard" className="regime-layout">
      <div>
        <Readout model={model} composite={data.composite} hoverIndex={hoverIndex} />
        {panels.map((p) => (
          <ComponentPanel
            key={p.panelId}
            {...p}
            gridTimes={model.gridTimes}
            gridDates={model.gridDates}
            sync={sync}
          />
        ))}
      </div>
      {/* Reserved for the future insights text box (plan §2) — intentionally empty. */}
      <aside data-testid="regime-reserved-column" aria-hidden="true" />
    </div>
  );
}
