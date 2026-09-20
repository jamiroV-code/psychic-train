import { MiniChart } from "@/components/chart/MiniChart";
import { DeadDataNotice } from "@/components/screener/DeadDataNotice";
import { SignalDetailPanel } from "@/components/screener/SignalDetailPanel";
import { TIMEFRAMES, type CoinPanel as CoinPanelData } from "@/lib/types/screener";

export interface CoinPanelProps {
  panel: CoinPanelData;
  onOpenDrillDown?: (symbol: string) => void;
}

function formatPercent(value: number | null): string {
  if (value === null) return "N/A"; // never a 0% standing in for missing data (AC-20)
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(1)}%`;
}

export function CoinPanel({ panel, onOpenDrillDown }: CoinPanelProps) {
  return (
    <div data-testid={`coin-panel-${panel.symbol}`} className="coin-panel">
      <div className="coin-panel__header">
        <span className="coin-panel__symbol">{panel.symbol}</span>
        {onOpenDrillDown && (
          // AC-7: on-demand only — never its own tile in the overview grid,
          // just an entry point from an already-rendered panel.
          <button
            type="button"
            data-testid={`open-drilldown-${panel.symbol}`}
            onClick={() => onOpenDrillDown(panel.symbol)}
          >
            Drill down
          </button>
        )}
        {/* RFC-004 (items 62/64/66/67): the real confidence badge,
            tap-to-expand into the per-signal detail panel — replaces
            RFC-001's plain-text placeholder. */}
        <SignalDetailPanel
          confidence={panel.confidence}
          momentum={panel.momentum}
          trend={panel.trend}
          legContext={panel.leg_context}
          narrativeState={panel.narrative_state}
        />
      </div>

      {panel.chart.available ? (
        <MiniChart price={panel.chart.price} sma={panel.chart.sma} />
      ) : (
        <DeadDataNotice
          testId="chart-unavailable"
          reason={panel.chart.reason}
          context="timeframe"
          className="coin-panel__unavailable"
        />
      )}

      <div className="coin-panel__signals">
        <span data-testid="momentum-state" data-state={panel.momentum.state}>
          Momentum: {panel.momentum.state}
        </span>
        <span data-testid="trend-direction" data-state={panel.trend.direction}>
          Trend: {panel.trend.direction}
        </span>
      </div>

      {/* Amendment 2 (AC-20): a compact 5-chip row, visually distinct from
          (not merged into) the momentum PASS/FAIL badge above — a coin can
          read "in momentum" while individual short-timeframe chips are
          negative without looking contradictory. */}
      <div data-testid="gain-readout-row" className="coin-panel__gain-row">
        {TIMEFRAMES.map((tf) => (
          <span key={tf} data-testid={`gain-chip-${tf}`} className="coin-panel__gain-chip">
            <span className="coin-panel__gain-chip-label">{tf}</span>
            <span className="coin-panel__gain-chip-value">
              {formatPercent(panel.percent_change_by_timeframe[tf])}
            </span>
          </span>
        ))}
      </div>
    </div>
  );
}
