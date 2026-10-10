"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useLiveData } from "@/components/screener/LiveProvider";
import type { SimpleLinesProps } from "@/lib/island-loader";
import { shareStructure, VOLATILE } from "@/lib/same-data";
import { useSimpleLines } from "@/lib/use-simple-lines";
import { boundaryMarkers, btcLegSpanText, btcSeries, currentLegReadouts, legBands } from "@/lib/btc-leg-lines";
import { DeadDataNotice } from "@/components/screener/DeadDataNotice";
import { LegEstimate } from "@/components/screener/LegEstimate";
import { fetchBtcLegs } from "@/lib/api/regime";
import type { BtcLegChartResponse } from "@/lib/types/btc-legs";

export interface BtcLegChartProps {
  // Injectable for tests; defaults to the real API client.
  fetchData?: () => Promise<BtcLegChartResponse>;
}

function formatPrice(v: number): string {
  return Math.round(v).toLocaleString("en-US");
}

/**
 * T38 / S7: BTC daily history above the board, every cached bar, with the
 * confirmed legs shaded (two alternating tints), each boundary date marked,
 * the current leg's numbers and the D-14 estimate. Zoom and pan come from
 * the simple-lines island (S6). Bands, markers and readouts are built in
 * lib/btc-leg-lines.ts, where they are unit-tested.
 *
 * T43 / S11b: refetches when the server's data changes (`dataVersion`),
 * keeps the last data on a failure, and updates the mounted chart in place.
 */
export function BtcLegChart({ fetchData = fetchBtcLegs }: BtcLegChartProps) {
  const [data, setData] = useState<BtcLegChartResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const { dataVersion } = useLiveData();

  useEffect(() => {
    let cancelled = false;
    fetchData()
      .then((res) => {
        if (cancelled) return;
        setData((prev) => shareStructure(prev, res, VOLATILE));
        setError(null);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [fetchData, dataVersion]);

  const available = data?.available === true;
  const series = useMemo(() => (data && available ? btcSeries(data) : []), [data, available]);
  const bands = useMemo(() => (data && available ? legBands(data) : []), [data, available]);
  const markers = useMemo(() => (data && available ? boundaryMarkers(data) : []), [data, available]);
  const span = data ? btcLegSpanText(data) : null;
  const readouts = data ? currentLegReadouts(data) : [];

  const islandProps = useMemo<SimpleLinesProps | null>(
    () =>
      series.length === 0
        ? null
        : {
            series,
            bands,
            markers,
            height: 280,
            format: formatPrice,
            label: span ? `BTC daily close with confirmed legs shaded. ${span}` : "BTC daily close with confirmed legs shaded",
            timeframe: "1d",
          },
    [series, bands, markers, span],
  );
  useSimpleLines(containerRef, islandProps, "btc");

  return (
    <section data-testid="btc-leg-chart" aria-label="BTC legs" className="btc-leg-chart">
      <h2 className="btc-leg-chart__title">BTC legs</h2>
      {span && (
        <p data-testid="btc-leg-span" className="btc-leg-chart__span">
          {span}
        </p>
      )}

      {error && <DeadDataNotice testId="btc-leg-error" message={error} />}

      {data && !available && (
        <p data-testid="btc-leg-unavailable" className="btc-leg-chart__note">
          BTC history unavailable: {data.reason ?? "no reason given"}
        </p>
      )}

      {data && available && data.reason && (
        <p data-testid="btc-leg-note" className="btc-leg-chart__note">
          {data.reason}
        </p>
      )}

      <div ref={containerRef} data-testid="btc-leg-chart-container" />

      {data && available && (
        <>
          {readouts.length > 0 ? (
            <dl className="btc-leg-chart__readouts" data-testid="btc-current-leg">
              {readouts.map((r) => (
                <div key={r.key} data-testid={`btc-current-leg-${r.key}`}>
                  <dt>{r.label}</dt>
                  <dd>{r.value}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <p data-testid="btc-current-leg-none" className="btc-leg-chart__note">
              No confirmed boundary in this history, so there is no current leg.
            </p>
          )}
          <p className="btc-leg-chart__note" data-testid="btc-leg-count">
            {data.legs.length} confirmed legs; the stretch before the first confirmed boundary is not a leg.
          </p>
          <LegEstimate estimate={data.estimate} />
        </>
      )}
    </section>
  );
}
