import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { NarrativeTabs } from "@/components/narrative/NarrativeTabs";
import type { AttentionResponse, AttentionWindow, BasketAttention } from "@/lib/types/attention";

vi.mock("@/lib/use-simple-lines", () => ({ useSimpleLines: () => undefined }));

const basket = (id: string, over: Partial<BasketAttention> = {}): BasketAttention => ({
  id,
  name: `Basket ${id}`,
  score: 40,
  change: 2,
  breadth: 0.5,
  coverage: "covers 3 of 4",
  series: [{ date: "2026-10-01", value: 1 }],
  coins: [],
  status: "ok",
  reason: "",
  universe_size: 4,
  ...over,
});

const resp = (baskets: BasketAttention[], window: AttentionWindow = 30): AttentionResponse => ({
  window,
  as_of: "2026-10-16",
  membership_as_of: "2026-10-10",
  baskets,
});

describe("NarrativeTabs", () => {
  it("has three tabs, My baskets selected first", async () => {
    render(<NarrativeTabs fetchAttention={() => Promise.resolve(resp([basket("a")]))} />);
    const tabs = screen.getAllByRole("tab");
    expect(tabs.map((t) => t.textContent)).toEqual(["My baskets", "Discovery", "New coins"]);
    expect(tabs[0].getAttribute("aria-selected")).toBe("true");
    await waitFor(() => expect(screen.getByTestId("attention-table")).toBeTruthy());
  });

  it("fetches 30 days first, then the chosen window", async () => {
    const fetchAttention = vi.fn((w: AttentionWindow) => Promise.resolve(resp([basket("a")], w)));
    render(<NarrativeTabs fetchAttention={fetchAttention} />);
    await waitFor(() => expect(fetchAttention).toHaveBeenCalledWith(30));
    fireEvent.click(screen.getByTestId("attention-window-90"));
    await waitFor(() => expect(fetchAttention).toHaveBeenCalledWith(90));
  });

  it("shows loading, then error, with no table", async () => {
    render(<NarrativeTabs fetchAttention={() => Promise.reject(new Error("boom"))} />);
    expect(screen.getByTestId("attention-loading")).toBeTruthy();
    await waitFor(() => expect(screen.getByTestId("attention-error").textContent).toContain("could not be loaded"));
    expect(screen.getByTestId("attention-error").textContent).not.toContain("boom");
    expect(screen.queryByTestId("attention-table")).toBeNull();
  });

  it("retries after an error", async () => {
    const fetchAttention = vi
      .fn()
      .mockRejectedValueOnce(new Error("boom"))
      .mockResolvedValue(resp([basket("a")]));
    render(<NarrativeTabs fetchAttention={fetchAttention} />);
    await waitFor(() => expect(screen.getByTestId("attention-retry")).toBeTruthy());
    fireEvent.click(screen.getByTestId("attention-retry"));
    await waitFor(() => expect(screen.getByTestId("attention-table")).toBeTruthy());
    expect(fetchAttention).toHaveBeenCalledTimes(2);
  });

  it("shows the empty state with a screener link", async () => {
    render(<NarrativeTabs fetchAttention={() => Promise.resolve(resp([]))} />);
    await waitFor(() => expect(screen.getByTestId("attention-empty")).toBeTruthy());
    expect(screen.getByRole("link", { name: /screener/i }).getAttribute("href")).toBe("/screener");
  });

  it("shows partial and ranking-off notes", async () => {
    const { unmount } = render(
      <NarrativeTabs fetchAttention={() => Promise.resolve(resp([basket("a"), basket("b", { status: "no-data", score: null })]))} />,
    );
    await waitFor(() => expect(screen.getByTestId("attention-partial")).toBeTruthy());
    unmount();
    render(
      <NarrativeTabs fetchAttention={() => Promise.resolve(resp([basket("a", { status: "no-data", reason: "reference-missing" })]))} />,
    );
    await waitFor(() => expect(screen.getByTestId("attention-ranking-off")).toBeTruthy());
  });

  it("Discovery tab shows the discovery panel, not the baskets chart", async () => {
    render(<NarrativeTabs fetchAttention={() => Promise.resolve(resp([]))} fetchDiscovery={() => new Promise(() => undefined)} />);
    fireEvent.click(screen.getByRole("tab", { name: "Discovery" }));
    expect(screen.getByTestId("discovery-loading")).toBeTruthy();
    expect(screen.queryByTestId("attention-chart")).toBeNull();
  });

  it("loads the New coins tab from the injected read-only response", async () => {
    render(<NarrativeTabs fetchAttention={() => Promise.resolve(resp([]))}
      fetchOnboarding={() => Promise.resolve({ mode: "shadow", as_of: null, status: "no-ledger",
        probation_days: 14, exit_band_rank: 120, exit_days: 7, coins: [] })} />);
    fireEvent.click(screen.getByRole("tab", { name: "New coins" }));
    await waitFor(() => expect(screen.getByTestId("onboarding-unavailable")).toBeTruthy());
    expect(screen.queryByTestId("attention-chart")).toBeNull();
  });

  it("carries no verdict vocabulary or badge class", async () => {
    const { container } = render(<NarrativeTabs fetchAttention={() => Promise.resolve(resp([basket("a")]))} />);
    await waitFor(() => expect(screen.getByTestId("attention-table")).toBeTruthy());
    const banned = [["trust", "weight"].join("_"), "trigger" + "ed", "confirm" + "ed", "bad" + "ge"];
    for (const word of banned) expect(container.innerHTML.toLowerCase()).not.toContain(word);
  });
});
