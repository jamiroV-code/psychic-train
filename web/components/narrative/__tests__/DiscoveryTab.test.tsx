import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DiscoveryTab } from "@/components/narrative/DiscoveryTab";
import type {
  DiscoveryCategory,
  DiscoveryReason,
  DiscoveryResponse,
  DiscoverySourcesResponse,
  DiscoveryWindow,
} from "@/lib/types/discovery";

const category = (id: string, over: Partial<DiscoveryCategory> = {}): DiscoveryCategory => ({
  id,
  name: `Category ${id}`,
  score: 12.5,
  median: 9.1,
  coins_used: 3,
  gaining_count: 2,
  ranked: true,
  coins: [
    {
      symbol: "AAA", change: 20, raw_change: 31, covered_weight: 35, rising_weight: 25, trigger: true,
      sources: [
        { source: "wikipedia", change: 42.4, as_of: "2026-10-15" },
        { source: "coingecko", change: 3, as_of: "2026-10-15" },
        { source: "trends", change: -18.2, as_of: "2026-10-14" },
      ],
    },
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
  shown_size: 50,
  excluded: { exclusion_list: 7, below_volume_floor: 30, no_category: 2, no_source_data: 1 },
  min_category_coins: 3,
  rising_threshold_pct: 10,
  min_covered_weight: 30,
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

  it("shows the live weight and one Trigger pill, with coverage as 'x / 100'", async () => {
    render(<DiscoveryTab fetchDiscovery={() => Promise.resolve(resp())} />);
    await screen.findByTestId("discovery-table");
    expect(screen.getByTestId("discovery-live-weight")).toHaveTextContent("Live weight today: 35 of 100");
    fireEvent.click(within(screen.getByTestId("discovery-row-high")).getByRole("button"));
    const coins = screen.getByTestId("discovery-coins-high");
    expect(within(coins).getAllByRole("columnheader").map((h) => h.textContent)).toEqual([
      "Coin", "Score", "Signal", "Sources", "Coverage",
    ]);
    for (const h of within(coins).getAllByRole("columnheader").slice(1)) expect(h.getAttribute("title")?.length).toBeGreaterThan(10);
    expect(within(coins).getByText("35 / 100")).toHaveAttribute("title", expect.stringContaining("30 are needed"));
    expect(within(coins).getByText("25 / 100")).toBeInTheDocument();
    expect(within(coins).getAllByText("Trigger")).toHaveLength(1);
    expect(coins.textContent).not.toContain("covers");
  });

  it("shows 'low data' under the coverage floor, a dash otherwise, and a trigger never reads low data", async () => {
    const coin = (symbol: string, covered: number, trigger: boolean) => ({
      symbol, change: 1, raw_change: 1, covered_weight: covered, rising_weight: 0, trigger, sources: [],
    });
    const c = category("x", { coins: [coin("LOW", 25, false), coin("MID", 40, false), coin("TRG", 25, true)] });
    render(<DiscoveryTab fetchDiscovery={() => Promise.resolve(resp({ categories: [c] }))} />);
    fireEvent.click(await within(await screen.findByTestId("discovery-row-x")).findByRole("button"));
    const rows = within(screen.getByTestId("discovery-coins-x")).getAllByRole("row").slice(1);
    const signal = (i: number) => rows[i].querySelectorAll("td")[2].textContent;
    expect([signal(0), signal(1), signal(2)]).toEqual(["low data", "\u2014", "Trigger"]);
  });

  it("shows one chip per source with data, signed and coloured against the rising threshold", async () => {
    render(<DiscoveryTab fetchDiscovery={() => Promise.resolve(resp())} />);
    await screen.findByTestId("discovery-table");
    fireEvent.click(within(screen.getByTestId("discovery-row-high")).getByRole("button"));
    const coins = screen.getByTestId("discovery-coins-high");
    const wiki = within(coins).getByText("Wiki +42.4%");
    const cg = within(coins).getByText("CG volume +3.0%");
    const trends = within(coins).getByText("Trends -18.2%");
    expect(wiki.className).toContain("discovery-chip--rising");
    expect(cg.className).toContain("discovery-chip--flat");
    expect(trends.className).toContain("discovery-chip--falling");
    expect(within(coins).queryByText(/Reddit/)).toBeNull();
    expect(within(coins).getAllByText(/^(Wiki|CG volume|Trends) /)).toHaveLength(3);
  });

  it("says how many of the top coins are shown and why the others are not", async () => {
    render(<DiscoveryTab fetchDiscovery={() => Promise.resolve(resp())} />);
    const line = await screen.findByTestId("discovery-coverage");
    expect(line).toHaveTextContent("50 of 90 top coins shown: the others are excluded (30 below the volume floor, 7 exchange tokens and other exclusions, 2 in none of the categories, 1 no source data yet)");
  });

  it("shows only the totals when nothing is excluded", async () => {
    render(<DiscoveryTab fetchDiscovery={() => Promise.resolve(resp({ shown_size: 90, universe_size: 90 }))} />);
    expect(await screen.findByTestId("discovery-coverage")).toHaveTextContent(/^90 of 90 top coins shown$/);
  });

  it("lists categories with too few coins apart, unranked, with no score and no chart", async () => {
    const small = category("tiny", { score: 99, median: 99, coins_used: 1, ranked: false, coins: [category("x").coins[0]] });
    const h = {
      fetchCoinHistory: vi.fn(), fetchCategoryHistory: vi.fn(), fetchPrice: vi.fn(),
    };
    render(<DiscoveryTab fetchDiscovery={() => Promise.resolve(resp({ categories: [category("high", { score: 40 }), small] }))} history={h} />);
    await screen.findByTestId("discovery-table");
    expect(screen.queryByTestId("discovery-row-tiny")).toBeNull();
    const group = screen.getByTestId("discovery-unranked");
    expect(group).toHaveTextContent("Too few coins to rank (need 3)");
    expect(within(group).getByTestId("discovery-unranked-tiny")).toHaveTextContent("Category tiny1 coin: AAA");
    expect(group.textContent).not.toContain("99");
    expect(within(group).queryByRole("button")).toBeNull();
    expect(within(screen.getByTestId("discovery-table")).getAllByTestId(/^discovery-row-/)).toHaveLength(1);
    expect(h.fetchCategoryHistory).not.toHaveBeenCalled();
  });

  it("never opens the category chart for an unranked category, even when selected", async () => {
    const small = category("tiny", { ranked: false, coins_used: 1 });
    const h = { fetchCoinHistory: vi.fn(), fetchCategoryHistory: vi.fn(), fetchPrice: vi.fn() };
    render(<DiscoveryTab fetchDiscovery={() => Promise.resolve(resp({ categories: [category("high"), small] }))} history={h} />);
    await screen.findByTestId("discovery-table");
    expect(screen.queryByTestId("discovery-history")).toBeNull();
    expect(h.fetchCategoryHistory).not.toHaveBeenCalled();
  });

  describe("sources panel", () => {
    const src = (over: Partial<DiscoverySourcesResponse> = {}): DiscoverySourcesResponse => ({
      as_of: "2026-10-17", universe_size: 100, eligible_size: 50, live_sources: 2, total_sources: 7, live_weight: 35,
      newest: "2026-10-17",
      sources: [
        { id: "wikipedia", label: "Wikipedia pageviews", kind: "weighted", weight: 25, state: "ok", newest: "2026-10-17", history_days: 99, coins_with_data: 38, eligible_size: 50, note: "" },
        { id: "reddit", label: "Reddit", kind: "weighted", weight: 15, state: "not-probed", newest: null, history_days: 0, coins_with_data: 0, eligible_size: 50, note: "not probed yet" },
        { id: "universe", label: "Top-100 universe", kind: "helper", weight: null, state: "ok", newest: "2026-10-17", history_days: 0, coins_with_data: 100, eligible_size: 0, note: "" },
      ],
      ...over,
    });

    it("is collapsed with a one-line summary and a status dot, and expands to the table", async () => {
      render(<DiscoveryTab fetchDiscovery={() => Promise.resolve(resp())} fetchSources={() => Promise.resolve(src())} />);
      const panel = await screen.findByTestId("sources-panel");
      expect(panel).not.toHaveAttribute("open");
      expect(screen.getByTestId("sources-summary")).toHaveTextContent("Sources: 2 of 7 live, 35 of 100 weight, newest data 2026-10-17");
      expect(screen.getByTestId("sources-dot")).toHaveAttribute("data-tone", "partial");
      const table = screen.getByTestId("sources-table");
      expect(within(table).getAllByRole("columnheader").map((h) => h.textContent)).toEqual([
        "Source", "Weight", "Status", "Coins", "Days", "Newest", "Note",
      ]);
      const wiki = screen.getByTestId("sources-row-wikipedia");
      expect(wiki).toHaveTextContent("Wikipedia pageviews25ok38 / 50992026-10-17");
      expect(screen.getByTestId("sources-row-reddit")).toHaveTextContent("not probed");
      expect(screen.getByTestId("sources-row-reddit")).toHaveTextContent("not probed yet");
    });

    it("has a red dot with nothing live and a green dot with everything live", async () => {
      const { rerender } = render(<DiscoveryTab fetchDiscovery={() => Promise.resolve(resp())} fetchSources={() => Promise.resolve(src({ live_sources: 0, live_weight: 0, newest: null }))} />);
      expect(await screen.findByTestId("sources-dot")).toHaveAttribute("data-tone", "none");
      expect(screen.getByTestId("sources-summary")).toHaveTextContent("Sources: 0 of 7 live, 0 of 100 weight");
      expect(screen.getByTestId("sources-summary").textContent).not.toContain("newest");
      rerender(<div />);
      render(<DiscoveryTab fetchDiscovery={() => Promise.resolve(resp())} fetchSources={() => Promise.resolve(src({ live_sources: 7, live_weight: 100 }))} />);
      expect((await screen.findAllByTestId("sources-dot")).at(-1)).toHaveAttribute("data-tone", "ok");
    });

    it("shows plain loading and error states without breaking the table", async () => {
      const { unmount } = render(<DiscoveryTab fetchDiscovery={() => Promise.resolve(resp())} fetchSources={() => new Promise(() => undefined)} />);
      expect(screen.getByTestId("sources-loading")).toBeInTheDocument();
      expect(await screen.findByTestId("discovery-table")).toBeInTheDocument();
      unmount();
      render(<DiscoveryTab fetchDiscovery={() => Promise.resolve(resp())} fetchSources={() => Promise.reject(new Error("boom"))} />);
      expect(await screen.findByTestId("sources-error")).toHaveTextContent("Source status could not be loaded.");
      expect(await screen.findByTestId("discovery-table")).toBeInTheDocument();
    });
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
      expect(screen.getByTestId("discovery-coin-high-AAA").closest("tr")).toHaveAttribute("aria-current", "true");
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
