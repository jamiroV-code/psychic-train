import type {
  DiscoveryCategoryHistory,
  DiscoveryCoinHistory,
  DiscoveryPrice,
  DiscoveryResponse,
  DiscoverySourcesResponse,
  DiscoveryWindow,
} from "@/lib/types/discovery";

// Same getJson pattern as the other lib/api clients.
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

/** GET /api/narrative/discovery */
export function fetchDiscovery(window: DiscoveryWindow = 30): Promise<DiscoveryResponse> {
  return getJson<DiscoveryResponse>(`/api/narrative/discovery?window=${window}`);
}

/** GET /api/narrative/discovery/history for one coin. */
export function fetchCoinHistory(symbol: string, window: DiscoveryWindow = 30): Promise<DiscoveryCoinHistory> {
  return getJson<DiscoveryCoinHistory>(
    `/api/narrative/discovery/history?symbol=${encodeURIComponent(symbol)}&window=${window}`,
  );
}

/** GET /api/narrative/discovery/history for one category aggregate. */
export function fetchCategoryHistory(id: string, window: DiscoveryWindow = 30): Promise<DiscoveryCategoryHistory> {
  return getJson<DiscoveryCategoryHistory>(
    `/api/narrative/discovery/history?category=${encodeURIComponent(id)}&window=${window}`,
  );
}

/** GET /api/narrative/discovery/price: daily closes from the local cache. */
export function fetchDiscoveryPrice(symbol: string, window: DiscoveryWindow = 30): Promise<DiscoveryPrice> {
  return getJson<DiscoveryPrice>(`/api/narrative/discovery/price?symbol=${encodeURIComponent(symbol)}&window=${window}`);
}

/** GET /api/narrative/sources: what each Discovery input has stored. */
export function fetchDiscoverySources(): Promise<DiscoverySourcesResponse> {
  return getJson<DiscoverySourcesResponse>("/api/narrative/sources");
}
