import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DiscoveryTab } from "@/components/narrative/DiscoveryTab";
import type {
  DiscoveryCategory,
  DiscoveryReason,
  DiscoveryResponse,
  DiscoveryWindow,
} from "@/lib/types/discovery";

const category = (id: string, over: Partial<DiscoveryCategory> = {}): DiscoveryCategory => ({
  id,
  name: `Category ${id}`,
  score: 12.5,
  median: 9.1,
  coins_used: 3,
  gaining_count: 2,
  coins: [
    { symbol: "AAA", change: 20, raw_change: 31, covered_weight: 35, rising_weight: 25, trigger: true, sources: [] },
    { symbol: "BBB", change: 5, raw_change: 5, covered_weight: 25, rising_weight: 0, trigger: false, sources: [] },
  ],
  ...over,
});

const resp = (over: Partial<DiscoveryResponse> = {}): DiscoveryResponse => ({
  window: 30,
  as_of: "2026-10-16",
  categories_as_of: "2026-10-10",
  status: "ok",
  reason: "",
  universe_size: 90,
  eligible_size: 60,
  categories: [category("low", { score: 3 }), category("high", { score: 40 })],
  ...over,
});

const noData = (reason: DiscoveryReason): DiscoveryResponse =>
  resp({ status: "no-data", reason, categories: [] });

describe("DiscoveryTab", () => {
  it("shows loading first, then a ranked table with four columns", async () => {
    render(<DiscoveryTab fetchDiscovery={() => Promise.resolve(resp())} />);
    expect(screen.getByTestId("discovery-loading")).toBeInTheDocument();
    const table = await screen.findByTestId("discovery-table");
    expect(within(table).getAllByRole("columnheader")).toHaveLength(4);
    const rows = within(table).getAllByTestId(/^discovery-row-/);
    expect(rows.map((r) => r.getAttribute("data-testid"))).toEqual(["discovery-row-high", "discovery-row-low"]);
    expect(screen.queryByTestId("discovery-loading")).toBeNull();
  });

  it("has at most one legend and no badge class", async () => {
    const { container } = render(<DiscoveryTab fetchDiscovery={() => Promise.resolve(resp())} />);
    await screen.findByTestId("discovery-table");
    expect(container.querySelectorAll('[data-testid="discovery-legend"]').length).toBeLessThanOrEqual(1);
    expect(container.querySelectorAll('[class*="badge"]')).toHaveLength(0);
  });

  it("expands a category to its coins", async () => {
    render(<DiscoveryTab fetchDiscovery={() => Promise.resolve(resp())} />);
    await screen.findByTestId("discovery-table");
    expect(screen.queryByTestId("discovery-coins-high")).toBeNull();
    fireEvent.click(within(screen.getByTestId("discovery-row-high")).getByRole("button"));
    const coins = screen.getByTestId("discovery-coins-high");
    expect(within(coins).getByText("AAA")).toBeInTheDocument();
    expect(within(coins).getByText("BBB")).toBeInTheDocument();
  });

  it.each([
    ["categories-missing"],
    ["reference-missing"],
    ["no-attention-data"],
  ] as const)("renders the %s no-data state with one plain line", async (reason) => {
    render(<DiscoveryTab fetchDiscovery={() => Promise.resolve(noData(reason))} />);
    const line = await screen.findByTestId(`discovery-nodata-${reason}`);
    expect(line.textContent?.trim().length).toBeGreaterThan(0);
    expect(screen.queryByTestId("discovery-table")).toBeNull();
  });

  it("renders the error state and retries", async () => {
    const fetchDiscovery = vi
      .fn<(w: DiscoveryWindow) => Promise<DiscoveryResponse>>()
      .mockRejectedValueOnce(new Error("boom"))
      .mockResolvedValue(resp());
    render(<DiscoveryTab fetchDiscovery={fetchDiscovery} />);
    expect(await screen.findByTestId("discovery-error")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("discovery-retry"));
    expect(await screen.findByTestId("discovery-table")).toBeInTheDocument();
    expect(fetchDiscovery).toHaveBeenCalledTimes(2);
  });

  it("refetches when the window changes", async () => {
    const fetchDiscovery = vi.fn((w: DiscoveryWindow) => Promise.resolve(resp({ window: w })));
    render(<DiscoveryTab fetchDiscovery={fetchDiscovery} />);
    await screen.findByTestId("discovery-table");
    expect(fetchDiscovery).toHaveBeenLastCalledWith(30);
    fireEvent.click(screen.getByTestId("discovery-window-7"));
    await waitFor(() => expect(fetchDiscovery).toHaveBeenLastCalledWith(7));
    fireEvent.click(screen.getByTestId("discovery-window-90"));
    await waitFor(() => expect(fetchDiscovery).toHaveBeenLastCalledWith(90));
    expect(screen.getByTestId("discovery-window-90")).toHaveAttribute("aria-pressed", "true");
  });

  it("matches My baskets: title, joined control, as-of date, unit labels", async () => {
    render(<DiscoveryTab fetchDiscovery={() => Promise.resolve(resp())} />);
    await screen.findByTestId("discovery-table");
    expect(screen.getByRole("heading", { name: "Attention by category" })).toBeInTheDocument();
    expect(screen.getByTestId("discovery-window-30").className).toBe("basket-seg__btn");
    expect(screen.getByTestId("discovery-as-of")).toHaveTextContent("as of 2026-10-16");
    expect(screen.getByRole("columnheader", { name: "Score (%)" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Median (%)" })).toBeInTheDocument();
  });

  it("shows coverage, a trigger marker and the live weight", async () => {
    render(<DiscoveryTab fetchDiscovery={() => Promise.resolve(resp())} />);
    await screen.findByTestId("discovery-table");
    expect(screen.getByTestId("discovery-live-weight")).toHaveTextContent("Live weight today: 35 of 100");
    fireEvent.click(within(screen.getByTestId("discovery-row-high")).getByRole("button"));
    const coins = screen.getByTestId("discovery-coins-high");
    expect(within(coins).getByText("covers 35% of weight, 71% rising")).toBeInTheDocument();
    expect(within(coins).getByText("covers 25% of weight, 0% rising")).toBeInTheDocument();
    expect(within(coins).getAllByText("Trigger")).toHaveLength(1);
  });

  it("shows live weight 0 when no coin has data", async () => {
    render(<DiscoveryTab fetchDiscovery={() => Promise.resolve(resp({ categories: [] }))} />);
    expect(await screen.findByTestId("discovery-live-weight")).toHaveTextContent("Live weight today: 0 of 100");
  });

  it("folds categories with zero coins used into one collapsed line", async () => {
    const categories = [
      category("high", { score: 40 }),
      category("e1", { score: null, median: null, coins_used: 0, coins: [] }),
      category("e2", { score: null, median: null, coins_used: 0, coins: [] }),
    ];
    render(<DiscoveryTab fetchDiscovery={() => Promise.resolve(resp({ categories }))} />);
    await screen.findByTestId("discovery-table");
    expect(screen.queryByTestId("discovery-row-e1")).toBeNull();
    const folded = screen.getByTestId("discovery-empty-categories");
    expect(folded).toHaveTextContent("2 categories without data");
    expect(folded).not.toHaveAttribute("open");
  });

  describe("history chart", () => {
    const dates = ["2026-10-14", "2026-10-15"];
    const coinHist = (window: DiscoveryWindow) => ({
      kind: "coin" as const, id: "AAA", window, as_of: "2026-10-15", status: "ok" as const, reason: "",
      min_history_days: 30, min_covered_weight: 30, history_days: {},
      days: dates.map((date, i) => ({ date, score: 10 + i, covered_weight: 35, rising_weight: 25, trigger: i === 1, thin: false })),
    });
    const catHist = (window: DiscoveryWindow) => ({
      kind: "category" as const, id: "high", window, as_of: "2026-10-15", status: "ok" as const, reason: "",
      min_history_days: 30, min_covered_weight: 30, history_days: {},
      days: dates.map((date, i) => ({ date, score: 5 + i, coins_used: 2, triggered_count: i, triggered_share: i / 2 })),
    });
    const history = () => ({
      fetchCoinHistory: vi.fn((_s: string, w: DiscoveryWindow) => Promise.resolve(coinHist(w))),
      fetchCategoryHistory: vi.fn((_i: string, w: DiscoveryWindow) => Promise.resolve(catHist(w))),
      fetchPrice: vi.fn((s: string, w: DiscoveryWindow) =>
        Promise.resolve({ symbol: s, window: w, status: "no-data" as const, last_date: null, days: [] })),
    });

    it("opens the category chart when a category opens, then a coin chart on a coin click", async () => {
      const h = history();
      render(<DiscoveryTab fetchDiscovery={() => Promise.resolve(resp())} history={h} />);
      await screen.findByTestId("discovery-table");
      expect(screen.queryByTestId("discovery-history")).toBeNull();
      fireEvent.click(within(screen.getByTestId("discovery-row-high")).getByRole("button"));
      await screen.findByTestId("history-share-line");
      expect(h.fetchCategoryHistory).toHaveBeenCalledWith("high", 30);
      expect(screen.getByTestId("discovery-row-high")).toHaveAttribute("aria-current", "true");
      fireEvent.click(screen.getByTestId("discovery-coin-high-AAA"));
      await screen.findByTestId("history-band");
      expect(h.fetchCoinHistory).toHaveBeenCalledWith("AAA", 30);
      expect(screen.getByTestId("discovery-coin-high-AAA").closest("li")).toHaveAttribute("aria-current", "true");
      expect(screen.getByTestId("discovery-row-high")).not.toHaveAttribute("aria-current");
    });

    it("refetches the open chart when the shared window changes, and closes", async () => {
      const h = history();
      render(<DiscoveryTab fetchDiscovery={(w) => Promise.resolve(resp({ window: w }))} history={h} />);
      await screen.findByTestId("discovery-table");
      fireEvent.click(within(screen.getByTestId("discovery-row-high")).getByRole("button"));
      fireEvent.click(await screen.findByTestId("discovery-coin-high-AAA"));
      await screen.findByTestId("history-band");
      fireEvent.click(screen.getByTestId("discovery-window-90"));
      await waitFor(() => expect(h.fetchCoinHistory).toHaveBeenLastCalledWith("AAA", 90));
      await screen.findByTestId("history-band");
      fireEvent.click(screen.getByTestId("history-close"));
      expect(screen.queryByTestId("discovery-history")).toBeNull();
    });
  });
});
