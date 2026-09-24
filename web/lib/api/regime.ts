import type { RegimeComponentsResponse } from "@/lib/types/regime";

// Same getJson pattern as lib/api/screener.ts (base URL fallback, 10 s
// timeout, readable errors). Kept separate so screener.ts stays untouched.
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

/** GET /api/regime/components — full history unless start/end (YYYY-MM-DD) given. */
export function fetchRegimeComponents(start?: string, end?: string): Promise<RegimeComponentsResponse> {
  const params = new URLSearchParams();
  if (start) params.set("start", start);
  if (end) params.set("end", end);
  const query = params.toString();
  return getJson<RegimeComponentsResponse>(`/api/regime/components${query ? `?${query}` : ""}`);
}
