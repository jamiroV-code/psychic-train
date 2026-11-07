import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CollectorStatus } from "@/components/narrative/CollectorStatus";
import { DiscoverySourcesPanel } from "@/components/narrative/DiscoverySourcesPanel";
import type {
  DiscoveryCollectorSource, DiscoveryCollectorStatus, DiscoverySourceHealth, DiscoverySourcesResponse,
} from "@/lib/types/discovery";

const health: DiscoverySourceHealth = {
  last_unit_at: null, paused: false, pause_reason: null, pause_until: null, collection_day: "2026-11-07",
  attempted: null, fetched: null, completeness_day: "2026-11-06", completeness_attempted: null,
  completeness_fetched: null, missing: null, missing_reasons: null, capped: null, newest_age_hours: null,
  budget_used: null, effective_budget: null, budget_spent: null, mode: null, expected_gap_s: null, stale: null,
  completeness: "", accounts_active: null, accounts_total: null, accounts: [], free_disk_bytes: null,
  clock_sync_age_seconds: null,
};

const reddit: DiscoveryCollectorSource = {
  id: "reddit", label: "Reddit", has_state: true, last_unit_at: null, paused: false, pause_reason: null,
  pause_until: null, stale: false, budget_used: 1, effective_budget: 2,
  methods: [
    { method: "reddit_live_browser", label: "Reddit live (browser)", state: "needs_probe", reason: "probe_missing",
      last_settled_day: null, lanes: null, comments_scope: null, requests_today: null, cap: null },
    { method: "reddit_web", label: "Reddit web feed", state: "unknown", reason: null, last_settled_day: null,
      lanes: null, comments_scope: null, requests_today: null, cap: null },
  ],
};

const base: DiscoveryCollectorStatus = {
  state: "running", reason: "", started_at: null, last_beat: null, age_s: 5, mode: "standalone", version: null,
  running_sources: [], sources: [reddit],
};

const full: DiscoveryCollectorStatus = {
  ...base,
  daily_report: { day: "2026-11-06", revision: 1, complete: false, per_source_method: {
    "reddit/reddit_live_gql": { eligible: 4, stored: 3, exact: 3, estimated: 0, missing: 1, reasons: { blocked: 1 } } } },
  doctor: { state: "UNKNOWN", checked_at: null, failures: null, warnings: null },
  browser: { profile_state: "missing", relay_refusals: [{ host: "edge.microsoft.com", count: 2 }] },
};

describe("CollectorStatus finish fields", () => {
  it("lists each Reddit method under the Reddit source; unknown stays unknown", () => {
    render(<CollectorStatus collector={base} />);
    expect(screen.getByTestId("collector-method-reddit_live_browser"))
      .toHaveTextContent("Reddit live (browser): needs probe (probe_missing)");
    const web = screen.getByTestId("collector-method-reddit_web").textContent ?? "";
    expect(web).toMatch(/^Reddit web feed: unknown,/);
    expect(web).not.toMatch(/\bok\b/);
  });

  it("shows report, doctor and browser lines when present", () => {
    render(<CollectorStatus collector={full} />);
    expect(screen.getByTestId("collector-daily-report")).toHaveTextContent("Daily report 2026-11-06 (revision 1): incomplete");
    expect(screen.getByTestId("collector-daily-report")).toHaveTextContent("reddit/reddit_live_gql: eligible 4, stored 3");
    expect(screen.getByTestId("collector-doctor")).toHaveTextContent("Doctor: unknown");
    expect(screen.getByTestId("collector-browser")).toHaveTextContent(
      "Browser profile: missing; relay refused edge.microsoft.com 2");
  });

  it("keeps the pre-finish box when an older API omits every new field", () => {
    const { methods: _m, ...legacyReddit } = reddit;
    render(<CollectorStatus collector={{ ...base, sources: [legacyReddit] }} />);
    for (const id of ["collector-daily-report", "collector-doctor", "collector-browser", "collector-reddit-accounts",
      "collector-queryids"]) expect(screen.queryByTestId(id)).toBeNull();
    expect(screen.queryByTestId(/collector-method-/)).toBeNull();
  });

  it("labels X and Reddit account lists per site", () => {
    render(<CollectorStatus collector={base}
      xHealth={{ ...health, accounts_active: 1, accounts_total: 1, queryids: { mode: "sentinel", state: "candidate" },
        accounts: [{ label: "acct_a", state: "active", reason: null, last_used: null, cookie_age_days: 1 }] }}
      redditHealth={{ ...health, accounts_active: 0, accounts_total: 1, accounts: [
        { site: "reddit", label: "r_one", state: "resting", reason: null, reads_today: null, cap: 40, rest_until: null,
          ready: false, session_state: null, session_checked_at: null } ] }} />);
    expect(screen.getByTestId("collector-x-accounts")).toHaveTextContent("X accounts: 1 of 1 active");
    expect(screen.getByTestId("collector-reddit-accounts")).toHaveTextContent("Reddit accounts: 0 of 1 active");
    expect(screen.getByTestId("collector-reddit-account-r_one")).toHaveTextContent("r_one resting, reads today unknown / 40");
    expect(screen.getByTestId("collector-queryids")).toHaveTextContent("Query ids (sentinel): candidate pending");
    // A Reddit account is never rendered in the X list.
    expect(screen.queryByTestId("collector-account-r_one")).toBeNull();
  });

  it("the panel passes the Reddit row health to the box", async () => {
    const resp: DiscoverySourcesResponse = {
      as_of: "2026-11-06", universe_size: 1, eligible_size: 1, live_sources: 0, total_sources: 1, live_weight: 0,
      newest: null, collector: base, sources: [{ id: "reddit", label: "Reddit", kind: "weighted", weight: 10,
        state: "ok", newest: null, history_days: 0, coins_with_data: 0, eligible_size: 1, note: "", reason: "",
        impl: "reddit_web", health: { ...health, accounts_active: 1, accounts_total: 1, accounts: [
          { site: "reddit", label: "r_one", state: "active", reason: null, reads_today: 2, cap: 40, rest_until: null,
            ready: true, session_state: "ok", session_checked_at: null }] } }],
    };
    render(<DiscoverySourcesPanel fetchSources={() => Promise.resolve(resp)} />);
    expect(await screen.findByTestId("collector-reddit-account-r_one")).toHaveTextContent("r_one active");
  });
});
