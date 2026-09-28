import type { NarrativeHistoryResponse, NarrativeMomentumResponse } from "@/lib/types/narrative";

// Same getJson pattern as lib/api/regime.ts (base URL fallback, 10 s
// timeout, readable errors). Kept separate so regime/screener stay untouched.
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

export interface NarrativeHistoryQuery {
  categories?: string[];
  start?: string;
  end?: string;
}

/** GET /api/narrative/history — full history of every category unless narrowed. */
export function fetchNarrativeHistory(query: NarrativeHistoryQuery = {}): Promise<NarrativeHistoryResponse> {
  const params = new URLSearchParams();
  if (query.categories && query.categories.length > 0) params.set("categories", query.categories.join(","));
  if (query.start) params.set("start", query.start);
  if (query.end) params.set("end", query.end);
  const qs = params.toString();
  return getJson<NarrativeHistoryResponse>(`/api/narrative/history${qs ? `?${qs}` : ""}`);
}

/** GET /api/narrative/momentum — narratives ranked vs each other on recent change (RFC-4). */
export function fetchNarrativeMomentum(): Promise<NarrativeMomentumResponse> {
  return getJson<NarrativeMomentumResponse>("/api/narrative/momentum");
}
