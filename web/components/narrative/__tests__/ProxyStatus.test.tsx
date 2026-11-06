import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DiscoverySourcesPanel } from "@/components/narrative/DiscoverySourcesPanel";
import type { DiscoveryProxyState, DiscoverySourceHealth, DiscoverySourcesResponse } from "@/lib/types/discovery";

const states: DiscoveryProxyState[] = ["direct", "unknown", "healthy", "quarantined", "blocked"];
const health: DiscoverySourceHealth = {
  last_unit_at: null, paused: false, pause_reason: null, pause_until: null, collection_day: "2026-11-03",
  attempted: null, fetched: null, completeness_day: "2026-11-02", completeness_attempted: null,
  completeness_fetched: null, missing: null, missing_reasons: null, capped: null, newest_age_hours: null,
  budget_used: null, effective_budget: null, budget_spent: null, mode: null, expected_gap_s: null, stale: null,
  completeness: "unknown", accounts_active: 5, accounts_total: 6,
  accounts: [...states.map((proxy_state) => ({ label: proxy_state, state: "active" as const, reason: null,
    last_used: null, cookie_age_days: null, proxy_state })),
    { label: "legacy", state: "inactive", reason: "x_login_required", last_used: null, cookie_age_days: null }],
  free_disk_bytes: null, clock_sync_age_seconds: null,
};
const response: DiscoverySourcesResponse = {
  as_of: "2026-11-02", universe_size: 0, eligible_size: 0, live_sources: 0, total_sources: 1, live_weight: 0, newest: null,
  sources: [{ id: "xsearch", label: "X search", kind: "weighted", weight: 10, state: "unavailable", newest: null,
    history_days: 0, coins_with_data: 0, eligible_size: 0, note: "", reason: "no_stored_data", impl: "xsearch_web", health }],
};

describe("B2 source and collector account presentation", () => {
  it("renders the canonical xsearch account pool in both consumers with every proxy state", async () => {
    render(<DiscoverySourcesPanel fetchSources={async () => response} />);
    const collector = await screen.findByTestId("collector-status");
    const sources = screen.getByTestId("sources-health-xsearch");
    for (const state of states) {
      expect(within(collector).getByTestId(`collector-account-${state}`)).toHaveTextContent(`proxy ${state}`);
      expect(sources).toHaveTextContent(`proxy ${state}`);
    }
    const legacy = within(collector).getByTestId("collector-account-legacy");
    expect(legacy).toHaveTextContent("inactive (x_login_required)");
    expect(legacy).toHaveTextContent("proxy unknown");
    expect(legacy).not.toHaveTextContent(/proxy (healthy|direct)/);
    expect(collector).not.toHaveTextContent(/undefined|NaN|https?:\/\//);
  });
});
