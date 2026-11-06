import { describe, expect, it } from "vitest";
import { accountText } from "@/lib/source-health";
import type { DiscoveryAccountHealth } from "@/lib/types/discovery";

const base: DiscoveryAccountHealth = { label: "acct-1", state: "active", reason: null, last_used: null, cookie_age_days: null };

describe("B2 account proxy formatting", () => {
  it.each(["direct", "unknown", "healthy", "quarantined", "blocked"] as const)("shows explicit %s without changing account state", (proxy_state) => {
    const text = accountText({ ...base, proxy_state, proxy_reason: "proxy_region", region: "US-CA", connection_style: "curl" });
    expect(text).toContain("acct-1 active");
    expect(text).toContain(`proxy ${proxy_state} (proxy_region)`);
    expect(text).toContain("region US-CA, connection style curl");
  });
  it("never infers direct or healthy from absent historical values", () => {
    const text = accountText(base);
    expect(text).toContain("proxy unknown");
    expect(text).not.toMatch(/proxy (healthy|direct)/);
    expect(text).toContain("proxy checked unknown, quarantine until unknown");
  });
  it("does not echo unsafe unexpected proxy fields even from a malformed server payload", () => {
    const marker = "https://user:SECRET@192.0.2.1/private";
    const account = { ...base, proxy_state: marker, proxy_reason: marker, proxy_id: marker, region: marker,
      connection_style: marker, identity_revision: marker, proxy_checked_at: marker, proxy_quarantine_until: marker };
    const text = accountText(account as unknown as DiscoveryAccountHealth);
    expect(text).not.toMatch(/SECRET|192\.0\.2\.1|https:|\/private/);
    expect(text).toContain("proxy unknown");
  });
});
