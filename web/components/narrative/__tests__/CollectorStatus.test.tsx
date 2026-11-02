import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CollectorStatus } from "@/components/narrative/CollectorStatus";
import { DiscoverySourcesPanel } from "@/components/narrative/DiscoverySourcesPanel";
import type { DiscoveryCollectorSource, DiscoveryCollectorStatus, DiscoverySourcesResponse } from "@/lib/types/discovery";

const noState = (id: string, label: string): DiscoveryCollectorSource => ({
  id, label, has_state: false, last_unit_at: null, paused: null, pause_reason: null, pause_until: null, stale: null,
  budget_used: null, effective_budget: null,
});

const reddit: DiscoveryCollectorSource = {
  id: "reddit", label: "Reddit", has_state: true, last_unit_at: "2026-11-02T09:58:00+00:00", paused: false,
  pause_reason: null, pause_until: null, stale: false, budget_used: 12, effective_budget: 250,
};

const base: DiscoveryCollectorStatus = {
  state: "running", reason: "", started_at: "2026-11-02T08:00:00+00:00", last_beat: "2026-11-02T10:00:00+00:00",
  age_s: 12, mode: "standalone", version: "abc1234", running_sources: ["xsearch_web", "reddit_web"],
  sources: [noState("xsearch", "X search"), reddit],
};

function head(): string {
  return screen.getByTestId("collector-status-head").textContent ?? "";
}

describe("CollectorStatus", () => {
  it("shows a running collector with its start, heartbeat age and mode as plain text", () => {
    render(<CollectorStatus collector={base} />);
    const box = screen.getByTestId("collector-status");
    expect(box).toHaveAttribute("role", "status");
    expect(box).toHaveAttribute("aria-live", "polite");
    expect(box).toHaveAttribute("data-state", "running");
    expect(head()).toBe(
      "Collector: Running (standalone process), since 2026-11-02 08:00 UTC, last heartbeat 12 s ago, code abc1234");
    expect(box.querySelector("[title]")).toBeNull();
  });

  it("formats the heartbeat age in minutes, hours and days", () => {
    const cases: [number, string][] = [[119, "119 s ago"], [600, "10 min ago"], [3 * 3600, "3 h ago"], [3 * 86400, "3 days ago"]];
    for (const [age, text] of cases) {
      const { unmount } = render(<CollectorStatus collector={{ ...base, age_s: age }} />);
      expect(head()).toContain(`last heartbeat ${text}`);
      unmount();
    }
  });

  it.each([
    ["stopped_cleanly", "Collector: Stopped (stopped cleanly), last heartbeat 3 h ago at 2026-11-02 10:00 UTC"],
    ["heartbeat_stale", "Collector: Stopped (no heartbeat for over 90 s), last heartbeat 3 h ago at 2026-11-02 10:00 UTC"],
    ["process_gone", "Collector: Stopped (process not running), last heartbeat 3 h ago at 2026-11-02 10:00 UTC"],
  ] as const)("shows a stopped collector: %s", (reason, text) => {
    render(<CollectorStatus collector={{ ...base, state: "stopped", reason, age_s: 3 * 3600 }} />);
    expect(head()).toBe(text);
    expect(screen.getByTestId("collector-status")).toHaveAttribute("data-state", "stopped");
  });

  it("shows a collector that never started", () => {
    render(<CollectorStatus collector={{ ...base, state: "never_started", reason: "no_heartbeat", started_at: null, last_beat: null, age_s: null, mode: null, version: null, running_sources: [] }} />);
    expect(head()).toBe("Collector: Not started (no heartbeat yet)");
  });

  it("shows an unreadable heartbeat as unknown, never running", () => {
    render(<CollectorStatus collector={{ ...base, state: "unknown", reason: "unreadable", started_at: null, last_beat: null, age_s: null, mode: null, version: null }} />);
    expect(head()).toBe("Collector: Status unknown (heartbeat file unreadable)");
    expect(screen.getByTestId("collector-status")).toHaveAttribute("data-state", "unknown");
  });

  it("shows a missing collector object as unknown with no source lines", () => {
    for (const collector of [null, undefined]) {
      const { unmount } = render(<CollectorStatus collector={collector} />);
      expect(head()).toBe("Collector: Status unknown (not reported by the API)");
      expect(screen.getByTestId("collector-status").textContent).not.toMatch(/Running|ok\b/);
      expect(screen.queryByTestId("collector-source-reddit")).toBeNull();
      unmount();
    }
  });

  it("writes one line per source; missing worker state is unknown, never 0 or not paused", () => {
    render(<CollectorStatus collector={base} />);
    expect(screen.getByTestId("collector-source-reddit")).toHaveTextContent(
      "Reddit: last unit 2026-11-02 09:58 UTC; not paused; not stale; budget used 12 of 250");
    const x = screen.getByTestId("collector-source-xsearch").textContent ?? "";
    expect(x).toBe("X search: no worker state yet");
    expect(x).not.toMatch(/\b0\b|not paused/);
  });

  it("writes pause reasons, staleness and unknown values in words", () => {
    const sources: DiscoveryCollectorSource[] = [
      { ...reddit, paused: true, pause_reason: "rate_limited", pause_until: "2026-11-03T00:00:20+00:00", stale: true },
      { ...reddit, id: "xsearch", label: "X search", last_unit_at: null, paused: true, pause_reason: "login_expired", stale: null, budget_used: null, effective_budget: null },
    ];
    render(<CollectorStatus collector={{ ...base, sources }} />);
    expect(screen.getByTestId("collector-source-reddit")).toHaveTextContent(
      "Reddit: last unit 2026-11-02 09:58 UTC; paused: rate_limited until 2026-11-03 00:00 UTC; stale; budget used 12 of 250");
    expect(screen.getByTestId("collector-source-xsearch")).toHaveTextContent(
      "X search: last unit unknown; paused: login_expired, owner action needed; staleness unknown; budget used unknown of unknown");
  });
});

describe("DiscoverySourcesPanel collector box", () => {
  const resp: DiscoverySourcesResponse = {
    as_of: "2026-11-01", universe_size: 100, eligible_size: 50, live_sources: 0, total_sources: 3, live_weight: 0,
    newest: null, sources: [], collector: base,
  };

  it("renders the box outside the collapsed table, visible at a glance", async () => {
    render(<DiscoverySourcesPanel fetchSources={() => Promise.resolve(resp)} />);
    const box = await screen.findByTestId("collector-status");
    expect(box.closest("details")).toBeNull();
    expect(box).toHaveTextContent("Collector: Running");
  });

  it("renders unknown when an older API omits the collector object", async () => {
    const { collector: _omit, ...older } = resp;
    render(<DiscoverySourcesPanel fetchSources={() => Promise.resolve(older)} />);
    expect(await screen.findByTestId("collector-status-head")).toHaveTextContent("Collector: Status unknown (not reported by the API)");
  });
});
