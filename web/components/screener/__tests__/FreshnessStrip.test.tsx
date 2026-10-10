import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FreshnessStrip } from "@/components/screener/FreshnessStrip";
import { LiveProvider } from "@/components/screener/LiveProvider";
import type { RefreshStatus } from "@/lib/types/refresh";

// Expected strings come from clock arithmetic: 2026-10-03 is summer time
// (+02:00); summer time ends 2026-10-25T01:00Z (last Sunday of October).
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
    server_time: "2026-10-03T12:18:00Z",
    ...overrides,
  };
}

const HELP =
  "Page checked is the last time this page got an answer from the server, by the server's clock; " +
  "it re-checks every minute while this tab is visible. Overdue means more than 5 min past the scheduled refresh time.";

let monoNow = 0;
const mono = () => monoNow;

/** Renders the strip; each check takes the next answer (an Error fails it). */
function renderStrip(answers: (RefreshStatus | Error)[], intervalMs?: number) {
  const queue = [...answers];
  let last: RefreshStatus | Error = answers[0];
  const fetchStatus = vi.fn(async () => {
    if (queue.length > 0) last = queue.shift()!;
    if (last instanceof Error) throw last;
    return last;
  });
  render(
    <LiveProvider fetchStatus={fetchStatus} mono={mono} intervalMs={intervalMs}>
      <FreshnessStrip />
    </LiveProvider>,
  );
  return fetchStatus;
}

async function advance(ms: number) {
  await act(async () => {
    monoNow += ms;
    await vi.advanceTimersByTimeAsync(ms);
  });
}

const text = (id: string) => screen.getByTestId(id).textContent;

beforeEach(() => {
  vi.useFakeTimers();
  monoNow = 0;
});

afterEach(() => {
  vi.useRealTimers();
});

describe("FreshnessStrip", () => {
  it("ok golden with testids, zone line and help text", async () => {
    // A 5 min cadence, so the 30 s clock ticker alone carries the server
    // clock from the 12:17 answer to 12:18.
    renderStrip([status({ server_time: "2026-10-03T12:17:00Z" })], 300_000);
    expect(screen.getByTestId("freshness-strip")).toHaveTextContent("Checking the server...");
    await advance(0);
    await advance(60_000);
    expect(text("strip-refreshed")).toBe("Server refreshed 14:15 CEST (3 min ago)");
    expect(text("strip-next")).toBe("Next refresh 14:30 CEST");
    expect(text("strip-checked")).toBe("Page checked 14:17 CEST");
    expect(text("strip-zone")).toBe("Times are Brussels time, CEST (+02:00).");
    expect(text("strip-help")).toBe(HELP);
    expect(screen.queryByTestId("strip-overdue")).toBeNull();
    expect(screen.queryByTestId("strip-failed")).toBeNull();
    expect(screen.getByTestId("freshness-strip")).not.toHaveTextContent("Checking the server...");
  });

  it("CEST to CET across 2026-10-25T01:00Z", async () => {
    const before = status({
      last_tick_finished: "2026-10-25T00:45:00Z",
      next_tick_at: "2026-10-25T01:00:00Z",
      server_time: "2026-10-25T00:59:00Z",
    });
    const after = status({
      last_tick_finished: "2026-10-25T01:00:00Z",
      next_tick_at: "2026-10-25T01:15:00Z",
      server_time: "2026-10-25T01:01:00Z",
    });
    renderStrip([before, after]);
    await advance(0);
    expect(text("strip-zone")).toBe("Times are Brussels time, CEST (+02:00).");
    expect(text("strip-refreshed")).toBe("Server refreshed 02:45 CEST (14 min ago)");
    expect(text("strip-next")).toBe("Next refresh 02:00 CET");
    await advance(60_000);
    expect(text("strip-zone")).toBe("Times are Brussels time, CET (+01:00).");
    expect(text("strip-refreshed")).toBe("Server refreshed 02:00 CET (1 min ago)");
    expect(text("strip-next")).toBe("Next refresh 02:15 CET");
    expect(text("strip-checked")).toBe("Page checked 02:01 CET");
  });

  it("no heading and no aria-live on the container; the announcer is role=status", async () => {
    renderStrip([status()]);
    await advance(0);
    const strip = screen.getByTestId("freshness-strip");
    expect(strip.tagName).toBe("SECTION");
    expect(strip.getAttribute("aria-label")).toBe("Data freshness");
    expect(strip.hasAttribute("aria-live")).toBe(false);
    expect(strip.querySelector("h1, h2, h3, h4, h5, h6, [role='heading']")).toBeNull();
    expect(strip.querySelectorAll("[aria-live]")).toHaveLength(1);
    const announcer = screen.getByTestId("strip-announcer");
    expect(announcer.getAttribute("role")).toBe("status");
    expect(announcer.getAttribute("aria-live")).toBe("polite");
    expect(announcer.className).toContain("visually-hidden");
  });

  it("five polls in one state leave the announcer unchanged; overdue sets it once; recovery says no longer overdue", async () => {
    const calm = (minute: number) => status({ server_time: `2026-10-03T12:${String(18 + minute).padStart(2, "0")}:00Z` });
    const late = (sec: string) => status({ server_time: `2026-10-03T12:${sec}Z` });
    renderStrip([
      calm(0),
      calm(1),
      calm(2),
      calm(3),
      calm(4),
      late("40:00"),
      late("41:00"),
      status({
        last_tick_finished: "2026-10-03T12:41:00Z",
        next_tick_at: "2026-10-03T12:56:00Z",
        server_time: "2026-10-03T12:42:00Z",
      }),
    ]);
    await advance(0);
    for (let i = 0; i < 4; i += 1) await advance(60_000);
    expect(text("strip-announcer")).toBe("");
    await advance(60_000);
    expect(text("strip-overdue")).toBe("Refresh overdue: expected 14:30 CEST");
    expect(text("strip-announcer")).toBe("Refresh is overdue");
    await advance(60_000);
    expect(text("strip-announcer")).toBe("Refresh is overdue");
    await advance(60_000);
    expect(screen.queryByTestId("strip-overdue")).toBeNull();
    expect(text("strip-announcer")).toBe("Refresh is no longer overdue");
  });

  it("overdue at + 301 s, not + 300 s", async () => {
    renderStrip([status({ server_time: "2026-10-03T12:35:00Z" }), status({ server_time: "2026-10-03T12:35:01Z" })]);
    await advance(0);
    expect(screen.queryByTestId("strip-overdue")).toBeNull();
    await advance(60_000);
    expect(text("strip-overdue")).toBe("Refresh overdue: expected 14:30 CEST");
  });

  it("a failed check keeps the last items and sets the failure line and the announcer", async () => {
    renderStrip([status({ server_time: "2026-10-03T12:17:00Z" }), new Error("down")]);
    await advance(0);
    await advance(60_000);
    expect(text("strip-failed")).toBe("Could not check the server. Last answer from the server: 14:17 CEST.");
    expect(text("strip-announcer")).toBe("Could not check the server");
    expect(text("strip-refreshed")).toBe("Server refreshed 14:15 CEST (3 min ago)");
    expect(text("strip-next")).toBe("Next refresh 14:30 CEST");
    expect(text("strip-checked")).toBe("Page checked 14:17 CEST");
  });

  it("worker-off and first-refresh copy", async () => {
    renderStrip([
      status({ running: false, disabled_reason: "SCREENER_REFRESH_WORKER=0", last_tick_finished: null, next_tick_at: null }),
      status({ last_tick_finished: null }),
    ]);
    await advance(0);
    expect(screen.getByTestId("freshness-strip")).toHaveTextContent(
      "Automatic server refresh is off (switched off by SCREENER_REFRESH_WORKER=0). This page still re-checks every minute.",
    );
    expect(screen.queryByTestId("strip-refreshed")).toBeNull();
    await advance(60_000);
    expect(screen.getByTestId("freshness-strip")).toHaveTextContent(
      "Server has not finished its first refresh. Next refresh 14:30 CEST",
    );
    expect(screen.queryByTestId("strip-next")).toBeNull();
  });

  it("day prefix", async () => {
    renderStrip([
      status({
        last_tick_finished: "2026-10-03T21:50:00Z", // 23:50 CEST on 03 Oct
        next_tick_at: "2026-10-03T22:05:00Z", // 00:05 CEST on 04 Oct
        server_time: "2026-10-03T22:01:00Z", // 00:01 CEST on 04 Oct
      }),
    ]);
    await advance(0);
    expect(text("strip-refreshed")).toBe("Server refreshed 03 Oct 23:50 CEST (11 min ago)");
    expect(text("strip-next")).toBe("Next refresh 00:05 CEST");
    expect(text("strip-checked")).toBe("Page checked 00:01 CEST");
  });
});
