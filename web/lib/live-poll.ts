import type { RefreshStatus } from "@/lib/types/refresh";

/**
 * T43 / S11b: the page's quiet check of the server, every minute while the
 * tab is visible. Pure: no React, and the constructor touches neither
 * `document` nor `window`, so it is safe to build during a server render.
 *
 * One check runs at `start()`, the next `intervalMs` after the previous one
 * SETTLES (a `setTimeout` chain, so two checks never overlap). Each check is
 * aborted after `timeoutMs`. Consecutive failures stretch the wait to
 * `min(intervalMs * 2^n, 300 s)`; a success resets it. A hidden tab cancels
 * the timer and any check in flight; turning visible runs one check at once.
 * An abort from `stop()` or a hidden tab is neither a failure nor a settled
 * check: no snapshot moves.
 *
 * Three snapshots for `useSyncExternalStore`, each the same object until
 * something in it changes:
 *   data   `{tick, dataVersion}`: `tick` rises after every settled check but
 *          the first (the baseline); `dataVersion` rises when the worker's
 *          `running`, `last_tick_started` or `last_tick_finished` differ from
 *          the previous success, and on every success while it is not running.
 *   status `{phase, failures, lastGood}`: the last status and its server instant.
 *   clock  `{nowMs}`: the server clock, `lastGood.serverMs` plus the monotonic
 *          time since that answer; null until an answer carried a usable clock.
 */

export const POLL_INTERVAL_MS = 60_000;
export const CHECK_TIMEOUT_MS = 10_000;
export const MAX_WAIT_MS = 300_000;
export const CLOCK_TICK_MS = 30_000;

export interface LiveData {
  tick: number;
  dataVersion: number;
}

export type LivePhase = "waiting" | "ok" | "failed";

export interface LastGood {
  status: RefreshStatus;
  /** The server's instant for that answer, or null if it never sent a usable one. */
  serverMs: number | null;
}

export interface LiveStatus {
  phase: LivePhase;
  failures: number;
  lastGood: LastGood | null;
}

export interface LiveClock {
  nowMs: number | null;
}

export interface LivePollerOptions {
  fetchStatus: (signal: AbortSignal) => Promise<RefreshStatus>;
  intervalMs?: number;
  timeoutMs?: number;
  mono?: () => number;
}

interface InFlight {
  controller: AbortController;
  timeoutId: ReturnType<typeof setTimeout>;
}

function parseInstant(value: string | null | undefined): number | null {
  if (!value) return null;
  const ms = Date.parse(value);
  return Number.isFinite(ms) ? ms : null;
}

function defaultMono(): number {
  return performance.now();
}

export class LivePoller {
  private readonly fetchStatus: LivePollerOptions["fetchStatus"];
  private readonly intervalMs: number;
  private readonly timeoutMs: number;
  private readonly mono: () => number;

  private running = false;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private clockTimer: ReturnType<typeof setInterval> | null = null;
  private inflight: InFlight | null = null;
  private settled = 0;
  private sync: { serverMs: number; monoMs: number } | null = null;
  private listeners = new Set<() => void>();

  private data: LiveData = { tick: 0, dataVersion: 0 };
  private status: LiveStatus = { phase: "waiting", failures: 0, lastGood: null };
  private clock: LiveClock = { nowMs: null };

  constructor(options: LivePollerOptions) {
    this.fetchStatus = options.fetchStatus;
    this.intervalMs = options.intervalMs ?? POLL_INTERVAL_MS;
    this.timeoutMs = options.timeoutMs ?? CHECK_TIMEOUT_MS;
    this.mono = options.mono ?? defaultMono;
  }

  // ---- store surface (arrow properties: stable, safe to pass around) ------

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };

  getData = (): LiveData => this.data;
  getStatus = (): LiveStatus => this.status;
  getClock = (): LiveClock => this.clock;

  /** The server clock now, or null before any answer carried one. */
  serverNowMs(): number | null {
    if (!this.sync) return null;
    return this.sync.serverMs + (this.mono() - this.sync.monoMs);
  }

  // ---- lifecycle ------------------------------------------------------------

  /** Idempotent, and restartable after `stop()` (StrictMode runs effects twice). */
  start(): void {
    if (this.running) return;
    this.running = true;
    if (typeof document !== "undefined") {
      document.addEventListener("visibilitychange", this.onVisibility);
    }
    if (this.isVisible()) this.resume();
  }

  stop(): void {
    if (!this.running) return;
    this.running = false;
    if (typeof document !== "undefined") {
      document.removeEventListener("visibilitychange", this.onVisibility);
    }
    this.pause();
  }

  /** Run a check now unless one is in flight; the pending timer, if any, is replaced. */
  checkNow(): void {
    if (!this.running || !this.isVisible() || this.inflight) return;
    this.clearTimer();
    void this.runCheck();
  }

  // ---- internals ------------------------------------------------------------

  private isVisible(): boolean {
    return typeof document === "undefined" || document.visibilityState !== "hidden";
  }

  private onVisibility = (): void => {
    if (!this.running) return;
    if (this.isVisible()) this.resume();
    else this.pause();
  };

  private resume(): void {
    this.refreshClock();
    if (this.clockTimer === null) {
      this.clockTimer = setInterval(() => this.refreshClock(), CLOCK_TICK_MS);
    }
    this.checkNow();
  }

  /** Cancel the timer, the clock ticker and any check in flight; no snapshot moves. */
  private pause(): void {
    this.clearTimer();
    if (this.clockTimer !== null) {
      clearInterval(this.clockTimer);
      this.clockTimer = null;
    }
    const inflight = this.inflight;
    if (inflight) {
      this.inflight = null;
      clearTimeout(inflight.timeoutId);
      inflight.controller.abort();
    }
  }

  private clearTimer(): void {
    if (this.timer !== null) {
      clearTimeout(this.timer);
      this.timer = null;
    }
  }

  private schedule(delayMs: number): void {
    this.clearTimer();
    this.timer = setTimeout(() => {
      this.timer = null;
      void this.runCheck();
    }, delayMs);
  }

  private async runCheck(): Promise<void> {
    if (this.inflight) return;
    const controller = new AbortController();
    let timedOut = false;
    const timeoutId = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, this.timeoutMs);
    const token: InFlight = { controller, timeoutId };
    this.inflight = token;

    let result: RefreshStatus | null = null;
    try {
      // Raced against the abort, so a fetch that ignores its signal still
      // settles at the timeout instead of blocking every later check.
      result = await new Promise<RefreshStatus>((resolve, reject) => {
        controller.signal.addEventListener("abort", () => reject(new Error("aborted")), { once: true });
        this.fetchStatus(controller.signal).then(resolve, reject);
      });
    } catch {
      result = null;
    }

    // Cancelled by stop() or a hidden tab: not a failure, not a settled check.
    if (this.inflight !== token) return;
    this.inflight = null;
    clearTimeout(timeoutId);

    if (result !== null && !timedOut) this.onSuccess(result);
    else this.onFailure();

    this.settled += 1;
    if (this.settled > 1) {
      this.data = { ...this.data, tick: this.data.tick + 1 };
    }
    this.emit();

    const failures = this.status.failures;
    this.schedule(failures > 0 ? Math.min(this.intervalMs * 2 ** failures, MAX_WAIT_MS) : this.intervalMs);
  }

  private onSuccess(next: RefreshStatus): void {
    const prev = this.status.lastGood;
    const serverMs = parseInstant(next.server_time);
    if (serverMs !== null) this.sync = { serverMs, monoMs: this.mono() };

    // The first settled check is the baseline: whatever the page fetched at
    // mount is already current, so nothing refetches for it.
    if (this.settled > 0) {
      const changed =
        prev === null ||
        prev.status.running !== next.running ||
        prev.status.last_tick_started !== next.last_tick_started ||
        prev.status.last_tick_finished !== next.last_tick_finished;
      if (changed || !next.running) {
        this.data = { ...this.data, dataVersion: this.data.dataVersion + 1 };
      }
    }

    this.status = {
      phase: "ok",
      failures: 0,
      lastGood: { status: next, serverMs: serverMs ?? prev?.serverMs ?? null },
    };
    this.refreshClock(false);
  }

  private onFailure(): void {
    this.status = { phase: "failed", failures: this.status.failures + 1, lastGood: this.status.lastGood };
  }

  private refreshClock(notify = true): void {
    const nowMs = this.serverNowMs();
    if (nowMs === this.clock.nowMs) return;
    this.clock = { nowMs };
    if (notify) this.emit();
  }

  private emit(): void {
    for (const listener of [...this.listeners]) listener();
  }
}
