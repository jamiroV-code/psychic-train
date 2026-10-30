import { describe, expect, it } from "vitest";
import { sourceHealthLines } from "@/lib/source-health";
import type { DiscoverySourceHealth, DiscoverySourceRow } from "@/lib/types/discovery";

const health = (over: Partial<DiscoverySourceHealth> = {}): DiscoverySourceHealth => ({
  last_unit_at: "2026-10-29T14:03:27Z",
  paused: false,
  pause_reason: null,
  pause_until: null,
  collection_day: "2026-10-29",
  attempted: 40,
  fetched: 37,
  completeness_day: "2026-10-28",
  completeness_attempted: 50,
  completeness_fetched: 45,
  missing: 5,
  missing_reasons: { timeout: 3, "rate-limited": 2 },
  capped: 4,
  newest_age_hours: 2.5,
  budget_used: 120,
  effective_budget: 400,
  budget_spent: false,
  mode: "baseline",
  expected_gap_s: 300,
  stale: false,
  completeness: "45 of 50 coin-days fetched",
  accounts_active: 2,
  accounts_total: 3,
  accounts: [
    { label: "acct-1", state: "active", reason: null, last_used: "2026-10-29T13:00:00Z", cookie_age_days: 6 },
    { label: "acct-2", state: "locked", reason: "login-wall", last_used: null, cookie_age_days: null },
  ],
  free_disk_bytes: 53_687_091_200,
  clock_sync_age_seconds: null,
  ...over,
});

const row = (h: DiscoverySourceHealth | undefined, over: Partial<DiscoverySourceRow> = {}): DiscoverySourceRow => ({
  id: "x", label: "X", kind: "weighted", weight: 15, state: "ok", newest: "2026-10-28", history_days: 30,
  coins_with_data: 40, eligible_size: 50, note: "", reason: "", impl: "x_worker", health: h, ...over,
});

const text = (r: DiscoverySourceRow) => Object.fromEntries((sourceHealthLines(r) ?? []).map((l) => [l.key, l.text]));

describe("sourceHealthLines", () => {
  it("returns null for a row without health", () => {
    expect(sourceHealthLines(row(undefined))).toBeNull();
  });

  it("formats every field of a full health object", () => {
    const t = text(row(health(), { reason: "x_live_off" }));
    expect(t.reason).toBe("Reason: X live collection off");
    expect(t.impl).toBe("Method: x_worker");
    expect(t.last_unit).toBe("Last unit: 2026-10-29 14:03 UTC");
    expect(t.paused).toBe("Paused: no");
    expect(t.stale).toBe("Stale: no");
    expect(t.today).toBe("Today 2026-10-29: attempted 40, fetched 37");
    expect(t.budget).toBe("Budget: used 120 of 400");
    expect(t.completeness).toBe(
      "Completeness 2026-10-28: 45 of 50 coin-days fetched. Attempted 50, fetched 45, missing 5 (timeout 3, rate-limited 2), capped 4, newest 2.5 h old",
    );
    expect(t.mode).toBe("Mode: baseline");
    expect(t.accounts).toBe("X accounts: 2 of 3 active. acct-1 active, cookie 6 days old; acct-2 locked (login-wall), cookie age unknown");
    expect(t.late).toBe("One day late: completeness covers 2026-10-28, the last full day; today's counts are still in progress.");
    expect(t.disk).toBe("Free disk: 50.0 GB");
  });

  it("shows no reason as an explicit none", () => {
    expect(text(row(health())).reason).toBe("Reason: none");
  });

  it("shows paused with reason and end, or owner action needed", () => {
    expect(text(row(health({ paused: true, pause_reason: "rate-limit", pause_until: "2026-10-29T18:00:00Z" }))).paused)
      .toBe("Paused: rate-limit, until 2026-10-29 18:00 UTC");
    expect(text(row(health({ paused: true, pause_reason: null, pause_until: null }))).paused)
      .toBe("Paused: reason unknown, owner action needed");
  });

  it("flags stale and spent budget and degraded mode", () => {
    const t = text(row(health({ stale: true, budget_spent: true, mode: "degraded" })));
    expect(t.stale).toBe("Stale: yes, no unit for over twice the expected gap");
    expect(t.budget).toBe("Budget: used 120 of 400, spent");
    expect(t.mode).toBe("Mode: degraded");
  });

  it("renders every null field as unknown, never 0 or blank", () => {
    const t = text(row(health({
      last_unit_at: null, attempted: null, fetched: null, completeness_attempted: null, completeness_fetched: null,
      missing: null, missing_reasons: null, capped: null, newest_age_hours: null, budget_used: null,
      effective_budget: null, budget_spent: null, mode: null, stale: null, accounts_active: null, accounts_total: null,
      accounts: [], free_disk_bytes: null,
    }), { impl: null }));
    expect(t.impl).toBe("Method: unknown");
    expect(t.last_unit).toBe("Last unit: unknown");
    expect(t.stale).toBe("Stale: unknown");
    expect(t.today).toBe("Today 2026-10-29: attempted unknown, fetched unknown");
    expect(t.budget).toBe("Budget: used unknown of unknown");
    expect(t.completeness).toBe(
      "Completeness 2026-10-28: 45 of 50 coin-days fetched. Attempted unknown, fetched unknown, missing unknown, capped unknown, newest age unknown",
    );
    expect(t.mode).toBe("Mode: unknown");
    expect(t.accounts).toBe("X accounts: unknown of unknown active");
    expect(t.disk).toBe("Free disk: unknown");
    for (const v of Object.values(t)) expect(v).not.toMatch(/NaN|undefined|null/);
  });

  it("treats an unparseable timestamp as unknown", () => {
    expect(text(row(health({ last_unit_at: "garbage" }))).last_unit).toBe("Last unit: unknown");
  });

  it("shows missing reasons unknown when missing > 0 but reasons absent", () => {
    expect(text(row(health({ missing_reasons: null }))).completeness).toContain("missing 5 (reasons unknown)");
  });

  it("omits the accounts line for a source without an account pool", () => {
    const t = text(row(health({ accounts_active: null, accounts_total: null, accounts: [] }), { id: "reddit" }));
    expect(t.accounts).toBeUndefined();
  });
});
