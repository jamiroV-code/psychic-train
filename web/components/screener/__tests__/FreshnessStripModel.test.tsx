import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { FreshnessStrip } from "@/components/screener/FreshnessStrip";
import { LiveProvider } from "@/components/screener/LiveProvider";
import { EQUITIES_STRIP_HELP, equitiesStripModel } from "@/lib/equities-strip";
import { STRIP_HELP, stripModel } from "@/lib/refresh-strip";
import type { EquitiesStatus } from "@/lib/types/equities";

// T50 / S9E: the strip's optional `model` prop. Without it the strip is the
// crypto one; the equities model adds the latest bar line.
const STATUS: EquitiesStatus = {
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
};

let monoNow = 0;
const mono = () => monoNow;

async function renderStrip(model?: typeof stripModel) {
  const fetchStatus = vi.fn(async () => STATUS);
  render(
    <LiveProvider fetchStatus={fetchStatus} mono={mono}>
      {model ? <FreshnessStrip model={model} /> : <FreshnessStrip />}
    </LiveProvider>,
  );
  await act(async () => {
    await vi.advanceTimersByTimeAsync(0);
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

test("without a model prop the strip keeps the crypto words", async () => {
  await renderStrip();
  expect(text("strip-next")).toBe("Next refresh 12 Oct 22:30 CEST");
  expect(text("strip-help")).toBe(STRIP_HELP);
});

test("a model prop replaces the words", async () => {
  await renderStrip(equitiesStripModel);
  expect(text("strip-next")).toBe("Next expected refresh Mon 12 Oct 22:30 CEST");
  expect(text("strip-help")).toBe(EQUITIES_STRIP_HELP);
});

test("the equities model shows the latest bar line", async () => {
  await renderStrip(equitiesStripModel);
  expect(text("strip-last-bar")).toBe("Latest daily bar 2026-10-09");
});

test("the crypto strip has no latest bar line", async () => {
  await renderStrip(stripModel);
  expect(screen.queryByTestId("strip-last-bar")).toBeNull();
});
