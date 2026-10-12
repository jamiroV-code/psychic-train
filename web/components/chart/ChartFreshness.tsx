"use client";

import { useLiveClock } from "@/components/screener/LiveProvider";
import { useVariant } from "@/components/screener/VariantProvider";
import { freshnessCaption, type ChartFreshnessFields } from "@/lib/chart-freshness";
import { dateOnlyCaption } from "@/lib/equities-freshness";
import type { Timeframe } from "@/lib/types/screener";

/**
 * Caption and plain `stale` marker under a screener chart (T34 / S2): when
 * the last bar is, in Brussels time, how old it is against the server's clock, and
 * whether the data is older than the timeframe allows.
 *
 * T43 / S11b: on a live page the age follows the live server clock; without
 * one it is the payload's own `server_time`. `stale` stays the payload's.
 *
 * T47 / S9C: a date-only variant (equities) shows the bar's date alone,
 * `Latest daily bar 2026-10-09` or, for 1w, `Latest weekly bar, week of ...`.
 */
export function ChartFreshness({ chart, timeframe }: { chart: ChartFreshnessFields; timeframe?: Timeframe }) {
  const nowMs = useLiveClock();
  const { dateOnlyBars } = useVariant();
  const caption = dateOnlyBars ? dateOnlyCaption(chart, timeframe) : freshnessCaption(chart, nowMs);
  if (!caption && !chart.stale) return null;
  return (
    <div data-testid="chart-freshness" className="chart-freshness">
      {caption && <span data-testid="chart-freshness-caption">{caption}</span>}
      {chart.stale && (
        <>
          {" "}
          <span data-testid="stale-marker" className="chart-freshness__stale">
            stale
          </span>
        </>
      )}
    </div>
  );
}
