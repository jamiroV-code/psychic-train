// Client for GET /api/symbols/suggest: symbol and name suggestions for the add boxes.

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
const TIMEOUT_MS = 5_000;

export type SuggestKind = "coin" | "ticker";

export interface Suggestion {
  symbol: string;
  name: string;
  /** Where the symbol can be charted: Hyperliquid, gate, mexc, kucoin, bitfinex, bigone. */
  venues: string[];
}

export interface SuggestResult {
  /** False while the server is still building its index (first start); suggestions may be partial. */
  ready: boolean;
  suggestions: Suggestion[];
}

export type SuggestFn = (kind: SuggestKind, query: string, signal?: AbortSignal) => Promise<SuggestResult>;

/** Rejects on network failure or a non-2xx answer; the caller decides what a failure looks like. */
export const fetchSuggestions: SuggestFn = async (kind, query, signal) => {
  const url = `${API_BASE_URL}/api/symbols/suggest?kind=${kind}&q=${encodeURIComponent(query)}&limit=8`;
  const timeout = AbortSignal.timeout(TIMEOUT_MS);
  const res = await fetch(url, { signal: signal ? AbortSignal.any([signal, timeout]) : timeout });
  if (!res.ok) throw new Error(`API request failed: /api/symbols/suggest -> ${res.status}`);
  return (await res.json()) as SuggestResult;
};
