import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DiscoveryExclusions } from "@/components/narrative/DiscoveryExclusions";
import type { DiscoveryExcludedCoin } from "@/lib/types/discovery";

const coins: DiscoveryExcludedCoin[] = [
  { symbol: "USDT", reason: "stablecoin", detail: "stablecoin" },
  { symbol: "USDC", reason: "stablecoin", detail: "" },
  { symbol: "BUIDL", reason: "no-market", detail: "tokenized fund" },
  { symbol: "STETH", reason: "wrapped-staked", detail: "wrapped or staked" },
  { symbol: "MMM", reason: "unassigned", detail: "" },
];
const counts = { stablecoin: 2, "no-market": 1, "wrapped-staked": 1, unassigned: 1 };

describe("DiscoveryExclusions", () => {
  it("lists_excluded_coin_with_reason_on_expand", () => {
    render(<DiscoveryExclusions coins={coins} counts={counts} minCategoryCoins={3} />);
    const toggle = screen.getByTestId("discovery-exclusions-toggle");
    expect(toggle.tagName).toBe("BUTTON");
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByTestId("discovery-exclusions-list")).toBeNull();

    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    const list = screen.getByTestId("discovery-exclusions-list");
    expect(toggle).toHaveAttribute("aria-controls", list.id);
    const stable = within(list).getByTestId("discovery-excluded-stablecoin");
    expect(stable).toHaveTextContent(/Stablecoins/);
    expect(stable).toHaveTextContent("USDT, USDC");
    expect(within(list).getByTestId("discovery-excluded-no-market")).toHaveTextContent("BUIDL (tokenized fund)");
    expect(within(list).getByTestId("discovery-excluded-unassigned")).toHaveTextContent(/attention_narratives\.json/);
    // Groups follow the count, biggest first.
    const order = within(list).getAllByTestId(/^discovery-excluded-/).map((g) => g.getAttribute("data-testid"));
    expect(order[0]).toBe("discovery-excluded-stablecoin");

    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByTestId("discovery-exclusions-list")).toBeNull();
  });

  it("gives each reason one plain sentence and keeps unknown reasons readable", () => {
    const all = ["stablecoin", "wrapped-staked", "no-market", "not-tradeable-config", "unassigned", "hidden-narrative", "no-source-data", "brand-new"]
      .map((reason, i) => ({ symbol: `C${i}`, reason, detail: "" }));
    render(<DiscoveryExclusions coins={all} counts={{}} minCategoryCoins={3} />);
    fireEvent.click(screen.getByTestId("discovery-exclusions-toggle"));
    const groups = screen.getAllByTestId(/^discovery-excluded-/);
    expect(groups).toHaveLength(8);
    for (const g of groups) {
      const sentence = g.querySelector(".discovery-exclusions__why")?.textContent ?? "";
      expect(sentence).toMatch(/^[A-Z].*\.$/);
    }
    expect(screen.getByTestId("discovery-excluded-hidden-narrative")).toHaveTextContent(/fewer than 3 coins/);
    // The count is coins, not narratives.
    expect(screen.getByTestId("discovery-excluded-hidden-narrative").querySelector("h3")).toHaveTextContent(/^1 coins in hidden narratives$/);
    expect(screen.getByTestId("discovery-excluded-brand-new")).toHaveTextContent(/brand-new/);
  });

  it("says once in the footer how tradeability is checked, only when a coin is unverified", () => {
    const { rerender } = render(<DiscoveryExclusions coins={coins} counts={counts} minCategoryCoins={3} tradeabilityUnverified />);
    fireEvent.click(screen.getByTestId("discovery-exclusions-toggle"));
    const notes = screen.getAllByText(/tradeability is checked against exchange lists once they are built; until then no coin is excluded for it/i);
    expect(notes).toHaveLength(1);
    rerender(<DiscoveryExclusions coins={coins} counts={counts} minCategoryCoins={3} tradeabilityUnverified={false} />);
    expect(screen.queryByText(/tradeability is checked/i)).toBeNull();
  });

  it("renders nothing when no coin is excluded", () => {
    const { container } = render(<DiscoveryExclusions coins={[]} counts={{}} minCategoryCoins={3} />);
    expect(container).toBeEmptyDOMElement();
  });
});
