import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { BasketCoins } from "@/components/narrative/BasketCoins";
import { formatCompact, sourceLabel } from "@/lib/attention-lines";
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
    expect(screen.getByTestId("coin-source-ETH-wikipedia").textContent).toContain("1.2K");
    expect(screen.getByTestId("coin-source-ETH-trends").textContent).toMatch(/no data/);
    expect(screen.getByTestId("coin-source-ETH-trends").textContent).toContain("unavailable");
    expect(screen.getByTestId("coin-source-ETH-reddit").textContent).toContain("not probed");
  });

  it("prints human source labels, never raw ids, and compact numbers", () => {
    render(<BasketCoins coins={[coin]} />);
    expect(screen.getByTestId("coin-source-ETH-wikipedia").textContent).toContain("Wikipedia");
    expect(screen.getByTestId("coin-source-ETH-wikipedia").textContent).not.toContain("wikipedia");
    expect(formatCompact(1234567890.123456)).toBe("1.23B");
    expect(sourceLabel("exchange_volume")).toBe("Exchange volume");
    expect(sourceLabel("xsearch")).toBe("X");
    expect(sourceLabel("some_new_one")).toBe("Some new one");
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
