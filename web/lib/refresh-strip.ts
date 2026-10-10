import { dayKey, formatDay, formatTimeZone, offsetLabel, zoneAbbr } from "@/lib/brussels-time";
import { formatAge } from "@/lib/chart-freshness";
import type { LiveStatus } from "@/lib/live-poll";

/**
 * T43 / S11b: the words of the freshness strip, kept pure so every state is
 * tested here. All times are Brussels time from the server's own clock;
 * nothing here reads the browser clock.
 */

/** Overdue means more than this past the scheduled refresh (covers a running tick). */
export const OVERDUE_GRACE_SECONDS = 300;

export const STRIP_CHECKING = "Checking the server...";
export const STRIP_HELP =
  "Page checked is the last time this page got an answer from the server, by the server's clock; " +
  "it re-checks every minute while this tab is visible. Overdue means more than 5 min past the scheduled refresh time.";

export type StripState = "waiting" | "normal" | "overdue" | "failed";

export interface StripModel {
  state: StripState;
  checking: string | null;
  off: string | null;
  first: string | null;
  refreshed: string | null;
  next: string | null;
  checked: string | null;
  overdue: string | null;
  failed: string | null;
  notes: string[];
  zone: string | null;
  help: string;
}

const REASONS: Record<string, string> = {
  "SCREENER_REFRESH_WORKER=0": "switched off by SCREENER_REFRESH_WORKER=0",
  "not-started": "not running",
  "not-running": "not running",
  "start-failed": "failed to start",
};

export function offReason(reason: string | null): string {
  if (!reason) return "not running";
  return REASONS[reason] ?? reason;
}

function instant(value: string | null | undefined): number | null {
  if (!value) return null;
  const ms = Date.parse(value);
  return Number.isFinite(ms) ? ms : null;
}

/** `14:15 CEST`, with a `DD MMM ` prefix when its Brussels day is not the reference day. */
export function stripTime(ms: number | null, refMs: number | null): string {
  if (ms === null) return "n/a";
  const date = new Date(ms);
  const text = formatTimeZone(date);
  if (refMs !== null && dayKey(date) !== dayKey(new Date(refMs))) return `${formatDay(date)} ${text}`;
  return text;
}

/** Running, past its first refresh, and the server clock strictly beyond `next_tick_at` plus the grace. */
export function isOverdue(status: LiveStatus, nowMs: number | null): boolean {
  const s = status.lastGood?.status;
  if (!s || !s.running || !s.last_tick_finished || nowMs === null) return false;
  const next = instant(s.next_tick_at);
  return next !== null && nowMs > next + OVERDUE_GRACE_SECONDS * 1000;
}

export function stripModel(status: LiveStatus, nowMs: number | null): StripModel {
  const last = status.lastGood;
  const model: StripModel = {
    state: "waiting",
    checking: null,
    off: null,
    first: null,
    refreshed: null,
    next: null,
    checked: null,
    overdue: null,
    failed: null,
    notes: [],
    zone: null,
    help: STRIP_HELP,
  };

  const ref = nowMs ?? last?.serverMs ?? null;
  const time = (ms: number | null) => stripTime(ms, ref);

  if (ref !== null) {
    const at = new Date(ref);
    model.zone = `Times are Brussels time, ${zoneAbbr(at)} (${offsetLabel(at)}).`;
  }

  if (last) {
    const s = last.status;
    const finished = instant(s.last_tick_finished);
    const next = instant(s.next_tick_at);
    if (!s.running) {
      model.off = `Automatic server refresh is off (${offReason(s.disabled_reason)}). This page still re-checks every minute.`;
    } else if (finished === null) {
      model.first = `Server has not finished its first refresh. Next refresh ${time(next)}`;
    } else {
      model.next = `Next refresh ${time(next)}`;
    }
    if (finished !== null) {
      const age = nowMs !== null ? ` (${formatAge((nowMs - finished) / 1000)} ago)` : "";
      model.refreshed = `Server refreshed ${time(finished)}${age}`;
    }
    if (s.last_tick_failed > 0) {
      model.notes.push(`${s.last_tick_failed} pairs did not refresh in that run`);
    }
    if (s.backoff_seconds > 0) {
      const retry = next ?? (last.serverMs !== null ? last.serverMs + s.backoff_seconds * 1000 : null);
      model.notes.push(`Refreshes are failing; retrying about ${time(retry)}`);
    }
    model.checked = `Page checked ${time(last.serverMs)}`;
    if (isOverdue(status, nowMs)) model.overdue = `Refresh overdue: expected ${time(next)}`;
  }

  if (status.phase === "failed") {
    model.failed = `Could not check the server. Last answer from the server: ${last ? time(last.serverMs) : "n/a"}.`;
  }

  if (status.phase === "waiting" && !last) model.checking = STRIP_CHECKING;

  model.state =
    status.phase === "failed" ? "failed" : model.overdue ? "overdue" : status.phase === "waiting" ? "waiting" : "normal";
  return model;
}

/**
 * What the polite announcer says on a change of state, or null to leave it
 * as it is (a poll that changes nothing announces nothing).
 */
export function announcement(prev: StripState | null, next: StripState): string | null {
  if (prev === null || prev === next) return null;
  if (next === "failed") return "Could not check the server";
  if (next === "overdue") return "Refresh is overdue";
  if (next === "normal" && prev === "failed") return "The server answered again";
  if (next === "normal" && prev === "overdue") return "Refresh is no longer overdue";
  return null;
}
