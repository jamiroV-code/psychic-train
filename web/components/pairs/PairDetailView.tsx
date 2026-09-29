"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ApiUnavailableNotice, ComputationStatusBanner } from "@/components/pairs/ComputationStatusBanner";
import { SpreadChart } from "@/components/pairs/SpreadChart";
import { DeadDataNotice } from "@/components/screener/DeadDataNotice";
import { fetchPairDetail } from "@/lib/api/pairs";
import {
  NOT_MEAN_REVERTING_TEXT,
  NO_VALUE,
  OPTIMISM_NOTE,
  formatDirection,
  formatHalfLife,
  formatNumber,
  formatPValue,
  formatSampleWindow,
  formatZScore,
} from "@/lib/format-pairs-value";
import type { EGDirection, PairDetail, PairDetailResponse } from "@/lib/types/pairs";

export interface PairDetailViewProps {
  a: string;
  b: string;
  fetchData?: (a: string, b: string) => Promise<PairDetailResponse>;
}

function EGBlock({ testId, eg, used }: { testId: string; eg: EGDirection | null; used: boolean }) {
  if (!eg) {
    return <div data-testid={testId}>{NO_VALUE}</div>;
  }
  return (
    <div data-testid={testId} data-used={used ? "true" : "false"} style={{ flex: 1, padding: 8, border: "1px solid #2a2e39" }}>
      <h4 style={{ margin: "0 0 4px" }}>
        {eg.dependent} on {eg.independent}
        {used && <span style={{ marginLeft: 6, fontSize: "0.8em", color: "var(--brand-navy-lift)" }}>(used for ranking)</span>}
      </h4>
      <div>p-value: {formatPValue(eg.p_value)}</div>
      <div>Hedge ratio: {formatNumber(eg.hedge_ratio, 3)}</div>
      <div>t-stat: {formatNumber(eg.t_stat, 2)}</div>
    </div>
  );
}

function OkBody({ pair }: { pair: PairDetail }) {
  const usedKey = pair.eg_direction;
  const key = (eg: EGDirection | null) => (eg ? `${eg.dependent}~${eg.independent}` : null);
  const first = pair.spread[0]?.date ?? null;
  const last = pair.spread[pair.spread.length - 1]?.date ?? null;
  return (
    <>
      <section>
        <h3>Spread ({formatDirection(pair.spread_direction)})</h3>
        <p data-testid="pairs-chart-range">
          Plotted: {first ?? NO_VALUE} → {last ?? NO_VALUE} ({pair.spread.length.toLocaleString("en-US")} points)
        </p>
        <SpreadChart points={pair.spread} />
        <p data-testid="pairs-detail-z">Latest z-score: {formatZScore(pair.z_score)}</p>
      </section>

      <section>
        <h3>Engle-Granger (both directions)</h3>
        <div style={{ display: "flex", gap: 12 }}>
          <EGBlock testId="pairs-eg-a-on-b" eg={pair.eg_a_on_b} used={key(pair.eg_a_on_b) === usedKey} />
          <EGBlock testId="pairs-eg-b-on-a" eg={pair.eg_b_on_a} used={key(pair.eg_b_on_a) === usedKey} />
        </div>
        <p data-testid="pairs-bh-p">BH-corrected p (ranking direction): {formatPValue(pair.eg_p_bh)}</p>
        <p data-testid="pairs-optimism-note" style={{ fontSize: "0.9em", color: "#8a8f98" }}>
          {OPTIMISM_NOTE}
        </p>
      </section>

      <section data-testid="pairs-johansen-block">
        <h3>Johansen</h3>
        {pair.johansen ? (
          <>
            <div>Trace statistic: {formatNumber(pair.johansen.trace_stat, 2)}</div>
            <div>95% critical value: {formatNumber(pair.johansen.crit_value_95, 2)}</div>
            <div data-testid="pairs-johansen-verdict">
              Cointegrated at 95% (rank ≥ 1): {pair.johansen.rank_at_least_1 ? "Yes" : "No"}
            </div>
          </>
        ) : (
          <div data-testid="pairs-johansen-reason">
            {NO_VALUE} {pair.johansen_reason ?? "Johansen result unavailable"}
          </div>
        )}
      </section>

      <section data-testid="pairs-half-life">
        <h3>Half-life</h3>
        {pair.half_life?.state === "not_mean_reverting" ? (
          <div data-testid="pairs-not-mean-reverting" role="status" style={{ border: "1px solid #ff9800", padding: 8 }}>
            {NOT_MEAN_REVERTING_TEXT}
          </div>
        ) : (
          <div>{formatHalfLife(pair.half_life)}</div>
        )}
      </section>
    </>
  );
}

/**
 * /pairs/[a]/[b] body (RFC-004): freshness banner, sample window, the
 * whole-history disclosure, then the spread chart, both EG directions side
 * by side, the separate Johansen block and the half-life. Non-ok pairs show
 * the API's reason and no statistics. Renders only.
 */
export function PairDetailView({ a, b, fetchData = fetchPairDetail }: PairDetailViewProps) {
  const [data, setData] = useState<PairDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchData(a, b)
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      cancelled = true;
    };
  }, [a, b]);

  const back = (
    <p>
      <Link href="/pairs">← All pairs</Link>
    </p>
  );

  if (error !== null) {
    return (
      <div>
        {back}
        <ApiUnavailableNotice error={error} />
      </div>
    );
  }
  if (data === null) return <p data-testid="pairs-loading">Loading pair…</p>;

  const pair = data.pair;
  return (
    <div>
      {back}
      <ComputationStatusBanner envelope={data} />
      {pair === null ? (
        <DeadDataNotice testId="pairs-detail-missing" message={`No result for ${a}/${b}.`} />
      ) : (
        <>
          <h2 data-testid="pairs-detail-heading">
            {pair.coin_a} / {pair.coin_b} <small>({pair.status})</small>
          </h2>
          <p data-testid="pairs-sample-window">
            Sample: {formatSampleWindow(pair.sample_start, pair.sample_end, pair.overlap_days)}
          </p>
          <p data-testid="pairs-disclosure" role="note" style={{ border: "1px solid #2a2e39", padding: 8 }}>
            {data.diagnostic_disclosure}
          </p>
          {pair.status === "ok" ? (
            <OkBody pair={pair} />
          ) : (
            <DeadDataNotice testId="pairs-detail-reason" message={pair.reason ?? `No statistics (${pair.status})`} />
          )}
        </>
      )}
    </div>
  );
}
