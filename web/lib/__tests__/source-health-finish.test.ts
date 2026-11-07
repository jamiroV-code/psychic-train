import { describe, expect, it } from "vitest";
import {
  accountText, browserText, doctorText, methodText, queryIdText, redditAccountText, reportLines, sourceHealthLines,
} from "@/lib/source-health";
import type {
  DiscoveryAccountHealth, DiscoveryRedditAccountHealth, DiscoveryRedditMethodHealth, DiscoverySourceHealth,
  DiscoverySourceRow,
} from "@/lib/types/discovery";

const base: DiscoverySourceHealth = {
  last_unit_at: null, paused: false, pause_reason: null, pause_until: null, collection_day: "2026-11-07",
  attempted: null, fetched: null, completeness_day: "2026-11-06", completeness_attempted: null,
  completeness_fetched: null, missing: null, missing_reasons: null, capped: null, newest_age_hours: null,
  budget_used: null, effective_budget: null, budget_spent: null, mode: null, expected_gap_s: null, stale: null,
  completeness: "no worker state for this method", accounts_active: null, accounts_total: null, accounts: [],
  free_disk_bytes: null, clock_sync_age_seconds: null,
};

const row = (id: string, h: DiscoverySourceHealth): DiscoverySourceRow => ({
  id, label: id === "reddit" ? "Reddit" : "X", kind: "weighted", weight: 10, state: "ok", newest: null,
  history_days: 0, coins_with_data: 0, eligible_size: 0, note: "", reason: "", impl: null, health: h,
});

const lines = (r: DiscoverySourceRow) => Object.fromEntries((sourceHealthLines(r) ?? []).map((l) => [l.key, l.text]));

const reddit = (over: Partial<DiscoveryRedditAccountHealth> = {}): DiscoveryRedditAccountHealth => ({
  site: "reddit", label: "r_one", state: "active", reason: null, reads_today: 12, cap: 40, rest_until: null,
  ready: true, session_state: "ok", session_checked_at: "2026-11-07T08:00:00+00:00", proxy_state: "healthy", ...over,
});

const method = (over: Partial<DiscoveryRedditMethodHealth> = {}): DiscoveryRedditMethodHealth => ({
  method: "reddit_live_gql", label: "Reddit live (GraphQL)", state: "ok", reason: null,
  last_settled_day: "2026-11-06", lanes: { posts: 1, comments: 0.5 }, comments_scope: "threads_opened",
  requests_today: 30, cap: 200, ...over,
});

const SECRETISH = /cookie=|token|password|C:\\|\/home\/|\d+\.\d+\.\d+\.\d+|NaN|undefined|null/;

describe("Reddit accounts (their own model and label)", () => {
  it.each([
    ["active", "r_one active"], ["resting", "r_one resting"], ["paused", "r_one paused"],
    ["locked", "r_one locked"], ["unknown", "r_one state unknown"],
  ] as const)("words state %s", (state, text) => {
    expect(redditAccountText(reddit({ state }))).toContain(text);
  });

  it("shows reads, cap, rest, ready, session and proxy", () => {
    expect(redditAccountText(reddit({ state: "resting", reason: "new_account_rest", ready: false,
      rest_until: "2026-11-09T00:00:00+00:00" }))).toBe(
      "r_one resting (new_account_rest), reads today 12 / 40, rest until 2026-11-09 00:00 UTC, ready no, " +
      "session ok (checked 2026-11-07 08:00 UTC), proxy healthy");
  });

  it("renders every absent value as unknown, never healthy or 0", () => {
    const t = redditAccountText({ site: "reddit", label: "r_two", state: "unknown", reason: null, reads_today: null,
      cap: null, rest_until: null, ready: null, session_state: null, session_checked_at: null });
    expect(t).toBe("r_two state unknown, reads today unknown / no limit, rest until unknown, ready unknown, " +
      "session unknown (checked unknown), proxy unknown");
    expect(t).not.toMatch(/healthy|\bok\b|\b0\b/);
  });

  it("treats an unexpected state code as unknown", () => {
    expect(redditAccountText(reddit({ state: "bogus" as never }))).toContain("r_one state unknown");
  });

  it("labels the Reddit row 'Reddit accounts' and the X row 'X accounts'", () => {
    const r = lines(row("reddit", { ...base, accounts_active: 1, accounts_total: 2,
      accounts: [reddit(), reddit({ label: "r_two", state: "locked", reason: "account_locked" })] }));
    expect(r.accounts).toMatch(/^Reddit accounts: 1 of 2 active\. r_one active/);
    expect(r.accounts).toContain("r_two locked (account_locked)");
    expect(r.accounts).not.toContain("X accounts");
    const x = lines(row("xsearch", { ...base, accounts_active: 0, accounts_total: 0 }));
    expect(x.accounts).toBe("X accounts: 0 of 0 active");
  });
});

describe("X finish account fields", () => {
  const x: DiscoveryAccountHealth = { label: "acct_a", state: "active", reason: null, last_used: null, cookie_age_days: 3 };

  it("adds nothing when the fields are absent (default-off shape)", () => {
    expect(accountText(x)).not.toMatch(/endpoint|harvest|ct0|warmup|cooldown|quiet/);
  });

  it("shows endpoint, behaviour, harvest and ct0 rotations when present", () => {
    const t = accountText({ ...x, endpoint_state: "restricted", ct0_rotations_seen: 2,
      behaviour: { quiet_until: "2026-11-07T06:00:00+00:00", cooldown_until: null, cooldown_reason: "shrink",
        warmup_stage: 1, effective_cap: 20, mixed_calls_today: 3 },
      harvest: { state: "needs_owner", reason: "login_wall", last_at: "2026-11-06T10:00:00+00:00" } });
    expect(t).toContain("endpoint restricted");
    expect(t).toContain("quiet until 2026-11-07 06:00 UTC, cooldown until unknown (shrink), warmup stage 1, " +
      "effective cap 20, mixed calls today 3");
    expect(t).toContain("cookie harvest needs owner (login_wall) at 2026-11-06 10:00 UTC");
    expect(t).toContain("ct0 rotations seen 2");
  });

  it("never shows unknown endpoint or empty behaviour as ok", () => {
    const t = accountText({ ...x, endpoint_state: "unknown",
      behaviour: { quiet_until: null, cooldown_until: null, cooldown_reason: null, warmup_stage: null,
        effective_cap: null, mixed_calls_today: null }, harvest: { state: "unknown", reason: null, last_at: null } });
    expect(t).toContain("endpoint unknown");
    expect(t).toContain("warmup stage unknown, effective cap unknown, mixed calls today unknown");
    expect(t).toContain("cookie harvest unknown");
    expect(t).not.toMatch(/endpoint ok|harvest ok/);
  });
});

describe("Reddit methods", () => {
  it.each([
    ["ok", "ok"], ["degraded", "degraded"], ["needs_probe", "needs probe"], ["disabled", "off"],
    ["blocked", "blocked"], ["stale", "stale"], ["unknown", "unknown"],
  ] as const)("words method state %s", (state, word) => {
    expect(methodText(method({ state }))).toMatch(new RegExp(`^Reddit live \\(GraphQL\\): ${word}[,( ]`));
  });

  it("shows settled day, lanes with comment scope and requests of cap", () => {
    expect(methodText(method())).toBe("Reddit live (GraphQL): ok, last settled 2026-11-06, " +
      "lanes posts 100%, comments 50% (threads opened only), requests today 30 of 200");
  });

  it("renders absent values as unknown", () => {
    const t = methodText({ method: "reddit_stream", label: "Reddit stream", state: "unknown", reason: null,
      last_settled_day: null, lanes: null, comments_scope: null, requests_today: null, cap: null });
    expect(t).toBe("Reddit stream: unknown, last settled unknown, lanes unknown, requests today unknown of unknown");
  });

  it("an unexpected state is unknown", () => {
    expect(methodText(method({ state: "great" as never }))).toMatch(/^Reddit live \(GraphQL\): unknown,/);
  });

  it("adds one line per method to the Reddit row and nothing when absent", () => {
    const r = lines(row("reddit", { ...base, methods: [method(), method({ method: "reddit_web", label: "Reddit web feed",
      state: "disabled", reason: "method_disabled" })] }));
    expect(r["method-reddit_live_gql"]).toMatch(/^Reddit live \(GraphQL\): ok/);
    expect(r["method-reddit_web"]).toMatch(/^Reddit web feed: off \(method_disabled\)/);
    expect(Object.keys(lines(row("reddit", base))).filter((k) => k.startsWith("method-"))).toEqual([]);
  });
});

describe("X query ids", () => {
  it.each([
    ["ok", "ok"], ["candidate", "candidate pending"], ["stale", "stale"], ["unknown", "unknown"],
    ["blocked", "blocked"], ["refused_by_policy", "refused by policy"],
  ] as const)("words query-id state %s", (state, word) => {
    expect(queryIdText({ mode: "sentinel", state })).toContain(`Query ids (sentinel): ${word},`);
  });

  it("shows source, age and last check, unknown when absent", () => {
    expect(queryIdText({ mode: "auto", state: "ok", active_source: "bundle", active_age_days: 4,
      last_check: "2026-11-07T01:00:00+00:00" })).toBe(
      "Query ids (auto): ok, source bundle, active for 4 days, last check 2026-11-07 01:00 UTC");
    expect(queryIdText({ mode: "off", state: "unknown" })).toBe(
      "Query ids (off): unknown, source unknown, active for unknown days, last check unknown");
  });

  it("adds a queryids line to the X row only when present", () => {
    expect(lines(row("xsearch", { ...base, queryids: { mode: "sentinel", state: "stale" } })).queryids)
      .toMatch(/^Query ids \(sentinel\): stale/);
    expect(lines(row("xsearch", base)).queryids).toBeUndefined();
  });
});

describe("collector-level report, doctor and browser", () => {
  it("doctor verdicts; UNKNOWN is never a pass", () => {
    expect(doctorText({ state: "PASS", checked_at: "2026-11-07T02:00:00+00:00", failures: 0, warnings: 0 }))
      .toBe("Doctor: pass, checked 2026-11-07 02:00 UTC, 0 failures, 0 warnings");
    expect(doctorText({ state: "WARN", checked_at: null, failures: null, warnings: 2 }))
      .toBe("Doctor: warnings, checked unknown, unknown failures, 2 warnings");
    expect(doctorText({ state: "FAIL", checked_at: null, failures: 1, warnings: null })).toMatch(/^Doctor: failing,/);
    const unknown = doctorText({ state: "UNKNOWN", checked_at: null, failures: null, warnings: null });
    expect(unknown).toMatch(/^Doctor: unknown,/);
    expect(unknown).not.toMatch(/pass/);
  });

  it("daily report: complete, incomplete, unknown counts never zero", () => {
    expect(reportLines({ day: "2026-11-06", revision: 2, complete: false, per_source_method: {
      "reddit/reddit_web": { eligible: 10, stored: 8, exact: 7, estimated: 1, missing: 2, reasons: { blocked: 2 } },
    } })).toEqual([
      "Daily report 2026-11-06 (revision 2): incomplete",
      "reddit/reddit_web: eligible 10, stored 8, exact 7, estimated 1, missing 2 (blocked 2)",
    ]);
    expect(reportLines({ day: "2026-11-06", revision: 1, complete: true, per_source_method: {
      "xsearch/xsearch_web": { eligible: 5, stored: 5, exact: 5, estimated: 0, missing: 0, reasons: {} },
    } })[0]).toBe("Daily report 2026-11-06 (revision 1): complete");
    expect(reportLines({ day: "2026-11-06", revision: null, per_source_method: null, complete: null }))
      .toEqual(["Daily report 2026-11-06 (revision unknown): counts unknown"]);
  });

  it("browser profile state and bounded refusals", () => {
    expect(browserText({ profile_state: "policy_unsatisfied", relay_refusals: [{ host: "edge.microsoft.com", count: 4 }] }))
      .toBe("Browser profile: policy not satisfied; relay refused edge.microsoft.com 4");
    expect(browserText({ profile_state: "unknown", relay_refusals: [] }))
      .toBe("Browser profile: unknown; relay refused none");
    expect(browserText({ profile_state: "ok", relay_refusals: [] })).toBe("Browser profile: ok; relay refused none");
  });

  it("no formatter output carries path, IP or placeholder text", () => {
    for (const t of [
      redditAccountText(reddit()), methodText(method()), queryIdText({ mode: "auto", state: "ok" }),
      doctorText({ state: "UNKNOWN", checked_at: null, failures: null, warnings: null }),
      browserText({ profile_state: "missing", relay_refusals: [] }),
    ]) expect(t).not.toMatch(SECRETISH);
  });
});
