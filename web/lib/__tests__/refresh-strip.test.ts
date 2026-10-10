import { describe, expect, it } from "vitest";
import type { LiveStatus } from "@/lib/live-poll";
import { announcement, isOverdue, STRIP_CHECKING, STRIP_HELP, stripModel, type StripModel } from "@/lib/refresh-strip";
import type { RefreshStatus } from "@/lib/types/refresh";

// Expected strings come from clock arithmetic: 2026-10-03 is summer time
// (+02:00) and summer time ends 2026-10-25T01:00Z (last Sunday of October).
const T = (iso: string) => Date.parse(iso);

function status(overrides: Partial<RefreshStatus> = {}): RefreshStatus {
  return {
    running: true,
    disabled_reason: null,
    interval_seconds: 900,
    last_tick_started: "2026-10-03T12:14:00Z",
    last_tick_finished: "2026-10-03T12:15:00Z",
    last_tick_ok: 10,
    last_tick_failed: 0,
    next_tick_at: "2026-10-03T12:30:00Z",
    queue_depth: 0,
    backoff_seconds: 0,
    server_time: "2026-10-03T12:17:00Z",
    ...overrides,
  };
}

function live(s: RefreshStatus | null, phase: LiveStatus["phase"] = "ok", serverMs?: number | null): LiveStatus {
  return {
    phase,
    failures: phase === "failed" ? 1 : 0,
    lastGood: s ? { status: s, serverMs: serverMs !== undefined ? serverMs : s.server_time ? T(s.server_time) : null } : null,
  };
}

function strings(model: StripModel): string[] {
  return Object.values(model)
    .flat()
    .filter((v): v is string => typeof v === "string");
}

describe("refresh-strip", () => {
  it("waiting: Checking the server, and a null server_time prints Page checked n/a with no age", () => {
    const waiting = stripModel({ phase: "waiting", failures: 0, lastGood: null }, null);
    expect(waiting.state).toBe("waiting");
    expect(waiting.checking).toBe(STRIP_CHECKING);
    expect(waiting.checking).toBe("Checking the server...");
    expect(waiting.help).toBe(STRIP_HELP);

    const clockless = stripModel(live(status({ server_time: null })), null);
    expect(clockless.checking).toBeNull();
    expect(clockless.checked).toBe("Page checked n/a");
    expect(clockless.refreshed).toBe("Server refreshed 14:15 CEST");
  });

  it("worker off: each reason in plain words", () => {
    const off = (reason: string | null) =>
      stripModel(live(status({ running: false, disabled_reason: reason })), T("2026-10-03T12:18:00Z")).off;
    const tail = "This page still re-checks every minute.";
    expect(off("SCREENER_REFRESH_WORKER=0")).toBe(
      `Automatic server refresh is off (switched off by SCREENER_REFRESH_WORKER=0). ${tail}`,
    );
    expect(off("not-started")).toBe(`Automatic server refresh is off (not running). ${tail}`);
    expect(off("not-running")).toBe(`Automatic server refresh is off (not running). ${tail}`);
    expect(off("start-failed")).toBe(`Automatic server refresh is off (failed to start). ${tail}`);
    expect(off("stopped")).toBe(`Automatic server refresh is off (stopped). ${tail}`);
    expect(off("something-else")).toBe(`Automatic server refresh is off (something-else). ${tail}`);
  });

  it("first refresh pending", () => {
    const model = stripModel(live(status({ last_tick_finished: null })), T("2026-10-03T12:18:00Z"));
    expect(model.first).toBe("Server has not finished its first refresh. Next refresh 14:30 CEST");
    expect(model.refreshed).toBeNull();
    expect(model.next).toBeNull();
  });

  it("ok lines golden, 3 min ago", () => {
    const model = stripModel(live(status()), T("2026-10-03T12:18:00Z"));
    expect(model.state).toBe("normal");
    expect(model.refreshed).toBe("Server refreshed 14:15 CEST (3 min ago)");
    expect(model.next).toBe("Next refresh 14:30 CEST");
    expect(model.checked).toBe("Page checked 14:17 CEST");
    expect(model.zone).toBe("Times are Brussels time, CEST (+02:00).");
    expect(model.overdue).toBeNull();
    expect(model.failed).toBeNull();
    expect(model.notes).toEqual([]);
  });

  it("overdue is false at next_tick_at + 300 s and true at + 301 s", () => {
    const s = live(status());
    expect(isOverdue(s, T("2026-10-03T12:35:00Z"))).toBe(false);
    expect(isOverdue(s, T("2026-10-03T12:35:01Z"))).toBe(true);
    const model = stripModel(s, T("2026-10-03T12:35:01Z"));
    expect(model.state).toBe("overdue");
    expect(model.overdue).toBe("Refresh overdue: expected 14:30 CEST");
  });

  it("never overdue when the worker is off or before the first refresh", () => {
    const late = T("2026-10-03T14:00:00Z");
    expect(isOverdue(live(status({ running: false, disabled_reason: "stopped" })), late)).toBe(false);
    expect(isOverdue(live(status({ last_tick_finished: null })), late)).toBe(false);
    expect(isOverdue(live(status()), null)).toBe(false);
  });

  it("day prefix and CET after 2026-10-25T01:00Z", () => {
    const s = status({
      last_tick_finished: "2026-10-25T00:50:00Z", // 25 Oct 02:50 CEST, before the switch
      next_tick_at: "2026-10-25T01:05:00Z", // 25 Oct 02:05 CET
      server_time: "2026-10-25T01:02:00Z", // 25 Oct 02:02 CET
    });
    const model = stripModel(live(s), T("2026-10-25T01:02:00Z"));
    expect(model.refreshed).toBe("Server refreshed 02:50 CEST (12 min ago)");
    expect(model.next).toBe("Next refresh 02:05 CET");
    expect(model.checked).toBe("Page checked 02:02 CET");
    expect(model.zone).toBe("Times are Brussels time, CET (+01:00).");

    // A refresh on the Brussels day before the server clock gets a prefix.
    const prior = stripModel(live(status({ last_tick_finished: "2026-10-02T21:50:00Z" })), T("2026-10-03T12:18:00Z"));
    expect(prior.refreshed).toBe("Server refreshed 02 Oct 23:50 CEST (14 h ago)");
  });

  it("backoff and failed-pair copy", () => {
    const model = stripModel(live(status({ last_tick_failed: 3, backoff_seconds: 1800 })), T("2026-10-03T12:18:00Z"));
    expect(model.notes).toEqual(["3 pairs did not refresh in that run", "Refreshes are failing; retrying about 14:30 CEST"]);
  });

  it("a failed check keeps the last items", () => {
    const model = stripModel(live(status(), "failed"), T("2026-10-03T12:19:00Z"));
    expect(model.state).toBe("failed");
    expect(model.failed).toBe("Could not check the server. Last answer from the server: 14:17 CEST.");
    expect(model.refreshed).toBe("Server refreshed 14:15 CEST (4 min ago)");
    expect(model.next).toBe("Next refresh 14:30 CEST");
    expect(model.checked).toBe("Page checked 14:17 CEST");

    expect(announcement("normal", "failed")).toBe("Could not check the server");
    expect(announcement("failed", "normal")).toBe("The server answered again");
    expect(announcement("normal", "overdue")).toBe("Refresh is overdue");
    expect(announcement("overdue", "normal")).toBe("Refresh is no longer overdue");
    expect(announcement("normal", "normal")).toBeNull();
    expect(announcement(null, "normal")).toBeNull();
    expect(announcement("waiting", "normal")).toBeNull();
  });

  it("no verdict word and no zone word of the data's own clock in any string", () => {
    const now = T("2026-10-03T12:40:00Z");
    const models = [
      stripModel({ phase: "waiting", failures: 0, lastGood: null }, null),
      stripModel(live(status()), now),
      stripModel(live(status(), "failed"), now),
      stripModel(live(status({ running: false, disabled_reason: "start-failed" })), now),
      stripModel(live(status({ last_tick_finished: null, last_tick_failed: 2, backoff_seconds: 60 })), now),
    ];
    const verdict =
      /\b(bullish|bearish|bull|bear|buy|sell|overbought|oversold|confidence|(out|under)perform(ing)?|risk-(on|off)|favorable|healthy|unhealthy|degraded|broken|good|bad|alert|badge|verdict|score|rating|momentum|trend|benchmark|narrative)\b/i;
    for (const text of models.flatMap(strings)) {
      expect(text).not.toMatch(verdict);
      expect(text).not.toMatch(/\bUTC\b/);
    }
  });
});
