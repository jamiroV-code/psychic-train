import type { RefreshStatus } from "@/lib/types/refresh";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export const REFRESH_STATUS_PATH = "/api/refresh/status";

/**
 * T47 / S9C: a status fetcher for one path (`/api/refresh/status`,
 * `/api/equities/status`, same JSON keys).
 *
 * T43 / S11b: one check of the server's refresh status. The caller (the live
 * poller) owns the abort and the timeout, so this takes its signal and adds
 * neither; a non-OK answer throws an error naming the status.
 */
export function createStatusFetcher(path: string): (signal?: AbortSignal) => Promise<RefreshStatus> {
  return async (signal) => {
    const res = await fetch(`${API_BASE_URL}${path}`, { signal, cache: "no-store" });
    if (!res.ok) {
      throw new Error(`Refresh status request failed: ${path} -> ${res.status}`);
    }
    return (await res.json()) as RefreshStatus;
  };
}

const cryptoClient = createStatusFetcher(REFRESH_STATUS_PATH);

export async function fetchRefreshStatus(signal?: AbortSignal): Promise<RefreshStatus> {
  return cryptoClient(signal);
}
