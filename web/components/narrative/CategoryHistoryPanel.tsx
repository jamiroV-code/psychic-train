"use client";

import { memo, useEffect, useMemo, useRef } from "react";
import { loadIslands } from "@/lib/island-loader";
import { buildNarrativeLines, DASHED_KEY } from "@/lib/narrative-panel-lines";
import { DeadDataNotice } from "@/components/screener/DeadDataNotice";
import { RedistributionBadge } from "@/components/narrative/RedistributionBadge";
import { formatNarrativeReason } from "@/lib/format-unavailable-reason";
import { buildPanelAxis, isPlottedSeries, seriesKey } from "@/lib/narrative-view-model";
import {
  NARRATIVE_COMPOSITE_COLOR,
  NARRATIVE_FALLBACK_COLOR,
  NARRATIVE_MIXED_SCALE_COLOR,
  NARRATIVE_SERIES,
} from "@/lib/chart-palette";
import type { NarrativeHistoryCategory, NarrativeHistorySeries, NarrativeSufficiency } from "@/lib/types/narrative";

// The UI audit measured the previous hand-picked palette as failing
// colour-blindness gates; these come from the validated --series-N set, with a
// test pinning them to globals.css. See lib/chart-palette.ts.
const COMPOSITE_COLOR = NARRATIVE_COMPOSITE_COLOR;
const MIXED_SCALE_COLOR = NARRATIVE_MIXED_SCALE_COLOR;
const SOURCE_COLORS = NARRATIVE_SERIES;
const FALLBACK_COLOR = NARRATIVE_FALLBACK_COLOR;

function seriesStatusText(s: NarrativeHistorySeries): string | null {
  if (s.status === "ok") return null;
  const reason = formatNarrativeReason(s.reason ?? s.status);
  return `${s.label}${s.variant ? ` (${s.variant})` : ""} [${s.status}]: ${reason}`;
}

/**
 * Narrative-v2 ADR-1: a series' sufficiency comes from the API on every point.
 * A series with no points at all is insufficient by definition.
 */
function seriesSufficiency(s: NarrativeHistorySeries): NarrativeSufficiency {
  return s.points.length > 0 ? s.points[0].sufficiency : "insufficient";
}

function realPointCount(s: NarrativeHistorySeries): number {
  return s.points.filter((p) => p.raw_value !== null).length;
}

function latestPoint(s: NarrativeHistorySeries) {
  return s.points.length > 0 ? s.points[s.points.length - 1] : null;
}

/**
 * One narrative category: its own chart (independent — not synced with other
 * panels, ADR-9 body / Stage 0 C2), full history, composite plus each
 * normalised source. `gap_before` breaks lines exactly as on /regime.
 * Mixed-scale composite points get orange marker dots. Counts that are not on
 * the 0..1 scale (legacy CoinGecko map count, Hyperliquid new listings) are
 * shown as text, not plotted. Renders only: every number comes from the API.
 */
function CategoryHistoryPanelImpl({ category, height = 160 }: { category: NarrativeHistoryCategory; height?: number }) {
  const id = category.category_id;
  const containerRef = useRef<HTMLDivElement>(null);
  const axis = useMemo(() => buildPanelAxis(category), [category]);
  const composable = category.series.filter(isPlottedSeries);
  // Insufficient series are never drawn as a line (ADR-1): they get an explicit marker instead.
  const plotted = composable.filter((s) => seriesSufficiency(s) !== "insufficient");
  const insufficient = composable.filter((s) => s.points.length > 0 && seriesSufficiency(s) === "insufficient");
  const provisional = plotted.filter((s) => seriesSufficiency(s) === "provisional");
  const hiddenKey = insufficient.map(seriesKey).sort().join("|");
  const legacy = category.series.find((s) => s.source === "coingecko");
  const listings = category.series.find((s) => s.source === "exchange_new_listings");

  useEffect(() => {
    const container = containerRef.current;
    if (!container || axis.dates.length === 0) return;

    const lines = buildNarrativeLines(axis.series, new Set(hiddenKey ? hiddenKey.split("|") : []));

    let disposed = false;
    let dispose: (() => void) | undefined;

    // The plot is a Svelte/LayerChart island (ADR-1). This panel is
    // independent by design, so unlike /regime it hands over no shared store.
    loadIslands()
      .then((api) => {
        if (disposed) return;
        dispose = api.mountNarrativePanel(container, {
          dates: axis.dates,
          lines,
          composite: {
            color: COMPOSITE_COLOR,
            values: axis.composite.values,
            gapBefore: axis.composite.gapBefore,
          },
          mixedScale:
            axis.mixedScaleCount > 0 ? { color: MIXED_SCALE_COLOR, values: axis.mixedScale } : null,
          height,
        });
      })
      .catch(() => {
        // Every reading, caveat and reason is in the surrounding markup, so a
        // chart that cannot load stays silent rather than blanking the panel.
      });

    return () => {
      disposed = true;
      dispose?.();
    };
  }, [axis, height, hiddenKey]);

  const compositeReason =
    category.composite.status === "unavailable"
      ? formatNarrativeReason(category.composite.reason ?? "unavailable")
      : null;
  const legacyPoint = legacy ? latestPoint(legacy) : null;
  const listingPoint = listings ? latestPoint(listings) : null;
  const anyNotRedistributable = category.series.some((s) => !s.redistributable);

  return (
    <section data-testid={`narrative-panel-${id}`} className="narrative-panel">
      <div>
        <strong className="narrative-panel__title">{category.label}</strong>
        <span className="narrative-panel__meta">composite: {category.composite.status}</span>
        <RedistributionBadge redistributable={!anyNotRedistributable} testId={`narrative-redistribution-${id}`} />
      </div>

      {category.coins.length > 0 && (
        <div style={{ fontSize: 12 }}>
          coins:{" "}
          {category.coins.map((c) => (
            <span
              key={c.symbol}
              data-testid={`narrative-coin-${id}-${c.symbol}`}
              data-narrative-only={c.narrative_only ? "true" : "false"}
              style={{ marginRight: 8 }}
            >
              {c.symbol}
              {c.narrative_only && <em style={{ color: "#8a8f98" }}> (narrative-only)</em>}
            </span>
          ))}
        </div>
      )}

      <div className="plot-legend">
        <span data-testid={`narrative-legend-${id}-composite`}>
          <span className="legend-glyph" style={{ color: COMPOSITE_COLOR }}>
            ▬
          </span>{" "}
          composite
        </span>
        {plotted.map((s) => {
          const key = seriesKey(s);
          return (
            <span key={key} data-testid={`narrative-legend-${id}-${key}`}>
              <span className="legend-glyph" style={{ color: SOURCE_COLORS[key] ?? FALLBACK_COLOR }}>
                {key === DASHED_KEY ? "┄" : "―"}
              </span>{" "}
              {s.label}
              {s.variant ? ` (${s.variant})` : ""}
              {seriesSufficiency(s) === "provisional" && <em className="plot-legend__note"> (provisional)</em>}
            </span>
          );
        })}
      </div>

      {insufficient.map((s) => {
        const key = seriesKey(s);
        const n = realPointCount(s);
        return (
          <div
            key={`insufficient-${key}`}
            data-testid={`narrative-insufficient-${id}-${key}`}
            data-sufficiency="insufficient"
            style={{ fontSize: 12, color: "#8a8f98" }}
          >
            ⊘ {s.label}
            {s.variant ? ` (${s.variant})` : ""}: not enough history yet ({n} point{n === 1 ? "" : "s"}) — not plotted,
            excluded from the composite
          </div>
        );
      })}
      {provisional.map((s) => {
        const key = seriesKey(s);
        const n = realPointCount(s);
        return (
          <div
            key={`provisional-${key}`}
            data-testid={`narrative-provisional-${id}-${key}`}
            data-sufficiency="provisional"
            style={{ fontSize: 12, color: "#b0b4bc", fontStyle: "italic" }}
          >
            ◌ {s.label}
            {s.variant ? ` (${s.variant})` : ""}: provisional — thin history ({n} point{n === 1 ? "" : "s"}), read with caution
          </div>
        );
      })}

      {compositeReason && (
        <DeadDataNotice testId={`narrative-composite-notice-${id}`} message={`Composite unavailable — ${compositeReason}`} className="narrative-notice" />
      )}
      {category.series.map((s) => {
        const text = seriesStatusText(s);
        if (!text) return null;
        return (
          <DeadDataNotice
            key={seriesKey(s)}
            testId={`narrative-notice-${id}-${seriesKey(s)}`}
            message={text}
            className={s.status === "stale" ? "narrative-notice narrative-notice--stale" : "narrative-notice"}
          />
        );
      })}

      {axis.mixedScaleCount > 0 && (
        <div data-testid={`narrative-mixed-scale-${id}`} data-count={axis.mixedScaleCount} style={{ fontSize: 12, color: MIXED_SCALE_COLOR }}>
          ● {axis.mixedScaleCount} composite point{axis.mixedScaleCount === 1 ? "" : "s"} use backfilled pytrends (269-day
          window, different scale) — marked in orange
        </div>
      )}

      {legacy && (
        <div data-testid={`narrative-legacy-count-${id}`} style={{ fontSize: 12, color: "#8a8f98" }}>
          legacy-map count:{" "}
          {legacyPoint && legacyPoint.raw_value !== null
            ? `${legacyPoint.raw_value} (as of ${legacyPoint.date})`
            : formatNarrativeReason(legacy.reason ?? "no-archived-data")}{" "}
          — excluded from the composite
        </div>
      )}

      {listings && (
        <div data-testid={`narrative-new-listings-${id}`} style={{ fontSize: 12, color: "#8a8f98" }}>
          Hyperliquid new listings (display only):{" "}
          {listingPoint && listingPoint.raw_value !== null
            ? `${listingPoint.raw_value} (as of ${listingPoint.date})`
            : formatNarrativeReason(listingPoint?.reason ?? listings.reason ?? "no-archived-data")}
        </div>
      )}

      {axis.dates.length === 0 ? (
        <DeadDataNotice testId={`narrative-chart-empty-${id}`} message="No history to chart for this category yet" />
      ) : (
        <div ref={containerRef} data-testid={`narrative-chart-${id}`} data-points={axis.dates.length} />
      )}
    </section>
  );
}

export const CategoryHistoryPanel = memo(CategoryHistoryPanelImpl);
