import { CAP_MESSAGE } from "@/lib/layout-state";
import { TIMEFRAMES, type Timeframe } from "@/lib/types/screener";

/**
 * T47 / S9C: what differs between the crypto screener and the equities page.
 * Text and timeframes only; the 30 cap (`MAX_COINS`, `isFull`) stays in
 * `layout-state.ts` and serves both. Read through `useVariant()`; without a
 * provider every component shows the crypto text it always had.
 */
export interface ScreenerVariant {
  id: "crypto" | "equities";
  timeframes: readonly Timeframe[];
  initialTimeframe: Timeframe;
  drillDownTimeframe: Timeframe;
  noun: string;
  nounPlural: string;
  /** Where the symbols live, as said in the empty-board line. */
  listName: string;
  capMessage: string;
  /** Daily and weekly bars carry a date, not a clock time. */
  dateOnlyBars: boolean;
}

export const CRYPTO_VARIANT: ScreenerVariant = {
  id: "crypto",
  timeframes: TIMEFRAMES,
  initialTimeframe: "1d",
  drillDownTimeframe: "4h",
  noun: "coin",
  nounPlural: "coins",
  listName: "the watchlist",
  capMessage: CAP_MESSAGE,
  dateOnlyBars: false,
};

// The server's own 409 text (api/data/equities_store.py::CAP_MESSAGE).
export const EQUITIES_CAP_MESSAGE = "Equities list is full: 30 tickers maximum. Remove a ticker to add another.";

export const EQUITIES_VARIANT: ScreenerVariant = {
  id: "equities",
  timeframes: ["1d", "1w"],
  initialTimeframe: "1d",
  drillDownTimeframe: "1d",
  noun: "ticker",
  nounPlural: "tickers",
  listName: "the equities list",
  capMessage: EQUITIES_CAP_MESSAGE,
  dateOnlyBars: true,
};

/** `1 coin`, `3 coins` (or tickers). */
export function countText(variant: ScreenerVariant, count: number): string {
  return count === 1 ? `1 ${variant.noun}` : `${count} ${variant.nounPlural}`;
}
