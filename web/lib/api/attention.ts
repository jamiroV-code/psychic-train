import type { AttentionResponse, AttentionWindow } from "@/lib/types/attention";

// Same getJson pattern as lib/api/narrative.ts.
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

/** GET /api/narrative/baskets/attention */
export function fetchBasketAttention(window: AttentionWindow = 30): Promise<AttentionResponse> {
  return getJson<AttentionResponse>(`/api/narrative/baskets/attention?window=${window}`);
}
