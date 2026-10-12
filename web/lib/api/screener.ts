import type {
  ChartView,
  ScreenerBoardResponse,
  SpaghettiResponse,
  Timeframe,
} from "@/lib/types/screener";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

const DEFAULT_TIMEOUT_MS = 10_000;

async function getJson<T>(path: string): Promise<T> {
  try {
    const res = await fetch(`${API_BASE_URL}${path}`, {
      signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS),
    });
    if (!res.ok) {
      throw new Error(`API request failed: ${path} -> ${res.status}`);
    }
    return (await res.json()) as T;
  } catch (err) {
    if (err instanceof Error && err.name === "TimeoutError") {
      throw new Error(`API request timed out after ${DEFAULT_TIMEOUT_MS}ms: ${path}`);
    }
    throw err;
  }
}

// T47 / S9C: one client per API base (`/api/screener`, `/api/equities`);
// same paths below the base, same errors and timeout.
export interface ScreenerClient {
  fetchBoard: (timeframe: Timeframe) => Promise<ScreenerBoardResponse>;
  fetchChart: (symbol: string, timeframe: Timeframe) => Promise<ChartView>;
  fetchSpaghetti: (timeframe: Timeframe) => Promise<SpaghettiResponse>;
}

export function createScreenerClient(base: string): ScreenerClient {
  return {
    fetchBoard: (timeframe) => getJson<ScreenerBoardResponse>(`${base}/board?timeframe=${timeframe}`),
    fetchChart: (symbol, timeframe) =>
      getJson<ChartView>(`${base}/${encodeURIComponent(symbol)}/chart?timeframe=${timeframe}`),
    fetchSpaghetti: (timeframe) => getJson<SpaghettiResponse>(`${base}/spaghetti?timeframe=${timeframe}`),
  };
}

const cryptoClient = createScreenerClient("/api/screener");

export function fetchScreenerBoard(timeframe: Timeframe = "1d"): Promise<ScreenerBoardResponse> {
  return cryptoClient.fetchBoard(timeframe);
}

export function fetchChartView(symbol: string, timeframe: Timeframe = "4h"): Promise<ChartView> {
  return cryptoClient.fetchChart(symbol, timeframe);
}

export function fetchSpaghetti(timeframe: Timeframe = "1d"): Promise<SpaghettiResponse> {
  return cryptoClient.fetchSpaghetti(timeframe);
}
