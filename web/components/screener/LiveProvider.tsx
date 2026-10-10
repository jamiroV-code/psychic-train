"use client";

import { createContext, useContext, useEffect, useRef, useSyncExternalStore, type ReactNode } from "react";
import { fetchRefreshStatus } from "@/lib/api/refresh";
import { LivePoller, type LiveData, type LiveStatus } from "@/lib/live-poll";
import type { RefreshStatus } from "@/lib/types/refresh";

/**
 * T43 / S11b: one live poller for the screener page, shared by a stable
 * context value. Board and drill-down refetch on `tick`, the spaghetti and
 * BTC charts on `dataVersion`, captions and the strip read the server clock.
 *
 * Without a provider nothing refetches on its own: `useLiveData` is
 * `{tick: 0, dataVersion: 0}` and `useLiveClock` is null.
 */

export interface LiveProviderProps {
  children?: ReactNode;
  // Injectable for tests; default the real API client and cadence.
  fetchStatus?: (signal: AbortSignal) => Promise<RefreshStatus>;
  intervalMs?: number;
  mono?: () => number;
}

const LiveContext = createContext<LivePoller | null>(null);

const NO_DATA: LiveData = { tick: 0, dataVersion: 0 };
const NO_STATUS: LiveStatus = { phase: "waiting", failures: 0, lastGood: null };
const NO_CLOCK = { nowMs: null };

function noSubscribe(): () => void {
  return () => {};
}

export function LiveProvider({ children, fetchStatus = fetchRefreshStatus, intervalMs, mono }: LiveProviderProps) {
  const ref = useRef<LivePoller | null>(null);
  if (ref.current === null) ref.current = new LivePoller({ fetchStatus, intervalMs, mono });
  const poller = ref.current;

  useEffect(() => {
    poller.start();
    return () => poller.stop();
  }, [poller]);

  return <LiveContext.Provider value={poller}>{children}</LiveContext.Provider>;
}

export function useLivePoller(): LivePoller | null {
  return useContext(LiveContext);
}

export function useLiveData(): LiveData {
  const poller = useContext(LiveContext);
  const get = poller ? poller.getData : () => NO_DATA;
  return useSyncExternalStore(poller ? poller.subscribe : noSubscribe, get, get);
}

export function useLiveStatus(): LiveStatus {
  const poller = useContext(LiveContext);
  const get = poller ? poller.getStatus : () => NO_STATUS;
  return useSyncExternalStore(poller ? poller.subscribe : noSubscribe, get, get);
}

/** The server clock in ms, or null with no provider or before a usable answer. */
export function useLiveClock(): number | null {
  const poller = useContext(LiveContext);
  const get = poller ? poller.getClock : () => NO_CLOCK;
  return useSyncExternalStore(poller ? poller.subscribe : noSubscribe, get, get).nowMs;
}
