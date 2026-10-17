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
    { symbol: "AAA", change: 20, raw_change: 31, gaining: true, sources_used: 3, sources_gaining: 2 },
    { symbol: "BBB", change: 5, raw_change: 5, gaining: false, sources_used: 2, sources_gaining: 1 },
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
});
