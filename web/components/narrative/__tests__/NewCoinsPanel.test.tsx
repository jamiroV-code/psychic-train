import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { NewCoinsPanel } from "@/components/narrative/NewCoinsPanel";
import type { OnboardingResponse } from "@/lib/types/discovery";

const fixture: OnboardingResponse = {
  mode: "shadow", as_of: "2026-11-01", status: "ok", probation_days: 14, exit_band_rank: 120, exit_days: 7,
  coins: [{ symbol: "NEW", state: "watching", days_in_top100: 3, class: "unknown", class_source: "auto",
    class_evidence: { reason: "no categories" },
    sources: {
      wikipedia: { state: "name", value: "<script>not executable</script>", reason: "" },
      trends: { state: "pending", value: null, reason: "volume history 20 of 66 days" },
      reddit_x: { state: "missing", value: null, reason: "no name resolved" },
    },
    pending: [{ source: "trends", reason: "volume history 20 of 66 days" }],
    proposal: [{ narrative: "defi", category: "decentralized-finance" }],
  }],
};

describe("NewCoinsPanel", () => {
  it("loads fixture evidence, names, missing reasons and proposals as text", async () => {
    const { container } = render(<NewCoinsPanel fetchOnboarding={() => Promise.resolve(fixture)} />);
    expect(screen.getByRole("status").textContent).toContain("Loading");
    await waitFor(() => expect(screen.getByTestId("onboarding-shadow")).toBeTruthy());
    expect(screen.getByText("NEW")).toBeTruthy();
    expect(screen.getByText(/3 of 14/)).toBeTruthy();
    expect(screen.getAllByText(/volume history 20 of 66 days/).length).toBeGreaterThan(0);
    expect(screen.getByText(/no categories/)).toBeTruthy();
    expect(screen.getByText(/defi/)).toBeTruthy();
    expect(screen.getByText("<script>not executable</script>")).toBeTruthy();
    expect(container.querySelector("script")).toBeNull();
  });

  it("shows none when nothing awaits review and omits shadow banner in enforce", async () => {
    render(<NewCoinsPanel fetchOnboarding={() => Promise.resolve({ ...fixture, mode: "enforce",
      coins: [{ ...fixture.coins[0], pending: [], proposal: [] }] })} />);
    await waitFor(() => expect(screen.getByText("NEW")).toBeTruthy());
    expect(screen.getByText("Pending: none")).toBeTruthy();
    expect(screen.queryByTestId("onboarding-shadow")).toBeNull();
  });

  it.each(["no-ledger", "corrupt"] as const)("explains %s", async (status) => {
    render(<NewCoinsPanel fetchOnboarding={() => Promise.resolve({ ...fixture, status, coins: [] })} />);
    await waitFor(() => expect(screen.getByTestId("onboarding-unavailable")).toBeTruthy());
  });

  it("retries a failed read without exposing exception text", async () => {
    const fetcher = vi.fn().mockRejectedValueOnce(new Error("private error")).mockResolvedValue(fixture);
    render(<NewCoinsPanel fetchOnboarding={fetcher} />);
    await waitFor(() => expect(screen.getByRole("alert")).toBeTruthy());
    expect(screen.queryByText(/private error/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(screen.getByText("NEW")).toBeTruthy());
  });
});
