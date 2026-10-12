import { createLayoutClient } from "@/lib/api/layout";
import { createStatusFetcher } from "@/lib/api/refresh";
import { createScreenerClient } from "@/lib/api/screener";
import { createWatchlistClient } from "@/lib/api/watchlist";

/**
 * T47 / S9C: the equities page's clients, bound once at module level so the
 * board's effects (whose deps include the fetchers) see the same functions on
 * every render. Adds send `{symbol, group_id}`; 409 and 422 map to the same
 * error classes as the crypto watchlist.
 */

export const EQUITIES_BASE = "/api/equities";
export const EQUITIES_STATUS_PATH = "/api/equities/status";

export interface EquitiesResponse {
  tickers: string[];
}

const screener = createScreenerClient(EQUITIES_BASE);
const list = createWatchlistClient<EquitiesResponse>(EQUITIES_BASE);
const layout = createLayoutClient("equities");

export const fetchEquitiesBoard = screener.fetchBoard;
export const fetchEquitiesChart = screener.fetchChart;
export const fetchEquitiesSpaghetti = screener.fetchSpaghetti;
export const addEquity = list.addCoin;
export const removeEquity = list.removeCoin;
export const fetchEquitiesLayout = layout.fetchLayout;
export const saveEquitiesLayout = layout.saveLayout;
export const fetchEquitiesStatus = createStatusFetcher(EQUITIES_STATUS_PATH);
