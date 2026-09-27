import type { PairDetailResponse, PairsResponse } from "@/lib/types/pairs";

// Same getJson pattern as lib/api/regime.ts (base URL fallback, 10 s timeout,
// readable errors). Kept separate so regime.ts/screener.ts stay untouched.
// Difference: a non-2xx response keeps the API's `detail` text (404 unknown
// ticker, 422 self-pair) so the detail view can show why, not just a code.
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

const DEFAULT_TIMEOUT_MS = 10_000;

async function getJson<T>(path: string): Promise<T> {
  try {
    const res = await fetch(`${API_BASE_URL}${path}`, {
      signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS),
    });
    if (!res.ok) {
      let detail = "";
      try {
        const body = (await res.json()) as { detail?: unknown };
        if (typeof body.detail === "string") detail = `: ${body.detail}`;
      } catch {
        // Body was not JSON — keep the status code alone.
      }
      throw new Error(`API request failed: ${path} -> ${res.status}${detail}`);
    }
    return (await res.json()) as T;
  } catch (err) {
    if (err instanceof Error && err.name === "TimeoutError") {
      throw new Error(`API request timed out after ${DEFAULT_TIMEOUT_MS}ms: ${path}`);
    }
    throw err;
  }
}

/** GET /api/pairs — the full current universe's pairs. */
export function fetchPairs(): Promise<PairsResponse> {
  return getJson<PairsResponse>("/api/pairs");
}

/** GET /api/pairs/{a}/{b} — one pair with both EG directions and the spread. */
export function fetchPairDetail(a: string, b: string): Promise<PairDetailResponse> {
  return getJson<PairDetailResponse>(`/api/pairs/${encodeURIComponent(a)}/${encodeURIComponent(b)}`);
}
