import { expect, test } from "vitest";
import { EQUITIES_STRIP_HELP, equitiesStripModel } from "@/lib/equities-strip";
import type { LiveStatus } from "@/lib/live-poll";
import type { EquitiesStatus } from "@/lib/types/equities";

// Clock arithmetic: in October 2026 New York is on daylight time until 1 Nov,
// so the 16:00 close is 20:00Z and the refresh 20:30Z. Brussels is CEST
// (+02:00) until 25 Oct, then CET (+01:00): 22:30 CEST, then 21:30 CET.
function eq(overrides: Partial<EquitiesStatus> = {}): EquitiesStatus {
  return {
    running: true,
    disabled_reason: null,
    interval_seconds: 86400,
    last_tick_started: "2026-10-09T20:30:00Z",
    last_tick_finished: "2026-10-09T20:31:00Z",
    last_tick_ok: 3,
    last_tick_failed: 0,
    next_tick_at: "2026-10-12T20:30:00Z",
    queue_depth: 0,
    backoff_seconds: 0,
    server_time: "2026-10-09T22:00:00Z",
    last_bar_date: "2026-10-09",
    ...overrides,
  };
}

function live(status: EquitiesStatus | null, phase: LiveStatus["phase"] = "ok"): LiveStatus {
  return {
    phase,
    failures: phase === "failed" ? 1 : 0,
    lastGood: status ? { status, serverMs: Date.parse(status.server_time!) } : null,
  };
}

const at = (iso: string) => Date.parse(iso);

test("waiting: no answer yet shows the checking line and the equities help", () => {
  const model = equitiesStripModel(live(null, "waiting"), null);
  expect(model.state).toBe("waiting");
  expect(model.checking).toBe("Checking the server...");
  expect(model.lastBar).toBeNull();
  expect(model.help).toBe(EQUITIES_STRIP_HELP);
});

test("off: the switch is named in plain words", () => {
  const s = eq({ running: false, disabled_reason: "SCREENER_REFRESH_WORKER=0", next_tick_at: null });
  const model = equitiesStripModel(live(s), at("2026-10-09T22:00:00Z"));
  expect(model.off).toBe(
    "Automatic market-close refresh is off (switched off by SCREENER_REFRESH_WORKER=0). This page still re-checks every minute.",
  );
  expect(model.next).toBeNull();
  expect(model.overdue).toBeNull();
});

test("missing key: says no market data key is set", () => {
  const s = eq({ running: false, disabled_reason: "missing-key", next_tick_at: null, last_tick_finished: null });
  const model = equitiesStripModel(live(s), at("2026-10-09T22:00:00Z"));
  expect(model.off).toBe(
    "Automatic market-close refresh is off (no market data key is set on the server). This page still re-checks every minute.",
  );
  expect(model.state).toBe("normal");
});

test("Friday evening after the tick is normal with Monday's refresh next", () => {
  const model = equitiesStripModel(live(eq()), at("2026-10-09T22:00:00Z"));
  expect(model.state).toBe("normal");
  expect(model.overdue).toBeNull();
  expect(model.next).toBe("Next expected refresh Mon 12 Oct 22:30 CEST");
});

test("Saturday is not overdue", () => {
  const model = equitiesStripModel(live(eq({ server_time: "2026-10-10T18:00:00Z" })), at("2026-10-10T18:00:00Z"));
  expect(model.state).toBe("normal");
  expect(model.overdue).toBeNull();
});

test("Sunday late evening is not overdue", () => {
  const model = equitiesStripModel(live(eq({ server_time: "2026-10-11T23:00:00Z" })), at("2026-10-11T23:00:00Z"));
  expect(model.state).toBe("normal");
  expect(model.overdue).toBeNull();
});

test("a holiday Monday (Labor Day) is not overdue: the server points at Tuesday", () => {
  const s = eq({
    last_tick_started: "2026-09-04T20:30:00Z",
    last_tick_finished: "2026-09-04T20:31:00Z",
    next_tick_at: "2026-09-08T20:30:00Z",
    server_time: "2026-09-07T22:00:00Z",
    last_bar_date: "2026-09-04",
  });
  const model = equitiesStripModel(live(s), at("2026-09-07T22:00:00Z"));
  expect(model.overdue).toBeNull();
  expect(model.next).toBe("Next expected refresh Tue 08 Sep 22:30 CEST");
});

test("a weekday tick missed by more than 300 s is overdue", () => {
  const model = equitiesStripModel(live(eq({ server_time: "2026-10-12T20:35:01Z" })), at("2026-10-12T20:35:01Z"));
  expect(model.state).toBe("overdue");
  expect(model.overdue).toBe("Refresh overdue: expected 22:30 CEST");
});

test("exactly 300 s past the expected refresh is not overdue", () => {
  const model = equitiesStripModel(live(eq({ server_time: "2026-10-12T20:35:00Z" })), at("2026-10-12T20:35:00Z"));
  expect(model.state).toBe("normal");
  expect(model.overdue).toBeNull();
});

test("failed: a failed check keeps the last answer and says so", () => {
  const model = equitiesStripModel(live(eq(), "failed"), at("2026-10-09T22:00:00Z"));
  expect(model.state).toBe("failed");
  expect(model.failed).toBe("Could not check the server. Last answer from the server: 00:00 CEST.");
  expect(model.lastBar).toBe("Latest daily bar 2026-10-09");
});

test("last bar text: the date only, or a plain line when nothing is cached", () => {
  expect(equitiesStripModel(live(eq()), null).lastBar).toBe("Latest daily bar 2026-10-09");
  expect(equitiesStripModel(live(eq({ last_bar_date: null })), null).lastBar).toBe("No daily bars cached yet");
});

test("next time in Brussels: CEST, then CET in the weeks the clocks differ", () => {
  const summer = equitiesStripModel(live(eq()), at("2026-10-09T22:00:00Z"));
  expect(summer.next).toBe("Next expected refresh Mon 12 Oct 22:30 CEST");
  const s = eq({
    last_tick_finished: null,
    next_tick_at: "2026-10-26T20:30:00Z",
    server_time: "2026-10-26T09:00:00Z",
  });
  const winter = equitiesStripModel(live(s), at("2026-10-26T09:00:00Z"));
  expect(winter.first).toBe("Server has not finished its first refresh. Next expected refresh Mon 26 Oct 21:30 CET");
  expect(winter.next).toBeNull();
});

test("backoff and failed tickers are noted in plain words", () => {
  const s = eq({
    last_tick_finished: "2026-10-12T20:31:00Z",
    last_tick_ok: 0,
    last_tick_failed: 2,
    backoff_seconds: 3600,
    next_tick_at: "2026-10-12T21:31:00Z",
    server_time: "2026-10-12T20:40:00Z",
  });
  const model = equitiesStripModel(live(s), at("2026-10-12T20:40:00Z"));
  expect(model.notes).toEqual([
    "2 tickers did not refresh in that run",
    "Refreshes are failing; retrying about 23:31 CEST",
  ]);
});

test("help text explains the market-close schedule, no 15-minute proof", () => {
  const model = equitiesStripModel(live(eq()), at("2026-10-09T22:00:00Z"));
  expect(model.help).toBe(EQUITIES_STRIP_HELP);
  expect(model.help).toContain("about 30 min after the 16:00 New York close");
  expect(model.help).toContain("weekends and US market holidays have no refresh");
  expect(model.help).not.toContain("15 min");
});
