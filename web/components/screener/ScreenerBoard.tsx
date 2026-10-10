"use client";

import { useEffect, useState } from "react";
import { CoinPanel } from "@/components/screener/CoinPanel";
import { DrillDownView } from "@/components/screener/DrillDownView";
import { useLiveData } from "@/components/screener/LiveProvider";
import { SpaghettiChart } from "@/components/screener/SpaghettiChart";
import { fetchChartView, fetchScreenerBoard, fetchSpaghetti as fetchSpaghettiDefault } from "@/lib/api/screener";
import { shareStructure, VOLATILE } from "@/lib/same-data";
import {
  TIMEFRAMES,
  type ChartView,
  type ScreenerBoardResponse,
  type SpaghettiResponse,
  type Timeframe,
} from "@/lib/types/screener";

export interface ScreenerBoardProps {
  // Injectable for tests (avoids requiring a real fetch/network layer);
  // defaults to the real API client in the app.
  fetchBoard?: (timeframe: Timeframe) => Promise<ScreenerBoardResponse>;
  fetchChart?: (symbol: string, timeframe: Timeframe) => Promise<ChartView>;
  // T37 / S6: the spaghetti chart below the grid follows the board timeframe.
  fetchSpaghetti?: (timeframe: Timeframe) => Promise<SpaghettiResponse>;
  initialTimeframe?: Timeframe;
}

export function ScreenerBoard({
  fetchBoard = fetchScreenerBoard,
  fetchChart = fetchChartView,
  fetchSpaghetti = fetchSpaghettiDefault,
  initialTimeframe = "1d",
}: ScreenerBoardProps) {
  // Amendment 2 (AC-16): ONE global timeframe control lifted here, passed
  // down to every CoinPanel/MiniChart — not an independent per-panel toggle.
  const [timeframe, setTimeframe] = useState<Timeframe>(initialTimeframe);
  const [board, setBoard] = useState<ScreenerBoardResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [drillDownSymbol, setDrillDownSymbol] = useState<string | null>(null);

  // T43 / S11b: every live check (`tick`) refetches the CURRENT timeframe.
  // A coin whose data is the same keeps the same object (structural sharing),
  // so its panel and chart are not touched; a failure keeps the panels and
  // shows the error, the next success clears it. The cancelled flag drops an
  // answer for a timeframe no longer selected.
  const { tick } = useLiveData();

  useEffect(() => {
    let cancelled = false;
    fetchBoard(timeframe)
      .then((data) => {
        if (cancelled) return;
        setBoard((prev) => shareStructure(prev, data, VOLATILE));
        setError(null);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [timeframe, fetchBoard, tick]);

  return (
    <section data-testid="screener-board" aria-label="Screener board">
      <div className="screener-board__toolbar">
        <div role="group" aria-label="Board timeframe" data-testid="timeframe-toggle">
          {TIMEFRAMES.map((tf) => (
            <button
              key={tf}
              type="button"
              data-testid={`timeframe-button-${tf}`}
              aria-pressed={tf === timeframe}
              onClick={() => setTimeframe(tf)}
            >
              {tf}
            </button>
          ))}
        </div>
      </div>

      {error && <div data-testid="board-error">{error}</div>}

      <div className="screener-board__grid" data-testid="screener-board-grid">
        {board?.coins.map((panel) => (
          <CoinPanel
            key={panel.symbol}
            panel={panel}
            onOpenDrillDown={setDrillDownSymbol}
            timeframe={board.timeframe}
          />
        ))}
      </div>

      <SpaghettiChart timeframe={timeframe} fetchSpaghetti={fetchSpaghetti} />

      {/* On-demand only (AC-7) — never rendered as part of the grid above. */}
      {drillDownSymbol && (
        <DrillDownView
          key={drillDownSymbol}
          symbol={drillDownSymbol}
          onClose={() => setDrillDownSymbol(null)}
          fetchChart={fetchChart}
        />
      )}
    </section>
  );
}
