import type {
  ChartView,
  RelativePerformanceResponse,
  RelativePerformanceTimeframe,
  ScreenerBoardResponse,
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

export function fetchScreenerBoard(timeframe: Timeframe = "1d"): Promise<ScreenerBoardResponse> {
  return getJson<ScreenerBoardResponse>(`/api/screener/board?timeframe=${timeframe}`);
}

export function fetchChartView(symbol: string, timeframe: Timeframe = "4h"): Promise<ChartView> {
  return getJson<ChartView>(`/api/screener/${encodeURIComponent(symbol)}/chart?timeframe=${timeframe}`);
}

export function fetchRelativePerformance(
  timeframe: RelativePerformanceTimeframe = "30d"
): Promise<RelativePerformanceResponse> {
  return getJson<RelativePerformanceResponse>(`/api/screener/relative-performance?timeframe=${timeframe}`);
}
