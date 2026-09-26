import type { OnchainChainsResponse, OnchainGrowthResponse, OnchainMetric } from "@/lib/types/onchain";

// Same getJson pattern as lib/api/screener.ts (base URL fallback, 10 s
// timeout, readable errors). Kept separate so regime.ts stays untouched.
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

/**
 * GET /api/onchain/growth. `start` (YYYY-MM-DD) is the comparison rebase date;
 * omitted = the API default (latest date - 365 days). The rebase is computed in
 * Python: the page re-fetches rather than rebasing in TypeScript.
 */
export function fetchOnchainGrowth(metric: OnchainMetric, start?: string): Promise<OnchainGrowthResponse> {
  const params = new URLSearchParams({ metric });
  if (start) params.set("start", start);
  return getJson<OnchainGrowthResponse>(`/api/onchain/growth?${params.toString()}`);
}

/** GET /api/onchain/chains. */
export function fetchOnchainChains(): Promise<OnchainChainsResponse> {
  return getJson<OnchainChainsResponse>("/api/onchain/chains");
}
