"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ApiUnavailableNotice, ComputationStatusBanner } from "@/components/pairs/ComputationStatusBanner";
import { DeadDataNotice } from "@/components/screener/DeadDataNotice";
import { fetchPairs } from "@/lib/api/pairs";
import {
  RAW_ONLY_TAG,
  formatDirection,
  formatHalfLife,
  formatOverlapDays,
  formatPValue,
  formatZScore,
  isRawOnlySignificant,
  pairLabel,
  significanceSummary,
  sortPairs,
  NO_VALUE,
} from "@/lib/format-pairs-value";
import type { PairSummary, PairsResponse } from "@/lib/types/pairs";

export interface PairsTableProps {
  fetchData?: () => Promise<PairsResponse>;
}

const STAT_COLUMNS = 6; // raw p, BH p, direction, Johansen, half-life, z-score

function JohansenCell({ pair }: { pair: PairSummary }) {
  if (pair.johansen) return <>{pair.johansen.rank_at_least_1 ? "Yes" : "No"}</>;
  return (
    <span data-testid={`pairs-johansen-reason-${pair.coin_a}-${pair.coin_b}`}>
      {NO_VALUE} {pair.johansen_reason ?? ""}
    </span>
  );
}

function Row({ pair }: { pair: PairSummary }) {
  const id = `${pair.coin_a}-${pair.coin_b}`;
  const rawOnly = isRawOnlySignificant(pair);
  return (
    <tr data-testid={`pairs-row-${id}`} data-status={pair.status}>
      <td>
        <Link href={`/pairs/${pair.coin_a}/${pair.coin_b}`}>{pairLabel(pair)}</Link>
        {rawOnly && (
          <span data-testid={`pairs-raw-only-${id}`} style={{ marginLeft: 6, fontSize: "0.8em", color: "#ff9800" }}>
            {RAW_ONLY_TAG}
          </span>
        )}
      </td>
      <td>{pair.status}</td>
      <td>{formatOverlapDays(pair.overlap_days)}</td>
      {pair.status === "ok" ? (
        <>
          <td>{formatPValue(pair.eg_p_raw)}</td>
          <td>{formatPValue(pair.eg_p_bh)}</td>
          <td>{formatDirection(pair.eg_direction)}</td>
          <td>
            <JohansenCell pair={pair} />
          </td>
          <td>{formatHalfLife(pair.half_life)}</td>
          <td>{formatZScore(pair.z_score)}</td>
        </>
      ) : (
        <td colSpan={STAT_COLUMNS}>
          <DeadDataNotice testId={`pairs-reason-${id}`} message={pair.reason ?? `No statistics (${pair.status})`} />
        </td>
      )}
    </tr>
  );
}

/**
 * /pairs page body (RFC-004): fetch once, show freshness + significance
 * banners and the disclosure, then every pair in the fixed default order
 * (corrected p ascending; non-ok rows in a separate group at the bottom).
 * Renders only — every number comes from the API.
 */
export function PairsTable({ fetchData = fetchPairs }: PairsTableProps) {
  const [data, setData] = useState<PairsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

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
    // Fetch once on mount.
  }, []);

  const rows = useMemo(() => (data ? sortPairs(data.pairs) : []), [data]);

  if (error !== null) return <ApiUnavailableNotice error={error} />;
  if (data === null) return <p data-testid="pairs-loading">Loading pairs…</p>;

  return (
    <div>
      <ComputationStatusBanner envelope={data} />
      {data.computation_status !== "results_unavailable" && rows.length > 0 && (
        <>
          <p data-testid="pairs-significance-banner" style={{ fontWeight: 600 }}>
            {significanceSummary(data.pairs)}
          </p>
          <p data-testid="pairs-disclosure" style={{ fontSize: "0.9em", color: "#8a8f98" }}>
            {data.diagnostic_disclosure}
          </p>
          <table data-testid="pairs-table">
            <thead>
              <tr>
                <th>Pair</th>
                <th>Status</th>
                <th>Overlap days</th>
                <th>Raw p</th>
                <th>BH-corrected p</th>
                <th>Direction</th>
                <th>Johansen</th>
                <th>Half-life</th>
                <th>z-score</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((pair) => (
                <Row key={`${pair.coin_a}-${pair.coin_b}`} pair={pair} />
              ))}
            </tbody>
          </table>
        </>
      )}
      {data.computation_status !== "results_unavailable" && rows.length === 0 && (
        <p data-testid="pairs-empty">No pairs in the current universe.</p>
      )}
    </div>
  );
}
