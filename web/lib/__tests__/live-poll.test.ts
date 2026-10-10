import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LivePoller, POLL_INTERVAL_MS } from "@/lib/live-poll";
import type { RefreshStatus } from "@/lib/types/refresh";

const SERVER = Date.UTC(2026, 9, 3, 12, 3);

function status(overrides: Partial<RefreshStatus> = {}): RefreshStatus {
  return {
    running: true,
    disabled_reason: null,
    interval_seconds: 900,
    last_tick_started: "2026-10-03T12:00:00Z",
    last_tick_finished: "2026-10-03T12:01:00Z",
    last_tick_ok: 10,
    last_tick_failed: 0,
    next_tick_at: "2026-10-03T12:15:00Z",
    queue_depth: 0,
    backoff_seconds: 0,
    server_time: "2026-10-03T12:03:00Z",
    ...overrides,
  };
}

let visibility: DocumentVisibilityState = "visible";
let monoNow = 0;
const mono = () => monoNow;

function setVisibility(next: DocumentVisibilityState) {
  visibility = next;
  document.dispatchEvent(new Event("visibilitychange"));
}

async function advance(ms: number) {
  monoNow += ms;
  await vi.advanceTimersByTimeAsync(ms);
}

beforeEach(() => {
  vi.useFakeTimers();
  visibility = "visible";
  monoNow = 0;
  Object.defineProperty(document, "visibilityState", { configurable: true, get: () => visibility });
});

afterEach(() => {
  vi.useRealTimers();
});

describe("live-poll", () => {
  it("runs the first check at once and the next 60 s after the previous one settles", async () => {
    let release: (() => void) | null = null;
    const fetchStatus = vi.fn(
      () =>
        new Promise<RefreshStatus>((resolve) => {
          release = () => resolve(status());
        }),
    );
    const poller = new LivePoller({ fetchStatus, mono });
    poller.start();
    expect(fetchStatus).toHaveBeenCalledTimes(1);

    // The first answer takes 5 s; the next check is 60 s after THAT.
    await advance(5_000);
    release!();
    await advance(0);
    await advance(POLL_INTERVAL_MS - 1);
    expect(fetchStatus).toHaveBeenCalledTimes(1);
    await advance(1);
    expect(fetchStatus).toHaveBeenCalledTimes(2);
    poller.stop();
  });

  it("never overlaps: a never-resolving check blocks the next until the 10 s abort", async () => {
    const fetchStatus = vi.fn(() => new Promise<RefreshStatus>(() => {}));
    const poller = new LivePoller({ fetchStatus, mono });
    poller.start();
    poller.checkNow();
    await advance(9_999);
    expect(fetchStatus).toHaveBeenCalledTimes(1);
    await advance(1);
    expect(poller.getStatus().phase).toBe("failed");
    // After one failure the next check waits 120 s.
    await advance(119_999);
    expect(fetchStatus).toHaveBeenCalledTimes(1);
    await advance(1);
    expect(fetchStatus).toHaveBeenCalledTimes(2);
    poller.stop();
  });

  it("hidden, also when started hidden: nothing runs for 10 min and a hidden abort changes no snapshot", async () => {
    visibility = "hidden";
    const fetchStatus = vi.fn(async () => status());
    const hiddenStart = new LivePoller({ fetchStatus, mono });
    hiddenStart.start();
    await advance(600_000);
    expect(fetchStatus).not.toHaveBeenCalled();
    hiddenStart.stop();

    visibility = "visible";
    const slow = vi.fn(() => new Promise<RefreshStatus>(() => {}));
    const poller = new LivePoller({ fetchStatus: slow, mono });
    poller.start();
    const before = [poller.getData(), poller.getStatus(), poller.getClock()];
    setVisibility("hidden");
    await advance(600_000);
    expect(slow).toHaveBeenCalledTimes(1);
    expect([poller.getData(), poller.getStatus(), poller.getClock()]).toEqual(before);
    expect(poller.getData()).toBe(before[0]);
    expect(poller.getStatus()).toBe(before[1]);
    expect(poller.getStatus().phase).toBe("waiting");
    poller.stop();
  });

  it("turning visible runs one check at once", async () => {
    const fetchStatus = vi.fn(async () => status());
    const poller = new LivePoller({ fetchStatus, mono });
    poller.start();
    await advance(0);
    setVisibility("hidden");
    await advance(300_000);
    expect(fetchStatus).toHaveBeenCalledTimes(1);
    setVisibility("visible");
    expect(fetchStatus).toHaveBeenCalledTimes(2);
    await advance(0);
    expect(fetchStatus).toHaveBeenCalledTimes(2);
    await advance(POLL_INTERVAL_MS);
    expect(fetchStatus).toHaveBeenCalledTimes(3);
    poller.stop();
  });

  it("waits 120, 240, 300, 300 s after consecutive failures and 60 s after a success", async () => {
    let fail = true;
    const fetchStatus = vi.fn(async () => {
      if (fail) throw new Error("down");
      return status();
    });
    const poller = new LivePoller({ fetchStatus, mono });
    poller.start();
    await advance(0);
    for (const wait of [120_000, 240_000, 300_000, 300_000]) {
      const calls = fetchStatus.mock.calls.length;
      await advance(wait - 1);
      expect(fetchStatus).toHaveBeenCalledTimes(calls);
      if (wait === 300_000 && calls === 4) fail = false;
      await advance(1);
      expect(fetchStatus).toHaveBeenCalledTimes(calls + 1);
    }
    expect(poller.getStatus()).toMatchObject({ phase: "ok", failures: 0 });
    await advance(POLL_INTERVAL_MS - 1);
    expect(fetchStatus).toHaveBeenCalledTimes(5);
    await advance(1);
    expect(fetchStatus).toHaveBeenCalledTimes(6);
    poller.stop();
  });

  it("a failure keeps lastGood; a null server_time succeeds without syncing the clock", async () => {
    const answers: (RefreshStatus | Error)[] = [status(), new Error("down"), status({ server_time: null })];
    const fetchStatus = vi.fn(async () => {
      const next = answers.shift()!;
      if (next instanceof Error) throw next;
      return next;
    });
    const poller = new LivePoller({ fetchStatus, mono });
    poller.start();
    await advance(0);
    const good = poller.getStatus().lastGood;
    expect(good?.serverMs).toBe(SERVER);

    await advance(POLL_INTERVAL_MS);
    expect(poller.getStatus()).toMatchObject({ phase: "failed", failures: 1 });
    expect(poller.getStatus().lastGood).toBe(good);

    await advance(120_000);
    expect(poller.getStatus().phase).toBe("ok");
    expect(poller.getStatus().lastGood?.status.server_time).toBeNull();
    expect(poller.getStatus().lastGood?.serverMs).toBe(SERVER);
    // Still the clock of the first answer, run on by monotonic time.
    expect(poller.serverNowMs()).toBe(SERVER + POLL_INTERVAL_MS + 120_000);

    // A poller whose only answer had no clock has none at all.
    const clockless = new LivePoller({ fetchStatus: async () => status({ server_time: null }), mono });
    clockless.start();
    await advance(0);
    expect(clockless.getStatus().phase).toBe("ok");
    expect(clockless.getStatus().lastGood?.serverMs).toBeNull();
    expect(clockless.getClock().nowMs).toBeNull();
    clockless.stop();
    poller.stop();
  });

  it("serverNowMs is the last server instant plus monotonic elapsed, whatever the system clock", async () => {
    const poller = new LivePoller({ fetchStatus: async () => status(), mono });
    poller.start();
    await advance(0);
    expect(poller.serverNowMs()).toBe(SERVER);
    vi.setSystemTime(new Date(Date.UTC(2001, 0, 1)));
    monoNow += 45_000;
    expect(poller.serverNowMs()).toBe(SERVER + 45_000);
    // The 30 s ticker publishes it.
    await advance(30_000);
    expect(poller.getClock().nowMs).toBe(SERVER + 75_000);
    poller.stop();
  });

  it("re-syncs the clock on every success", async () => {
    const times = ["2026-10-03T12:03:00Z", "2026-10-03T12:10:00Z"];
    const poller = new LivePoller({ fetchStatus: async () => status({ server_time: times.shift() ?? null }), mono });
    poller.start();
    await advance(0);
    expect(poller.getClock().nowMs).toBe(SERVER);
    await advance(POLL_INTERVAL_MS);
    // The server says 12:10, not 12:03 + 60 s: its own clock wins.
    expect(poller.serverNowMs()).toBe(Date.UTC(2026, 9, 3, 12, 10));
    expect(poller.getClock().nowMs).toBe(Date.UTC(2026, 9, 3, 12, 10));
    poller.stop();
  });

  it("dataVersion rises only on a changed last_tick_finished or a running flip, and on every success when not running", async () => {
    const answers = [
      status(),
      status({ server_time: "2026-10-03T12:04:00Z", queue_depth: 3 }),
      status({ last_tick_finished: "2026-10-03T12:16:00Z" }),
      status({ last_tick_finished: "2026-10-03T12:16:00Z", running: false, disabled_reason: "stopped" }),
      status({ last_tick_finished: "2026-10-03T12:16:00Z", running: false, disabled_reason: "stopped" }),
    ];
    const poller = new LivePoller({ fetchStatus: async () => answers.shift()!, mono });
    poller.start();
    await advance(0);
    expect(poller.getData().dataVersion).toBe(0); // the baseline
    await advance(POLL_INTERVAL_MS);
    expect(poller.getData().dataVersion).toBe(0); // only volatile fields moved
    await advance(POLL_INTERVAL_MS);
    expect(poller.getData().dataVersion).toBe(1);
    await advance(POLL_INTERVAL_MS);
    expect(poller.getData().dataVersion).toBe(2);
    await advance(POLL_INTERVAL_MS);
    expect(poller.getData().dataVersion).toBe(3); // not running: every success
    poller.stop();
  });

  it("tick rises after each settled check except the first", async () => {
    let n = 0;
    const poller = new LivePoller({
      fetchStatus: async () => {
        n += 1;
        if (n === 2) throw new Error("down");
        return status();
      },
      mono,
    });
    const listener = vi.fn();
    poller.subscribe(listener);
    poller.start();
    await advance(0);
    expect(poller.getData().tick).toBe(0);
    await advance(POLL_INTERVAL_MS);
    expect(poller.getData().tick).toBe(1); // a failed check settles too
    await advance(120_000);
    expect(poller.getData().tick).toBe(2);
    expect(listener).toHaveBeenCalled();
    poller.stop();
  });

  it("stop() mid-check leaves no timer, listener or failure, and start() works again", async () => {
    const removeSpy = vi.spyOn(document, "removeEventListener");
    const addSpy = vi.spyOn(document, "addEventListener");
    let resolveFirst: ((s: RefreshStatus) => void) | null = null;
    const fetchStatus = vi.fn((signal: AbortSignal) => {
      if (!resolveFirst) {
        return new Promise<RefreshStatus>((resolve) => {
          resolveFirst = resolve;
          void signal;
        });
      }
      return Promise.resolve(status());
    });
    const poller = new LivePoller({ fetchStatus, mono });
    poller.start();
    poller.start(); // idempotent
    expect(fetchStatus).toHaveBeenCalledTimes(1);
    expect(addSpy.mock.calls.filter((c) => c[0] === "visibilitychange")).toHaveLength(1);
    const before = poller.getStatus();
    poller.stop();
    expect(vi.getTimerCount()).toBe(0);
    expect(removeSpy.mock.calls.filter((c) => c[0] === "visibilitychange")).toHaveLength(1);
    resolveFirst!(status());
    await advance(600_000);
    expect(poller.getStatus()).toBe(before);
    expect(poller.getStatus().failures).toBe(0);
    expect(fetchStatus).toHaveBeenCalledTimes(1);

    poller.start();
    expect(fetchStatus).toHaveBeenCalledTimes(2);
    await advance(0);
    expect(poller.getStatus().phase).toBe("ok");
    expect(poller.getData().tick).toBe(0); // still the first settled check
    poller.stop();
    removeSpy.mockRestore();
    addSpy.mockRestore();
  });

  it("checkNow() never leaves two timers", async () => {
    const fetchStatus = vi.fn(async () => status());
    const poller = new LivePoller({ fetchStatus, mono });
    poller.start();
    await advance(0);
    // One pending check timer plus the 30 s clock ticker.
    expect(vi.getTimerCount()).toBe(2);
    poller.checkNow();
    poller.checkNow(); // ignored: a check is in flight
    await advance(0);
    expect(vi.getTimerCount()).toBe(2);
    expect(fetchStatus).toHaveBeenCalledTimes(2);
    poller.checkNow();
    await advance(0);
    expect(vi.getTimerCount()).toBe(2);
    expect(fetchStatus).toHaveBeenCalledTimes(3);
    await advance(POLL_INTERVAL_MS - 1);
    expect(fetchStatus).toHaveBeenCalledTimes(3);
    await advance(1);
    expect(fetchStatus).toHaveBeenCalledTimes(4);
    poller.stop();
    expect(vi.getTimerCount()).toBe(0);
  });
});
