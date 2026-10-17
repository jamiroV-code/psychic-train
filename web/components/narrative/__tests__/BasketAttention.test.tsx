import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { BasketAttentionChart } from "@/components/narrative/BasketAttentionChart";
import { BasketTable } from "@/components/narrative/BasketTable";
import type { AttentionResponse, BasketAttention } from "@/lib/types/attention";

vi.mock("@/lib/use-simple-lines", () => ({ useSimpleLines: () => undefined }));

const mk = (id: string, over: Partial<BasketAttention> = {}): BasketAttention => ({
  id,
  name: `Basket ${id}`,
  score: 12.3,
  change: -1.2,
  breadth: 0.6,
  coverage: "covers 3 of 4",
  series: [
    { date: "2026-10-01", value: 1 },
    { date: "2026-10-02", value: null },
    { date: "2026-10-03", value: 3 },
  ],
  coins: [
    {
      symbol: "ETH",
      score: 5,
      sources_used: 2,
      sources_total: 3,
      sources: [{ source: "wiki", raw: 120, ratio: 1.1, rank: null, state: "ok" }],
    },
  ],
  status: "ok",
  reason: "",
  universe_size: 4,
  ...over,
});

const data = (baskets: BasketAttention[]): AttentionResponse => ({
  window: 30,
  as_of: "2026-10-16",
  membership_as_of: "2026-10-10",
  baskets,
});

const chart = (props: Partial<React.ComponentProps<typeof BasketAttentionChart>> = {}) =>
  render(<BasketAttentionChart data={data([mk("a"), mk("b")])} window={30} onWindowChange={() => {}} {...props} />);

describe("BasketAttentionChart", () => {
  it("has exactly one legend and the membership line", () => {
    chart();
    expect(screen.getAllByRole("group", { name: /baskets shown/i })).toHaveLength(1);
    expect(screen.getByTestId("attention-membership").textContent).toBe("membership as of 2026-10-10");
  });
  it("uses no badge class", () => {
    const { container } = chart();
    expect(container.innerHTML).not.toMatch(/badge/i);
  });
  it("selects the window", () => {
    const fn = vi.fn();
    chart({ onWindowChange: fn });
    fireEvent.click(screen.getByRole("button", { name: "90d" }));
    expect(fn).toHaveBeenCalledWith(90);
  });
  it("renders loading", () => {
    chart({ data: null });
    expect(screen.getByTestId("attention-loading")).toBeTruthy();
  });
  it("renders error", () => {
    chart({ data: null, error: "API request failed: /api/x -> 500", onRetry: () => {} });
    const text = screen.getByTestId("attention-error").textContent ?? "";
    expect(text).toContain("could not be loaded");
    expect(text).not.toMatch(/\/api|500/);
  });
  it("retries from the error line", () => {
    const retry = vi.fn();
    chart({ data: null, error: "x", onRetry: retry });
    fireEvent.click(screen.getByTestId("attention-retry"));
    expect(retry).toHaveBeenCalledTimes(1);
  });
  it("shows one calm line and no legend when no basket has a series", () => {
    const none = (id: string) => mk(id, { status: "no-data", reason: "reference-missing", score: null, series: [{ date: "2026-10-01", value: null }] });
    chart({ data: data([none("a"), none("b")]) });
    expect(screen.getByTestId("attention-nodata").textContent).toMatch(/Ranking is off/);
    expect(screen.queryByRole("group", { name: "Baskets shown" })).toBeNull();
    expect(screen.queryByTestId("attention-chart-container")).toBeNull();
  });
  it("labels the y axis and keeps one legend when there is a series", () => {
    chart({ data: data([mk("a")]) });
    expect(screen.getByText("Attention score, start = 100")).toBeTruthy();
    expect(screen.getAllByRole("group", { name: "Baskets shown" })).toHaveLength(1);
  });
  it("renders empty with a screener link", () => {
    chart({ data: data([]) });
    expect(screen.getByTestId("attention-empty")).toBeTruthy();
    expect(screen.getByRole("link").getAttribute("href")).toBe("/screener");
  });
  it("renders partial for a basket without data", () => {
    chart({ data: data([mk("a"), mk("b", { status: "no-data", score: null, series: [] })]) });
    expect(screen.getByTestId("attention-partial")).toBeTruthy();
  });
  it("says ranking is off for reference-missing, in one muted line", () => {
    chart({ data: data([mk("a", { status: "no-data", reason: "reference-missing", score: null })]) });
    expect(screen.getAllByTestId("attention-ranking-off")).toHaveLength(1);
  });
});

describe("BasketTable", () => {
  it("has five columns", () => {
    render(<BasketTable baskets={[mk("a")]} />);
    expect(screen.getAllByRole("columnheader")).toHaveLength(5);
  });
  it("shows no data, never 0, for null numbers", () => {
    render(<BasketTable baskets={[mk("a", { score: null, change: null, breadth: null })]} />);
    expect(screen.getAllByText("no data").length).toBe(3);
  });
  it("signs the change", () => {
    render(<BasketTable baskets={[mk("a", { change: 2 })]} />);
    expect(screen.getByText("+2.0")).toBeTruthy();
  });
  it("expands coins with n of N sources and raw values", () => {
    render(<BasketTable baskets={[mk("a")]} />);
    fireEvent.click(screen.getByRole("button", { name: /Basket a/ }));
    expect(screen.getByText("ETH")).toBeTruthy();
    expect(screen.getByText("2 of 3 sources")).toBeTruthy();
    expect(screen.getByText("Wikipedia")).toBeTruthy();
    expect(screen.getByText("120")).toBeTruthy();
  });
  it("marks the name button expandable", () => {
    const { container } = render(<BasketTable baskets={[mk("a")]} />);
    expect(container.querySelector(".basket-table__chev")).toBeTruthy();
    expect(screen.getByRole("button", { name: /Basket a/ }).getAttribute("aria-expanded")).toBe("false");
  });
  it("uses no badge class", () => {
    const { container } = render(<BasketTable baskets={[mk("a")]} />);
    expect(container.innerHTML).not.toMatch(/badge/i);
  });
  it("renders empty", () => {
    render(<BasketTable baskets={[]} />);
    expect(screen.getByTestId("attention-table-empty")).toBeTruthy();
  });
});
