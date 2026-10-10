import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ChartFreshness } from "@/components/chart/ChartFreshness";

const BASE = { last_bar_ts: "2026-10-03T14:15:00Z", is_partial: true, server_time: "2026-10-03T14:22:00Z", stale: false };

describe("ChartFreshness", () => {
  it("renders the caption and no stale marker for fresh data", () => {
    render(<ChartFreshness chart={BASE} />);
    expect(screen.getByTestId("chart-freshness-caption").textContent).toBe(
      "Last bar 2026-10-03 16:15 CEST, opened 7 min ago (forming)",
    );
    expect(screen.queryByTestId("stale-marker")).toBeNull();
  });

  it("renders a plain 'stale' marker when stale", () => {
    render(<ChartFreshness chart={{ ...BASE, is_partial: false, server_time: "2026-10-05T14:15:00Z", stale: true }} />);
    expect(screen.getByTestId("chart-freshness-caption").textContent).toBe("Last bar 2026-10-03 16:15 CEST, 2 d ago");
    expect(screen.getByTestId("stale-marker").textContent).toBe("stale");
  });

  it("renders nothing without a last bar and without staleness", () => {
    const { container } = render(<ChartFreshness chart={{ last_bar_ts: null, is_partial: null, server_time: null, stale: false }} />);
    expect(container.innerHTML).toBe("");
  });
});
