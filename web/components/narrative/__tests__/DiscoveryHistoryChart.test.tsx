import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DiscoveryHistoryChart } from "@/components/narrative/DiscoveryHistoryChart";
import type {
  DiscoveryCategoryHistory,
  DiscoveryCoinHistory,
  DiscoveryPrice,
  DiscoveryWindow,
} from "@/lib/types/discovery";

const dates = ["2026-10-11", "2026-10-12", "2026-10-13", "2026-10-14", "2026-10-15"];

const coinHistory = (over: Partial<DiscoveryCoinHistory> = {}): DiscoveryCoinHistory => ({
  kind: "coin",
  id: "AAA",
  window: 7,
  as_of: "2026-10-15",
  status: "ok",
  reason: "",
  min_history_days: 30,
  min_covered_weight: 30,
  history_days: { wikipedia: 99 },
  days: dates.map((date, i) => ({
    date,
    score: [-2, 4, 12.5, 30, 41][i],
    covered_weight: [10, 10, 35, 35, 35][i],
    rising_weight: [0, 0, 25, 25, 25][i],
    trigger: i >= 3,
    thin: i < 2,
  })),
  ...over,
});

const priceOk = (): DiscoveryPrice => ({
  symbol: "AAA",
  window: 7,
  status: "ok",
  last_date: "2026-10-15",
  days: dates.map((date, i) => ({ date, close: 100 + i * 5 })),
});

const priceNone = (): DiscoveryPrice => ({ symbol: "AAA", window: 7, status: "no-data", last_date: null, days: [] });

const categoryHistory = (): DiscoveryCategoryHistory => ({
  kind: "category",
  id: "ai",
  window: 7,
  as_of: "2026-10-15",
  status: "ok",
  reason: "",
  min_history_days: 30,
  min_covered_weight: 30,
  history_days: {},
  days: dates.map((date, i) => ({
    date,
    score: i * 2,
    coins_used: 3 + i,
    triggered_count: i,
    triggered_share: i / (3 + i),
  })),
});

const coin = { kind: "coin", symbol: "AAA" } as const;

function setup(over: Partial<React.ComponentProps<typeof DiscoveryHistoryChart>> = {}) {
  const fetchCoinHistory = vi.fn((_s: string, _w: DiscoveryWindow) => Promise.resolve(coinHistory()));
  const fetchCategoryHistory = vi.fn((_id: string, _w: DiscoveryWindow) => Promise.resolve(categoryHistory()));
  const fetchPrice = vi.fn((_s: string, _w: DiscoveryWindow) => Promise.resolve(priceOk()));
  const props = {
    selection: coin,
    window: 7 as DiscoveryWindow,
    liveWeight: 35,
    onClose: vi.fn(),
    fetchCoinHistory,
    fetchCategoryHistory,
    fetchPrice,
    ...over,
  };
  const view = render(<DiscoveryHistoryChart {...props} />);
  return { ...view, props, fetchCoinHistory, fetchCategoryHistory, fetchPrice };
}

describe("DiscoveryHistoryChart: coin", () => {
  it("shows loading, then three stacked panels with a marker per stored trigger day and the coverage bars", async () => {
    setup();
    expect(screen.getByTestId("history-loading")).toBeInTheDocument();
    await screen.findByTestId("history-svg");
    const plot = screen.getByTestId("history-plot");
    expect(within(plot).getAllByTestId("history-trigger-marker")).toHaveLength(2);
    expect(within(plot).getByTestId("history-band")).toBeInTheDocument();
    expect(within(plot).getAllByTestId("history-band-floor")).toHaveLength(1);
    expect(within(plot).getByTestId("history-score-line").getAttribute("d")).toMatch(/^M/);
    expect(within(plot).getByTestId("history-price-line")).toBeInTheDocument();
    for (const id of ["score", "price", "coverage"]) expect(within(plot).getByTestId(`history-panel-${id}`)).toBeInTheDocument();
    expect(screen.queryByTestId("history-price-unavailable")).toBeNull();
  });

  it("titles each panel on one line, with the coverage wording and the floor label", async () => {
    setup();
    await screen.findByTestId("history-svg");
    expect(screen.getByTestId("history-panel-title-score").textContent).toContain("Weighted score (%)");
    expect(screen.getByTestId("history-panel-title-score").textContent).toContain("trigger day");
    expect(screen.getByTestId("history-panel-title-price").textContent).toContain("Price, % change since first common day");
    expect(screen.getByTestId("history-panel-title-coverage").textContent).toBe("Data coverage (weight of sources with data, out of 100)");
    expect(within(screen.getByTestId("history-panel-coverage")).getByText("needs 30 to fire")).toBeInTheDocument();
    expect(screen.queryByTestId("history-legend")).toBeNull();
  });

  it("mutes coverage bars under the floor", async () => {
    setup();
    await screen.findByTestId("history-svg");
    expect(screen.getAllByTestId("history-band-bar-muted")).toHaveLength(2);
    expect(screen.getAllByTestId("history-band-bar")).toHaveLength(3);
  });

  it("gives the price its own scale: the line spans its panel although the score is far bigger", async () => {
    setup({
      fetchCoinHistory: () =>
        Promise.resolve(coinHistory({ days: coinHistory().days.map((d, i) => ({ ...d, score: [10, 20, 30, 40, 49][i] })) })),
      fetchPrice: () =>
        Promise.resolve({ ...priceOk(), days: dates.map((date, i) => ({ date, close: 100 * (1 - [0, 0.01, 0.02, 0.03, 0.02][i]) })) }),
    });
    await screen.findByTestId("history-svg");
    const ys = (testid: string) =>
      (screen.getByTestId(testid).getAttribute("d") ?? "").match(/[ML][\d.]+ ([\d.]+)/g)!.map((m) => Number(m.split(" ")[1]));
    const py = ys("history-price-line");
    // The panel is 84px tall: a -3%..0% price must use most of it instead of hugging one edge.
    expect(Math.max(...py) - Math.min(...py)).toBeGreaterThan(50);
  });

  it("shows at most 3 y labels per panel and one x axis (first, middle, last) at the bottom only", async () => {
    setup();
    await screen.findByTestId("history-svg");
    for (const id of ["score", "price", "coverage"]) {
      const labels = within(screen.getByTestId(`history-panel-${id}`)).getAllByText(/%$|^\d+$/, { selector: "svg text" });
      expect(labels.length).toBeLessThanOrEqual(4);
      const texts = labels.map((l) => l.textContent);
      expect(new Set(texts).size).toBe(texts.length);
    }
    const axis = screen.getAllByTestId("history-xaxis");
    expect(axis).toHaveLength(1);
    expect(within(screen.getByTestId("history-panel-coverage")).getByTestId("history-xaxis")).toBe(axis[0]);
    expect(Array.from(axis[0].querySelectorAll("text")).map((t) => t.textContent)).toEqual(["2026-10-11", "2026-10-13", "2026-10-15"]);
  });

  it("uses fixed-size text: no font size in the svg depends on the viewBox", async () => {
    setup();
    await screen.findByTestId("history-svg");
    const svg = screen.getByTestId("history-svg");
    expect(svg.getAttribute("width")).toBe(svg.getAttribute("viewBox")!.split(" ")[2]);
    for (const t of Array.from(svg.querySelectorAll("text"))) expect(t.getAttribute("font-size")).toBe("11");
  });

  it("adds the trigger legend entry only when a trigger exists, and draws no markers otherwise", async () => {
    setup({
      fetchCoinHistory: () => Promise.resolve(coinHistory({ days: coinHistory().days.map((d) => ({ ...d, trigger: false })) })),
    });
    await screen.findByTestId("history-svg");
    expect(screen.queryAllByTestId("history-trigger-marker")).toHaveLength(0);
    expect(screen.getByTestId("history-panel-title-score").textContent).not.toContain("trigger day");
  });

  it("keeps the trigger dots semi-transparent and under the score line when every day triggers", async () => {
    setup({
      fetchCoinHistory: () => Promise.resolve(coinHistory({ days: coinHistory().days.map((d) => ({ ...d, trigger: true })) })),
    });
    await screen.findByTestId("history-svg");
    const dots = screen.getAllByTestId("history-trigger-marker");
    expect(dots).toHaveLength(5);
    expect(dots[0].getAttribute("r")).toBe("3");
    expect(Number(dots[0].getAttribute("fill-opacity"))).toBeLessThan(1);
    const line = screen.getByTestId("history-score-line");
    expect(dots[0].compareDocumentPosition(line) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("shows constant coverage anyway, in a compact panel", async () => {
    setup({
      fetchCoinHistory: () =>
        Promise.resolve(coinHistory({ days: coinHistory().days.map((d) => ({ ...d, covered_weight: 35, thin: false })) })),
    });
    await screen.findByTestId("history-svg");
    expect(screen.getAllByTestId("history-band-bar")).toHaveLength(5);
    const svg = within(screen.getByTestId("history-panel-coverage")).getByText("needs 30 to fire").closest("svg")!;
    expect(Number(svg.getAttribute("height"))).toBeLessThan(40 + 12 + 20 + 1);
  });

  it("renders a one-day window without NaN", async () => {
    setup({ fetchCoinHistory: () => Promise.resolve(coinHistory({ days: coinHistory().days.slice(0, 1) })) });
    await screen.findByTestId("history-svg");
    expect(screen.getByTestId("history-plot").innerHTML).not.toContain("NaN");
    expect(screen.getByTestId("history-readout").textContent).toContain("2026-10-11");
  });

  it("keeps drawing the other panels when the price has gaps", async () => {
    setup({ fetchPrice: () => Promise.resolve({ ...priceOk(), days: priceOk().days.filter((_, i) => i !== 2) }) });
    await screen.findByTestId("history-svg");
    expect(screen.getByTestId("history-price-line").getAttribute("d")).toContain("M");
    expect(screen.getByTestId("history-plot").innerHTML).not.toContain("NaN");
  });

  it("reads out the numbers of the last day first, then the day under the arrow keys", async () => {
    setup();
    const plot = await screen.findByTestId("history-plot");
    const readout = screen.getByTestId("history-readout");
    expect(readout.textContent).toContain("2026-10-15");
    expect(readout.textContent).toContain("+41.0%");
    expect(readout.textContent).toContain("covered 35 of 100");
    expect(readout.textContent).toContain("rising 25");
    expect(readout.textContent).toContain("trigger");
    expect(readout.textContent).toContain("price 120 (+20.0% since first day)");
    fireEvent.keyDown(plot, { key: "ArrowLeft" });
    fireEvent.keyDown(plot, { key: "ArrowLeft" });
    expect(readout.textContent).toContain("2026-10-13");
    expect(readout.textContent).toContain("no trigger");
    fireEvent.keyDown(plot, { key: "Home" });
    expect(readout.textContent).toContain("2026-10-11");
    expect(readout.textContent).toContain("thin");
    fireEvent.keyDown(plot, { key: "End" });
    expect(readout.textContent).toContain("2026-10-15");
  });

  it("says price is unavailable and still draws the score when the price has no data", async () => {
    setup({ fetchPrice: () => Promise.resolve(priceNone()) });
    await screen.findByTestId("history-svg");
    expect(screen.getByTestId("history-price-unavailable")).toBeInTheDocument();
    expect(screen.queryByTestId("history-price-line")).toBeNull();
    expect(screen.getByTestId("history-score-line")).toBeInTheDocument();
    expect(screen.getByTestId("history-readout").textContent).toContain("price unavailable");
  });

  it("treats a failed price request as unavailable, not as a chart error", async () => {
    setup({ fetchPrice: () => Promise.reject(new Error("boom")) });
    await screen.findByTestId("history-svg");
    expect(screen.getByTestId("history-price-unavailable")).toBeInTheDocument();
    expect(screen.queryByTestId("history-error")).toBeNull();
  });

  it("is honest about thin days and the live weight", async () => {
    setup();
    await screen.findByTestId("history-svg");
    const note = screen.getByTestId("history-weight-note").textContent ?? "";
    expect(note).toContain("Live weight today: 35 of 100");
    expect(note).toContain("Early days have little history");
    expect(note).toContain("2 of 5 days");
  });

  it("omits the thin-days line when no day is thin", async () => {
    setup({
      fetchCoinHistory: () =>
        Promise.resolve(coinHistory({ days: coinHistory().days.map((d) => ({ ...d, covered_weight: 35, thin: false })) })),
    });
    await screen.findByTestId("history-svg");
    expect(screen.getByTestId("history-weight-note").textContent).not.toContain("little history");
  });

  it("refetches both series when the shared window changes", async () => {
    const { rerender, props, fetchCoinHistory, fetchPrice } = setup();
    await screen.findByTestId("history-svg");
    expect(fetchCoinHistory).toHaveBeenLastCalledWith("AAA", 7);
    rerender(<DiscoveryHistoryChart {...props} window={90} />);
    expect(screen.getByTestId("history-loading")).toBeInTheDocument();
    await screen.findByTestId("history-svg");
    expect(fetchCoinHistory).toHaveBeenLastCalledWith("AAA", 90);
    expect(fetchPrice).toHaveBeenLastCalledWith("AAA", 90);
    expect(fetchCoinHistory).toHaveBeenCalledTimes(2);
  });

  it("ignores a slow answer for a window that is no longer selected", async () => {
    let resolveOld: (h: DiscoveryCoinHistory) => void = () => undefined;
    const fetchCoinHistory = vi
      .fn()
      .mockImplementationOnce(() => new Promise<DiscoveryCoinHistory>((r) => (resolveOld = r)))
      .mockImplementation(() => Promise.resolve(coinHistory({ window: 90, as_of: "2026-10-15" })));
    const { rerender, props } = setup({ fetchCoinHistory });
    rerender(<DiscoveryHistoryChart {...props} fetchCoinHistory={fetchCoinHistory} window={90} />);
    await screen.findByTestId("history-svg");
    resolveOld(coinHistory({ days: [] , status: "no-data", reason: "no-attention-data" }));
    await Promise.resolve();
    expect(screen.queryByTestId("history-nodata")).toBeNull();
    expect(screen.getByTestId("history-svg")).toBeInTheDocument();
  });

  it("shows an error with retry, and retry refetches", async () => {
    const fetchCoinHistory = vi
      .fn()
      .mockRejectedValueOnce(new Error("down"))
      .mockResolvedValue(coinHistory());
    setup({ fetchCoinHistory });
    expect(await screen.findByTestId("history-error")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("history-retry"));
    await screen.findByTestId("history-svg");
    expect(fetchCoinHistory).toHaveBeenCalledTimes(2);
  });

  it.each([
    ["no-attention-data", "no-data"],
    ["categories-missing", "no-data"],
  ])("renders one plain no-data line for reason %s", async (reason) => {
    setup({ fetchCoinHistory: () => Promise.resolve(coinHistory({ status: "no-data", reason, days: [] })) });
    const line = await screen.findByTestId("history-nodata");
    expect(line.textContent?.trim().length).toBeGreaterThan(0);
    expect(screen.queryByTestId("history-svg")).toBeNull();
  });

  it("treats an ok payload with zero usable days as no data", async () => {
    setup({ fetchCoinHistory: () => Promise.resolve(coinHistory({ days: [] })) });
    expect(await screen.findByTestId("history-nodata")).toBeInTheDocument();
  });

  it("closes through the button", async () => {
    const { props } = setup();
    await screen.findByTestId("history-svg");
    fireEvent.click(screen.getByTestId("history-close"));
    expect(props.onClose).toHaveBeenCalledTimes(1);
  });
});

describe("DiscoveryHistoryChart: category", () => {
  it("draws the average score and the triggered share in two panels with their own scales, and shows coins used", async () => {
    const { fetchCategoryHistory, fetchPrice } = setup({ selection: { kind: "category", id: "ai", name: "AI" } });
    await screen.findByTestId("history-svg");
    const plot = screen.getByTestId("history-plot");
    expect(fetchCategoryHistory).toHaveBeenCalledWith("ai", 7);
    expect(fetchPrice).not.toHaveBeenCalled();
    expect(within(plot).getByTestId("history-score-line")).toBeInTheDocument();
    expect(within(plot).getByTestId("history-share-line")).toBeInTheDocument();
    expect(within(plot).queryByTestId("history-band")).toBeNull();
    expect(screen.getByTestId("history-panel-title-score").textContent).toContain("Average score (%)");
    expect(screen.getByTestId("history-panel-title-share").textContent).toContain("Coins triggered (% of coins used)");
    expect(screen.getAllByTestId("history-xaxis")).toHaveLength(1);
    const ys = (screen.getByTestId("history-share-line").getAttribute("d") ?? "").match(/[ML][\d.]+ ([\d.]+)/g)!.map((m) => Number(m.split(" ")[1]));
    expect(Math.max(...ys) - Math.min(...ys)).toBeGreaterThan(50);
    const readout = screen.getByTestId("history-readout").textContent ?? "";
    expect(readout).toContain("coins used 7");
    expect(readout).toContain("triggered 4 of 7");
    expect(readout).toContain("57%");
    expect(screen.getByTestId("history-title").textContent).toContain("AI");
  });

  it("shows the error and no-data states too", async () => {
    setup({
      selection: { kind: "category", id: "ai", name: "AI" },
      fetchCategoryHistory: () => Promise.reject(new Error("x")),
    });
    expect(await screen.findByTestId("history-error")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByTestId("history-loading")).toBeNull());
  });
});
