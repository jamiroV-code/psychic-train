"use client";

import { useEffect, useState } from "react";
import { ChartFreshness } from "@/components/chart/ChartFreshness";
import { MiniChart } from "@/components/chart/MiniChart";
import { DeadDataNotice } from "@/components/screener/DeadDataNotice";
import { fetchScalpView } from "@/lib/api/screener";
import { TIMEFRAMES, type ScalpView, type Timeframe } from "@/lib/types/screener";

export interface DrillDownViewProps {
  symbol: string;
  onClose?: () => void;
  fetchScalp?: (symbol: string, timeframe: Timeframe) => Promise<ScalpView>;
}

const DEFAULT_DRILLDOWN_TIMEFRAME: Timeframe = "4h"; // matches the original scalp cadence

/**
 * On-demand, single-coin drill-down (AC-7) — never a main-board tile.
 * Amendment 2 (AC-18): carries its OWN timeframe control across the same
 * 15m/1h/4h/1D/1W range as the board, independent of whatever the board's
 * own toggle is currently set to. The scalp RSI reading is rendered
 * separately, always labeled with its own explicit timeframe, so it can
 * never be mistaken for whichever interval the chart is currently zoomed to.
 */
export function DrillDownView({ symbol, onClose, fetchScalp = fetchScalpView }: DrillDownViewProps) {
  const [timeframe, setTimeframe] = useState<Timeframe>(DEFAULT_DRILLDOWN_TIMEFRAME);
  const [view, setView] = useState<ScalpView | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    fetchScalp(symbol, timeframe)
      .then((data) => {
        if (!cancelled) setView(data);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [symbol, timeframe, fetchScalp]);

  return (
    <div data-testid="drilldown-view" role="dialog" aria-label={`${symbol} drill-down`}>
      <div className="drilldown-view__header">
        <span>{symbol}</span>
        {onClose && (
          <button type="button" onClick={onClose} data-testid="drilldown-close">
            Close
          </button>
        )}
      </div>

      <div role="group" aria-label="Drill-down timeframe" data-testid="drilldown-timeframe-toggle">
        {TIMEFRAMES.map((tf) => (
          <button
            key={tf}
            type="button"
            data-testid={`drilldown-timeframe-button-${tf}`}
            aria-pressed={tf === timeframe}
            onClick={() => setTimeframe(tf)}
          >
            {tf}
          </button>
        ))}
      </div>

      {error ? (
        <DeadDataNotice testId="drilldown-error" message={error} />
      ) : (
        <>
          {view?.chart.available ? (
            <>
              <MiniChart price={view.chart.price} sma={view.chart.sma} height={240} timeframe={view.timeframe} />
              <ChartFreshness chart={view.chart} />
            </>
          ) : (
            <DeadDataNotice
              testId="drilldown-chart-unavailable"
              reason={view?.chart.reason ?? null}
              context="timeframe"
            />
          )}

          {/* Always its own labeled timeframe (4h) — never derived from the
              chart's current zoom (AC-18). */}
          <div data-testid="scalp-rsi-reading">
            Scalp RSI ({view?.scalp_momentum.timeframe ?? "4h"}):{" "}
            {view ? `${view.scalp_momentum.state}${view.scalp_momentum.value !== null ? ` (${view.scalp_momentum.value.toFixed(1)})` : ""}` : "…"}
          </div>
        </>
      )}
    </div>
  );
}
