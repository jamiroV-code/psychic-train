import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DiscoverySourcesPanel } from "@/components/narrative/DiscoverySourcesPanel";
import type { DiscoverySourceHealth, DiscoverySourcesResponse } from "@/lib/types/discovery";

const health: DiscoverySourceHealth = {
  last_unit_at: null, paused: true, pause_reason: null, pause_until: null, collection_day: "2026-10-29",
  attempted: null, fetched: null, completeness_day: "2026-10-28", completeness_attempted: null,
  completeness_fetched: null, missing: null, missing_reasons: null, capped: null, newest_age_hours: null,
  budget_used: null, effective_budget: null, budget_spent: null, mode: null, expected_gap_s: null, stale: null,
  completeness: "no completeness evidence", accounts_active: 1, accounts_total: 2,
  accounts: [{ label: "acct-1", state: "active", reason: null, last_used: null, cookie_age_days: 3 }],
  free_disk_bytes: null, clock_sync_age_seconds: null,
};

const resp: DiscoverySourcesResponse = {
  as_of: "2026-10-29", universe_size: 100, eligible_size: 50, live_sources: 1, total_sources: 3, live_weight: 25,
  newest: "2026-10-29",
  sources: [
    { id: "wikipedia", label: "Wikipedia pageviews", kind: "weighted", weight: 25, state: "ok", newest: "2026-10-29", history_days: 99, coins_with_data: 38, eligible_size: 50, note: "", reason: "", impl: "wiki" },
    { id: "x", label: "X", kind: "weighted", weight: 15, state: "unavailable", newest: null, history_days: 0, coins_with_data: 0, eligible_size: 50, note: "", reason: "x_live_off", impl: "x_worker", health },
  ],
};

describe("DiscoverySourcesPanel health", () => {
  it("renders a visible health block under a worker row", async () => {
    render(<DiscoverySourcesPanel fetchSources={() => Promise.resolve(resp)} />);
    const block = await screen.findByTestId("sources-health-x");
    const t = block.textContent ?? "";
    expect(t).toContain("Reason: X live collection off");
    expect(t).toContain("Method: x_worker");
    expect(t).toContain("Last unit: unknown");
    expect(t).toContain("Paused: reason unknown, owner action needed");
    expect(t).toContain("Stale: unknown");
    expect(t).toContain("Today 2026-10-29: attempted unknown, fetched unknown");
    expect(t).toContain("Budget: used unknown of unknown");
    expect(t).toContain("Completeness 2026-10-28: no completeness evidence");
    expect(t).toContain("Mode: unknown");
    expect(t).toContain("X accounts: 1 of 2 active. acct-1 active, cookie 3 days old");
    expect(t).toContain("One day late");
    expect(t).toContain("Free disk: unknown");
    expect(block.querySelector("[title]")).toBeNull();
  });

  it("renders rows without health exactly as before", async () => {
    render(<DiscoverySourcesPanel fetchSources={() => Promise.resolve(resp)} />);
    expect(await screen.findByTestId("sources-row-wikipedia")).toHaveTextContent("Wikipedia pageviews25ok38 / 50992026-10-29");
    expect(screen.queryByTestId("sources-health-wikipedia")).toBeNull();
    expect(screen.getByTestId("sources-row-wikipedia").textContent).not.toContain("Method");
  });
});

describe("DiscoverySourcesPanel waking-up watch list (stage 2)", () => {
  const trendsRow = { id: "trends", label: "Google Trends", kind: "weighted" as const, weight: 25, state: "ok" as const, newest: "2026-10-29", history_days: 100, coins_with_data: 40, eligible_size: 50, note: "", reason: "" as const, impl: "pytrends" };

  it("renders the watch text with days held", async () => {
    render(<DiscoverySourcesPanel fetchSources={() => Promise.resolve({ ...resp, sources: [trendsRow], trends_watch: [{ symbol: "QNT", days_held: 5 }] })} />);
    expect(await screen.findByTestId("sources-trends-watch")).toHaveTextContent("Waking up (daily pulls): QNT (5 days)");
  });

  it("renders nothing when the list is empty, null or missing", async () => {
    for (const trends_watch of [[], null, undefined]) {
      const { unmount } = render(<DiscoverySourcesPanel fetchSources={() => Promise.resolve({ ...resp, sources: [trendsRow], trends_watch })} />);
      expect(await screen.findByTestId("sources-row-trends")).toBeInTheDocument();
      expect(screen.queryByTestId("sources-trends-watch")).toBeNull();
      unmount();
    }
  });
});
