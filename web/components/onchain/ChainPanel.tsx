"use client";

import { memo, useEffect, useMemo, useRef } from "react";
import { loadIslands, type PanelSyncStore } from "@/lib/island-loader";
import { MARKER } from "@/lib/chart-palette";
import { RedistributionBadge } from "@/components/narrative/RedistributionBadge";
import { CrossCheckNote } from "@/components/onchain/CrossCheckNote";
import { FloorRampStateLabel } from "@/components/onchain/FloorRampStateLabel";
import { LimitedHistoryFlag } from "@/components/onchain/LimitedHistoryFlag";
import { SourceMethodBadge } from "@/components/onchain/SourceMethodBadge";
import { lineBreakIndices } from "@/lib/regime-line-segments";
import { INK, formatCount, staleDays, type PanelModel } from "@/lib/onchain-view-model";
import type { ChainGrowth } from "@/lib/types/onchain";

export interface ChainPanelProps {
  chain: ChainGrowth;
  model: PanelModel;
  gridDates: string[];
  gridTimes: number[];
  generatedUtc: string;
  sync: PanelSyncStore | null;
  /** Shared hover index from the sync group; null = show the latest point. */
  hoverIndex: number | null;
  height?: number;
}

function withAlpha(hex: string, alpha: number): string {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}

function lastIndexWithValue(model: PanelModel): number | null {
  for (let i = model.value.length - 1; i >= 0; i--) {
    if (model.value[i] !== null || model.preLaunchValue[i] !== null) return i;
  }
  return null;
}

/**
 * One chain's raw panel: daily value (thin) + EMA28 (2px) in the chain's
 * colour on its own y-axis, pre-launch points as a muted shaded area (D2),
 * floor/ramp markers from the API, honest gaps (`gap_before`), and a hover
 * readout synced with the other panels. No value is computed here.
 */
function ChainPanelImpl({ chain, model, gridDates, gridTimes, generatedUtc, sync, hoverIndex, height = 180 }: ChainPanelProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const series = chain.series;
  const gapDates = useMemo(
    () => lineBreakIndices(model.value, model.gapBefore).map((i) => gridDates[i]),
    [model, gridDates]
  );

  useEffect(() => {
    const container = containerRef.current;
    if (!container || !sync) return;

    let disposed = false;
    let dispose: (() => void) | undefined;

    // The plot is a Svelte/LayerChart island (ADR-1). Every chain panel mounts
    // its own but they all share the one store, which is what keeps the range
    // and the hovered date identical across panels without any panel knowing
    // another exists.
    loadIslands()
      .then((api) => {
        if (disposed) return;
        const unregister = sync.registerElement(chain.id, container);
        const unmountPanel = api.mountOnchainPanel(container, {
          store: sync,
          gridDates,
          value: model.value,
          preLaunchValue: model.hasPreLaunch ? model.preLaunchValue : model.preLaunchValue.map(() => null),
          ema28: model.ema28,
          gapBefore: model.gapBefore,
          markers: model.markers.map((m) => ({ date: m.date, kind: m.kind })),
          color: model.color,
          rawColor: withAlpha(model.color, 0.45),
          preLaunchColor: INK.preLaunch,
          preLaunchFill: INK.preLaunchFill,
          floorColor: MARKER.floor,
          rampColor: MARKER.ramp,
          height,
        });
        dispose = () => {
          unmountPanel();
          unregister();
        };
      })
      .catch(() => {
        // The readout, badges and cross-check note carry every number, so a
        // chart that cannot load stays silent rather than blanking the panel.
      });

    return () => {
      disposed = true;
      dispose?.();
    };
  }, [chain.id, model, gridDates, sync, height]);

  const readoutIndex = hoverIndex ?? lastIndexWithValue(model);
  const readoutRaw = readoutIndex === null ? null : model.value[readoutIndex] ?? model.preLaunchValue[readoutIndex];
  const isPreLaunch = readoutIndex !== null && model.preLaunchValue[readoutIndex] !== null;
  const days = chain.status === "stale" ? staleDays(series?.last_as_of_utc ?? null, generatedUtc) : null;

  return (
    <section
      data-testid={`onchain-panel-${chain.id}`}
      style={{ borderTop: `2px solid ${model.color}`, padding: "6px 0", minWidth: 0 }}
    >
      <div>
        <strong style={{ color: INK.primary }}>{chain.label}</strong>
        {chain.floor_ramp && <FloorRampStateLabel chainId={chain.id} state={chain.floor_ramp.state} />}
        {chain.status === "stale" && (
          <span
            data-testid={`onchain-panel-${chain.id}-stale`}
            style={{ fontSize: 11, color: INK.primary, border: "1px solid #fab219", borderRadius: 3, padding: "0 4px", marginLeft: 6 }}
          >
            ⚠ Stale — last updated {days === null ? "an unknown number of" : days} day{days === 1 ? "" : "s"} ago
          </span>
        )}
        {series && (
          <RedistributionBadge redistributable={series.redistributable} testId={`onchain-panel-${chain.id}-redistribution`} />
        )}
      </div>
      {series && <SourceMethodBadge chainId={chain.id} source={series.source} method={series.method} />}
      <LimitedHistoryFlag chain={chain} />
      {/* On the light strip, because every colour in it is a plot colour —
          the chain hues, the muted pre-launch fill and the neutral markers are
          all validated against the light panel, not the dark shell. */}
      <div className="plot-legend">
        <span>
          <span className="legend-glyph" style={{ color: model.color }}>―</span> 28-day EMA
        </span>
        <span>
          <span className="legend-glyph" style={{ color: withAlpha(model.color, 0.45) }}>―</span> daily value
        </span>
        {model.hasPreLaunch && chain.launch_date && (
          <span data-testid={`onchain-panel-${chain.id}-prelaunch`}>
            <span className="legend-glyph" style={{ color: INK.preLaunch }}>▇</span> before launch ({chain.launch_date}),
            not used in analytics
          </span>
        )}
        {model.markers.length > 0 && (
          <span>
            {/* Canvas point marks are circles, so floor and ramp are told
                apart by colour; the key shows exactly what is drawn. */}
            <span className="legend-glyph" style={{ color: MARKER.floor }}>●</span> floor{" "}
            <span className="legend-glyph" style={{ color: MARKER.ramp }}>●</span> ramp
          </span>
        )}
      </div>
      <div
        ref={containerRef}
        data-testid={`onchain-chart-${chain.id}`}
        data-gap-count={gapDates.length}
        data-gap-dates={gapDates.join(",")}
        data-marker-count={model.markers.length}
      />
      <div data-testid={`onchain-panel-${chain.id}-readout`} style={{ fontSize: 12, color: INK.secondary }}>
        {readoutIndex === null ? (
          "No data"
        ) : (
          <>
            <strong style={{ color: INK.primary }}>{formatCount(readoutRaw ?? null)}</strong> on {gridDates[readoutIndex]}
            {isPreLaunch
              ? " (before launch)"
              : ` · EMA7 ${formatCount(model.ema7[readoutIndex])} · EMA28 ${formatCount(model.ema28[readoutIndex])}`}
          </>
        )}
      </div>
      <CrossCheckNote chainId={chain.id} check={chain.cross_check} />
    </section>
  );
}

export const ChainPanel = memo(ChainPanelImpl);
