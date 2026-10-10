import type { RefreshStatus } from "@/lib/types/refresh";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export const REFRESH_STATUS_PATH = "/api/refresh/status";

/**
 * T43 / S11b: one check of the server's refresh status. The caller (the live
 * poller) owns the abort and the timeout, so this takes its signal and adds
 * neither; a non-OK answer throws an error naming the status.
 */
export async function fetchRefreshStatus(signal?: AbortSignal): Promise<RefreshStatus> {
  const res = await fetch(`${API_BASE_URL}${REFRESH_STATUS_PATH}`, { signal, cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Refresh status request failed: ${REFRESH_STATUS_PATH} -> ${res.status}`);
  }
  return (await res.json()) as RefreshStatus;
}
