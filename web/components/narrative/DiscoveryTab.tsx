"use client";

import { useEffect, useState } from "react";
import { DiscoverySourcesPanel } from "@/components/narrative/DiscoverySourcesPanel";
import { DiscoveryTable } from "@/components/narrative/DiscoveryTable";
import { fetchDiscovery as fetchDiscoveryDefault } from "@/lib/api/discovery";
import { DiscoveryHistoryChart, type DiscoveryHistoryChartProps } from "@/components/narrative/DiscoveryHistoryChart";
import type {
  DiscoveryReason,
  DiscoveryResponse,
  DiscoverySelection,
  DiscoverySourcesResponse,
  DiscoveryWindow,
} from "@/lib/types/discovery";

export interface DiscoveryTabProps {
  fetchDiscovery?: (window: DiscoveryWindow) => Promise<DiscoveryResponse>;
  fetchSources?: () => Promise<DiscoverySourcesResponse>;
  /** History chart fetchers, injected by tests. */
  history?: Pick<DiscoveryHistoryChartProps, "fetchCoinHistory" | "fetchCategoryHistory" | "fetchPrice">;
}

const WINDOWS: readonly DiscoveryWindow[] = [7, 30, 90];

const NO_DATA_LINES: Record<Exclude<DiscoveryReason, "">, string> = {
  "categories-missing": "Category lists have not been downloaded yet, so there is nothing to rank.",
  "reference-missing": "The reference data for this window is not available yet.",
  "no-attention-data": "There is no attention data to compare for this window yet.",
};

/** The most weight any returned coin had data for: how much of the 100 is live today. */
function liveWeight(data: DiscoveryResponse): number {
  const all = data.categories.flatMap((c) => c.coins.map((coin) => coin.covered_weight));
  return all.length === 0 ? 0 : Math.round(Math.max(...all));
}

const EXCLUDED_TEXT: [keyof DiscoveryResponse["excluded"], string][] = [
  ["below_volume_floor", "below the volume floor"],
  ["exclusion_list", "exchange tokens and other exclusions"],
  ["no_category", "in none of the categories"],
  ["no_source_data", "no source data yet"],
];

/** "N of 100 top coins shown", with the biggest reasons the rest are not. */
function coverageLine(data: DiscoveryResponse): string {
  const reasons = EXCLUDED_TEXT.filter(([k]) => data.excluded[k] > 0)
    .sort((a, b) => data.excluded[b[0]] - data.excluded[a[0]])
    .map(([k, label]) => `${data.excluded[k]} ${label}`);
  const rest = data.universe_size - data.shown_size;
  return `${data.shown_size} of ${data.universe_size} top coins shown${rest > 0 && reasons.length > 0 ? `: the others are excluded (${reasons.join(", ")})` : ""}`;
}

/** Discovery tab: 7d/30d/90d selector, then a ranked category table or one plain state line. */
export function DiscoveryTab({ fetchDiscovery = fetchDiscoveryDefault, fetchSources, history }: DiscoveryTabProps) {
  const [window, setWindow] = useState<DiscoveryWindow>(30);
  const [attempt, setAttempt] = useState(0);
  const [data, setData] = useState<DiscoveryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selection, setSelection] = useState<DiscoverySelection | null>(null);

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError(null);
    fetchDiscovery(window)
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      cancelled = true;
    };
    // fetchDiscovery is a stable default or an injected test double.
  }, [window, attempt]);

  let body;
  if (error !== null) {
    body = (
      <div data-testid="discovery-error" role="alert">
        <p className="basket-note basket-note--error">Discovery could not be loaded.</p>
        <button type="button" className="board-button" data-testid="discovery-retry" onClick={() => setAttempt((n) => n + 1)}>
          Retry
        </button>
      </div>
    );
  } else if (data === null) {
    body = (
      <p data-testid="discovery-loading" className="basket-note" aria-busy="true">
        Loading discovery...
      </p>
    );
  } else if (data.status === "no-data") {
    const reason = data.reason === "" ? "no-attention-data" : data.reason;
    body = (
      <p data-testid={`discovery-nodata-${reason}`} className="basket-note">
        {NO_DATA_LINES[reason]}
      </p>
    );
  } else {
    body = (
      <DiscoveryTable
        categories={data.categories}
        selection={selection}
        onSelect={setSelection}
        minCategoryCoins={data.min_category_coins}
        risingThresholdPct={data.rising_threshold_pct}
        minCoveredWeight={data.min_covered_weight}
      />
    );
  }

  return (
    <section data-testid="discovery-tab" aria-label="Category discovery" className="basket-chart">
      <header className="basket-chart__head">
        <h2 className="basket-chart__title">Attention by category</h2>
        <span className="basket-seg" role="group" aria-label="Window">
          {WINDOWS.map((w) => (
            <button
              key={w}
              type="button"
              className="basket-seg__btn"
              data-testid={`discovery-window-${w}`}
              aria-pressed={window === w}
              onClick={() => setWindow(w)}
            >
              {`${w}d`}
            </button>
          ))}
        </span>
      </header>
      <DiscoverySourcesPanel fetchSources={fetchSources} />
      {data && data.status === "ok" && (
        <p data-testid="discovery-coverage" className="basket-note">{coverageLine(data)}</p>
      )}
      {data && data.status === "ok" && (
        <p data-testid="discovery-as-of" className="basket-note">{`as of ${data.as_of.slice(0, 10)}`}</p>
      )}
      {data && data.status === "ok" && (
        <p data-testid="discovery-live-weight" className="basket-note">{`Live weight today: ${liveWeight(data)} of 100`}</p>
      )}
      {body}
      {selection && selection.kind === "category" && data?.categories.some((c) => c.id === selection.id && !c.ranked) && (
        <p data-testid="discovery-history-unranked" className="basket-note">
          No history chart: this category has too few coins to rank.
        </p>
      )}
      {selection && data && data.status === "ok" && !(selection.kind === "category" && data.categories.some((c) => c.id === selection.id && !c.ranked)) && (
        <DiscoveryHistoryChart
          selection={selection}
          window={window}
          liveWeight={liveWeight(data)}
          onClose={() => setSelection(null)}
          {...history}
        />
      )}
    </section>
  );
}
