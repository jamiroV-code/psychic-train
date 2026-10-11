import { memo, type ReactNode } from "react";
import { ChartFreshness } from "@/components/chart/ChartFreshness";
import { MiniChart } from "@/components/chart/MiniChart";
import { DeadDataNotice } from "@/components/screener/DeadDataNotice";
import { formatDateTimeZone } from "@/lib/brussels-time";
import type { ChartRange } from "@/lib/island-loader";
import { formatUnavailableReason } from "@/lib/format-unavailable-reason";
import { formatRsi, rsiTitle } from "@/lib/rsi-format";
import { TIMEFRAMES, type CoinPanel as CoinPanelData, type GainChip, type Timeframe } from "@/lib/types/screener";

export interface CoinPanelProps {
  panel: CoinPanelData;
  onOpenDrillDown?: (symbol: string) => void;
  // T34 / S2: the board's timeframe, so the chart's time axis is Brussels time for it.
  timeframe?: Timeframe;
  // T44: the board's shared zoom; every small chart shows the same range.
  range?: ChartRange | null;
  onRangeChange?: (range: ChartRange | null) => void;
  // T41 / S5b: the coin's layout controls (memoised by the board), in the header.
  actions?: ReactNode;
}

function formatPercent(value: number | null): string {
  if (value === null) return "N/A"; // never a 0% standing in for missing data (AC-20)
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(1)}%`;
}

function chipTitle(tf: Timeframe, chip: GainChip | undefined): string | undefined {
  if (!chip) return undefined;
  if (chip.pct === null) return chip.reason ? formatUnavailableReason(chip.reason, "timeframe") : undefined;
  // Current candle, open to latest (T34 / S2); the open in Brussels time (T42 / S11a).
  const open = chip.open_ts ? formatDateTimeZone(new Date(chip.open_ts)) : "?";
  return `${tf} candle from ${open}${chip.is_partial ? " (forming)" : ""}`;
}

// T43 / S11b: memoised, so a refresh that leaves this coin's data the same
// object (structural sharing in the board) re-renders nothing here.
export const CoinPanel = memo(function CoinPanel({
  panel,
  onOpenDrillDown,
  timeframe,
  range,
  onRangeChange,
  actions,
}: CoinPanelProps) {
  const rsi = panel.rsi;
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
        {actions}
      </div>

      {panel.chart.available ? (
        <>
          <MiniChart
            price={panel.chart.price}
            sma={panel.chart.sma}
            timeframe={timeframe}
            range={range}
            onRangeChange={onRangeChange}
          />
          <ChartFreshness chart={panel.chart} />
        </>
      ) : (
        <DeadDataNotice
          testId="chart-unavailable"
          reason={panel.chart.reason}
          context="timeframe"
          className="coin-panel__unavailable"
        />
      )}

      {/* T41 / S5b: RSI 14 of the board timeframe. Always rendered, the same
          height for a number and for N/A, which carries its reason. */}
      <div data-testid={`rsi-readout-${panel.symbol}`} className="coin-panel__rsi-row">
        <span className="coin-panel__rsi-label">{timeframe ? `RSI 14 (${timeframe})` : "RSI 14"}</span>
        <span
          data-testid={`rsi-value-${panel.symbol}`}
          className="coin-panel__rsi-value"
          data-reason={rsi?.reason ?? undefined}
          title={rsi ? rsiTitle(rsi) : undefined}
        >
          {formatRsi(rsi?.value ?? null)}
        </span>
      </div>

      {/* Amendment 2 (AC-20): a compact 5-chip row under the chart. */}
      {/* T34 / S2: each chip is the timeframe's current candle, open to
          latest price, read from `gain_by_timeframe`; N/A carries its reason. */}
      <div data-testid="gain-readout-row" className="coin-panel__gain-row">
        {TIMEFRAMES.map((tf) => {
          const chip = panel.gain_by_timeframe?.[tf];
          return (
            <span
              key={tf}
              data-testid={`gain-chip-${tf}`}
              className="coin-panel__gain-chip"
              data-reason={chip?.reason ?? undefined}
              title={chipTitle(tf, chip)}
            >
              <span className="coin-panel__gain-chip-label">{tf}</span>
              <span className="coin-panel__gain-chip-value">{formatPercent(chip?.pct ?? null)}</span>
            </span>
          );
        })}
      </div>
    </div>
  );
});
