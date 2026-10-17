import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { BasketCoins } from "@/components/narrative/BasketCoins";
import type { CoinAttention } from "@/lib/types/attention";

const coin: CoinAttention = {
  symbol: "ETH",
  score: 55.4,
  sources_used: 2,
  sources_total: 3,
  sources: [
    { source: "wikipedia", raw: 1200, ratio: 1.2, rank: null, state: "ok" },
    { source: "trends", raw: null, ratio: null, rank: null, state: "unavailable" },
    { source: "reddit", raw: null, ratio: null, rank: null, state: "not-probed" },
  ],
};

describe("BasketCoins", () => {
  it("shows score, n of N sources, raw per source and state marks", () => {
    render(<BasketCoins coins={[coin]} />);
    expect(screen.getByText("ETH")).toBeTruthy();
    expect(screen.getByText("2 of 3 sources")).toBeTruthy();
    expect(screen.getByTestId("coin-source-ETH-wikipedia").textContent).toContain("1200");
    expect(screen.getByTestId("coin-source-ETH-trends").textContent).toMatch(/no data/);
    expect(screen.getByTestId("coin-source-ETH-trends").textContent).toContain("unavailable");
    expect(screen.getByTestId("coin-source-ETH-reddit").textContent).toContain("not-probed");
  });

  it("never prints 0 for a missing raw value", () => {
    render(<BasketCoins coins={[coin]} />);
    expect(screen.getByTestId("coin-source-ETH-trends").textContent).not.toMatch(/\b0\b/);
  });

  it("shows one muted no-data line when there are no coins", () => {
    render(<BasketCoins coins={[]} />);
    expect(screen.getByTestId("basket-coins-empty").textContent).toMatch(/no data/);
  });
});
