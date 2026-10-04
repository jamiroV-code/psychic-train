import { freshnessCaption, type ChartFreshnessFields } from "@/lib/chart-freshness";

/**
 * Caption and plain `stale` marker under a screener chart (T34 / S2): when
 * the last bar is, in UTC, how old it is against the server's clock, and
 * whether the data is older than the timeframe allows.
 */
export function ChartFreshness({ chart }: { chart: ChartFreshnessFields }) {
  const caption = freshnessCaption(chart);
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
