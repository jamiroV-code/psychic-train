"use client";

import { useEffect, useState } from "react";
import { CoinPanel } from "@/components/screener/CoinPanel";
import { DrillDownView } from "@/components/screener/DrillDownView";
import { fetchScalpView, fetchScreenerBoard } from "@/lib/api/screener";
import { TIMEFRAMES, type ScalpView, type ScreenerBoardResponse, type Timeframe } from "@/lib/types/screener";

export interface ScreenerBoardProps {
  // Injectable for tests (avoids requiring a real fetch/network layer);
  // defaults to the real API client in the app.
  fetchBoard?: (timeframe: Timeframe) => Promise<ScreenerBoardResponse>;
  fetchScalp?: (symbol: string, timeframe: Timeframe) => Promise<ScalpView>;
  initialTimeframe?: Timeframe;
}

export function ScreenerBoard({
  fetchBoard = fetchScreenerBoard,
  fetchScalp = fetchScalpView,
  initialTimeframe = "1d",
}: ScreenerBoardProps) {
  // Amendment 2 (AC-16): ONE global timeframe control lifted here, passed
  // down to every CoinPanel/MiniChart — not an independent per-panel toggle.
  const [timeframe, setTimeframe] = useState<Timeframe>(initialTimeframe);
  const [board, setBoard] = useState<ScreenerBoardResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [drillDownSymbol, setDrillDownSymbol] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchBoard(timeframe)
      .then((data) => {
        if (!cancelled) setBoard(data);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [timeframe, fetchBoard]);

  return (
    <section data-testid="screener-board" aria-label="Screener board">
      <div className="screener-board__toolbar">
        <span className="screener-board__benchmark" data-testid="active-benchmark">
          Benchmark: {board?.active_benchmark.active ?? "…"}
        </span>
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

      {/* On-demand only (AC-7) — never rendered as part of the grid above. */}
      {drillDownSymbol && (
        <DrillDownView
          symbol={drillDownSymbol}
          onClose={() => setDrillDownSymbol(null)}
          fetchScalp={fetchScalp}
        />
      )}
    </section>
  );
}
