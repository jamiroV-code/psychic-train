"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ChainPanel } from "@/components/onchain/ChainPanel";
import { ComparisonOverlay } from "@/components/onchain/ComparisonOverlay";
import { MetricSelector } from "@/components/onchain/MetricSelector";
import { RangePicker } from "@/components/onchain/RangePicker";
import { SourceAttributionFooter } from "@/components/onchain/SourceAttributionFooter";
import { UnavailableChainCard } from "@/components/onchain/UnavailableChainCard";
import { fetchOnchainGrowth } from "@/lib/api/onchain";
import { isoDateToUtcSeconds } from "@/lib/regime-chart-sync";
import { loadIslands, type IslandApi, type PanelSyncStore } from "@/lib/island-loader";
import {
  DEFAULT_RANGE,
  INK,
  buildPanelModel,
  isLive,
  methodNote,
  rangeStart,
  staleDays,
  usesGrowthepie,
  visibleRangeFrom,
  type RangeKey,
} from "@/lib/onchain-view-model";
import type { OnchainGrowthResponse, OnchainMetric } from "@/lib/types/onchain";

export interface OnchainDashboardProps {
  /** Injected for tests; defaults to the real API client. */
  fetchData?: (metric: OnchainMetric, start?: string) => Promise<OnchainGrowthResponse>;
}

/**
 * /onchain page body (chain-growth RFC-5). One filter row (metric + range)
 * scopes everything below it. Changing either re-fetches; the range is sent
 * as `?start=` so the comparison is rebased in Python, never in TypeScript.
 * While a refetch runs the previous render stays at reduced opacity.
 */
export function OnchainDashboard({ fetchData = fetchOnchainGrowth }: OnchainDashboardProps) {
  const [metric, setMetric] = useState<OnchainMetric>("active_addresses");
  const [range, setRange] = useState<RangeKey>(DEFAULT_RANGE);
  const [data, setData] = useState<OnchainGrowthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const requestSeq = useRef(0);

  const load = useCallback(
    (m: OnchainMetric, start?: string) => {
      const seq = ++requestSeq.current;
      setLoading(true);
      setError(null);
      fetchData(m, start)
        .then((resp) => {
          if (seq !== requestSeq.current) return; // a newer request superseded this one
          setData(resp);
          setLoading(false);
        })
        .catch((err: unknown) => {
          if (seq !== requestSeq.current) return;
          setError(err instanceof Error ? err.message : String(err));
          setLoading(false);
        });
    },
    [fetchData]
  );

  // First load: no `start`, so the API applies its own 1-year default.
  useEffect(() => {
    load("active_addresses");
  }, [load]);

  // Calendar offset from the last grid date; undefined until the first response lands.
  const startFor = (r: RangeKey) => (data ? rangeStart(r, data.grid_dates) : undefined);

  const onMetric = (m: OnchainMetric) => {
    setMetric(m);
    load(m, startFor(range));
  };
  const onRange = (r: RangeKey) => {
    setRange(r);
    load(metric, startFor(r));
  };

  const gridTimes = useMemo(() => (data ? data.grid_dates.map(isoDateToUtcSeconds) : []), [data]);
  const live = useMemo(() => (data ? data.chains.filter(isLive) : []), [data]);
  const unavailable = useMemo(() => (data ? data.chains.filter((c) => !isLive(c)) : []), [data]);
  const models = useMemo(
    () => new Map(live.map((c) => [c.id, buildPanelModel(c, data?.grid_dates ?? [])])),
    [live, data]
  );
  // The chart islands are built by Vite and fetched at runtime, so the store
  // the chain panels share cannot exist until that module has loaded.
  const [island, setIsland] = useState<IslandApi | null>(null);
  useEffect(() => {
    let cancelled = false;
    loadIslands()
      .then((api) => {
        if (!cancelled) setIsland(api);
      })
      .catch(() => {
        // Panels still render their badges, readout and notes without a plot.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const sync: PanelSyncStore | null = useMemo(
    () =>
      island && data
        ? island.createPanelSync({
            gridDates: data.grid_dates,
            gridTimes,
            initialRange: visibleRangeFrom(data.grid_dates, data.comparison.start_date),
            onHover: setHoverIndex,
          })
        : null,
    [island, data, gridTimes]
  );
  const labels = useMemo(() => Object.fromEntries((data?.chains ?? []).map((c) => [c.id, c.label])), [data]);
  const gapBefore = useMemo(
    () => Object.fromEntries([...models.entries()].map(([id, m]) => [id, m.gapBefore])),
    [models]
  );

  const filters = (
    <div data-testid="onchain-filters" style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "center", margin: "6px 0" }}>
      <span style={{ fontSize: 13, color: INK.secondary }}>Metric</span>
      <MetricSelector value={metric} onChange={onMetric} />
      <span style={{ fontSize: 13, color: INK.secondary }}>Range</span>
      <RangePicker value={range} onChange={onRange} />
    </div>
  );

  if (data === null) {
    if (error !== null) {
      return (
        <div data-testid="onchain-error" role="alert">
          Could not load on-chain growth data: {error}{" "}
          <button type="button" data-testid="onchain-retry" onClick={() => load(metric, startFor(range))}>
            Retry
          </button>
        </div>
      );
    }
    return <div data-testid="onchain-loading">Loading on-chain growth data…</div>;
  }

  const stale = live.filter((c) => c.status === "stale");

  return (
    <div data-testid="onchain-dashboard" data-metric={data.metric} style={{ color: INK.primary }}>
      {filters}
      {loading && (
        <div data-testid="onchain-refetching" style={{ fontSize: 12, color: INK.secondary }}>
          Loading…
        </div>
      )}
      {error !== null && (
        <div data-testid="onchain-error" role="alert" style={{ fontSize: 12 }}>
          Could not refresh: {error} — showing the previous data.{" "}
          <button type="button" data-testid="onchain-retry" onClick={() => load(metric, startFor(range))}>
            Retry
          </button>
        </div>
      )}
      <div style={{ opacity: loading ? 0.5 : 1, transition: "opacity 120ms" }}>
        <p data-testid="onchain-method-note" style={{ fontSize: 12, color: INK.secondary, margin: "4px 0 8px" }}>
          {methodNote(data.params)}
        </p>
        {stale.length > 0 && (
          <div data-testid="onchain-stale-banner" role="note" style={{ fontSize: 12, borderLeft: "3px solid #fab219", paddingLeft: 6 }}>
            ⚠ Stale data:{" "}
            {stale
              .map((c) => {
                const d = staleDays(c.series?.last_as_of_utc ?? null, data.generated_utc);
                return `${c.label} last updated ${d === null ? "at an unknown time" : `${d} day${d === 1 ? "" : "s"} ago`}`;
              })
              .join("; ")}
          </div>
        )}

        {live.length === 0 ? (
          <div data-testid="onchain-empty">No chain has data for this metric yet — every chain below is unavailable.</div>
        ) : (
          <ComparisonOverlay
            key={`${data.metric}-${data.comparison.start_date}`}
            series={data.comparison.series}
            labels={labels}
            gapBefore={gapBefore}
            gridDates={data.grid_dates}
            gridTimes={gridTimes}
            startDate={data.comparison.start_date}
            logScaleDefault={data.comparison.log_scale_default}
            normalizationMethod={data.comparison.normalization_method}
            alternativeMethod={data.comparison.alternative_method}
            windowDays={data.params.window_days}
          />
        )}

        <h2 style={{ fontSize: 16, margin: "16px 0 4px" }}>Per chain (raw values, own scale)</h2>
        <div
          data-testid="onchain-panels"
          style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(360px, 1fr))", gap: 16 }}
        >
          {live.map((c) => (
            <ChainPanel
              key={c.id}
              chain={c}
              model={models.get(c.id)!}
              gridDates={data.grid_dates}
              gridTimes={gridTimes}
              generatedUtc={data.generated_utc}
              sync={sync}
              hoverIndex={hoverIndex}
            />
          ))}
        </div>

        {unavailable.length > 0 && (
          <div
            data-testid="onchain-unavailable-list"
            style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 12, marginTop: 12 }}
          >
            {unavailable.map((c) => (
              <UnavailableChainCard key={c.id} chain={c} />
            ))}
          </div>
        )}

        {usesGrowthepie(data) && <SourceAttributionFooter attribution={data.attribution} />}
      </div>
    </div>
  );
}
