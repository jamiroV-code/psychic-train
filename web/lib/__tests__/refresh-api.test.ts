import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchRefreshStatus } from "@/lib/api/refresh";

const STATUS = {
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
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("refresh-api", () => {
  it("fetches the status URL and parses it", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify(STATUS), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(fetchRefreshStatus()).resolves.toEqual(STATUS);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(String((fetchMock.mock.calls[0] as unknown[])[0])).toMatch(/\/api\/refresh\/status$/);
  });

  it("a non-OK answer names the status", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("down", { status: 503 })));
    await expect(fetchRefreshStatus()).rejects.toThrow(/503/);
  });

  it("passes the signal, and an abort rejects", async () => {
    const fetchMock = vi.fn(
      (_url: string, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
        }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const controller = new AbortController();
    const pending = fetchRefreshStatus(controller.signal);
    expect((fetchMock.mock.calls[0] as unknown[])[1]).toMatchObject({ signal: controller.signal });
    controller.abort();
    await expect(pending).rejects.toThrow(/aborted/);
  });
});
