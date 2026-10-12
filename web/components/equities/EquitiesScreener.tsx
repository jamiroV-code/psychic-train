"use client";

import { FreshnessStrip } from "@/components/screener/FreshnessStrip";
import { LiveProvider } from "@/components/screener/LiveProvider";
import { ScreenerBoard } from "@/components/screener/ScreenerBoard";
import { VariantProvider } from "@/components/screener/VariantProvider";
import {
  addEquity,
  fetchEquitiesBoard,
  fetchEquitiesChart,
  fetchEquitiesLayout,
  fetchEquitiesSpaghetti,
  fetchEquitiesStatus,
  removeEquity,
  saveEquitiesLayout,
} from "@/lib/api/equities";
import { EQUITIES_VARIANT } from "@/lib/screener-variant";

export const PRIVATE_USE_NOTE =
  "Private use only. Prices come from London Strategic Edge under a personal licence and are not shared or redistributed. Prices are split-adjusted only; delisted tickers have no data.";

/**
 * T47 / S9C: the equities board, the crypto board's components with the
 * equities variant and clients. One live poller re-reads the equities status
 * every 60 s; the strip says how fresh it is.
 */
export function EquitiesScreener() {
  return (
    <VariantProvider variant={EQUITIES_VARIANT}>
      <LiveProvider fetchStatus={fetchEquitiesStatus}>
        <FreshnessStrip />
        <p data-testid="equities-note">{PRIVATE_USE_NOTE}</p>
        <ScreenerBoard
          fetchBoard={fetchEquitiesBoard}
          fetchChart={fetchEquitiesChart}
          fetchSpaghetti={fetchEquitiesSpaghetti}
          fetchLayout={fetchEquitiesLayout}
          saveLayout={saveEquitiesLayout}
          addCoin={addEquity}
          removeCoin={removeEquity}
        />
      </LiveProvider>
    </VariantProvider>
  );
}
