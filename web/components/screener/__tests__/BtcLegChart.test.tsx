import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { BtcLegChart } from "@/components/screener/BtcLegChart";
import type { BtcLegChartResponse } from "@/lib/types/btc-legs";

function response(overrides: Partial<BtcLegChartResponse> = {}): BtcLegChartResponse {
  return {
    available: true,
    reason: null,
    server_time: "2026-10-09T12:00:00Z",
    composite_variant: "reduced",
    first_bar_ts: "2026-01-01T00:00:00Z",
    last_bar_ts: "2026-10-08T00:00:00Z",
    bar_count: 3,
    btc: [
      { timestamp: "2026-01-01T00:00:00Z", close: 90000 },
      { timestamp: "2026-06-01T00:00:00Z", close: 95000 },
      { timestamp: "2026-10-08T00:00:00Z", close: 120000 },
    ],
    boundaries: [{ date: "2026-06-01", z_score: 2.0, confirmed_date: "2026-06-02" }],
    legs: [{ start: "2026-06-01", end: null, days: 129, is_current: true }],
    current_leg: {
      start_date: "2026-06-01",
      days_in_leg: 129,
      composite_value: 0.21,
      composite_as_of: "2026-10-07",
      change_14d: -0.034,
      last_boundary_z: 2.0,
      latest_candidate: { date: "2026-09-01", z_score: 1.7, confirmed: false },
      composite_variant: "reduced",
    },
    estimate: {
      heading: "Estimate (rule over the numbers shown)",
      age: {
        label: null,
        age_days: 129,
        median_days: null,
        ratio: null,
        earlier_legs: 0,
        earlier_lengths_days: [],
        rule: "early when 3 x age_days < median_days; ...",
        reason: "N/A: 0 earlier completed confirmed legs, at least 3 needed",
      },
      composite: {
        label: "falling",
        change_14d: -0.034,
        threshold: 0.02,
        history_std: 0.04,
        n_changes: 300,
        composite_as_of: "2026-10-07",
        rule: "rising when change_14d >= +T; ...",
        reason: null,
      },
    },
    ...overrides,
  };
}

async function mount(data: BtcLegChartResponse) {
  const fetchData = vi.fn(async () => data);
  render(<BtcLegChart fetchData={fetchData} />);
  await waitFor(() => expect(fetchData).toHaveBeenCalled());
}

describe("BtcLegChart", () => {
  it("heading text exact", async () => {
    await mount(response());
    await waitFor(() =>
      expect(screen.getByTestId("leg-estimate-heading")).toHaveTextContent(/^Estimate \(rule over the numbers shown\)$/),
    );
    expect(screen.getByTestId("btc-leg-span")).toHaveTextContent("Daily BTC, 2026-01-01 to 2026-10-08 UTC, 3 bars");
  });

  it("inputs visible beside each label", async () => {
    await mount(response());
    await waitFor(() => expect(screen.getByTestId("leg-estimate-composite-label")).toHaveTextContent("falling"));
    expect(screen.getByTestId("leg-estimate-composite-change-14d")).toHaveTextContent("change_14d-0.034");
    expect(screen.getByTestId("leg-estimate-composite-threshold")).toHaveTextContent("T0.02");
    expect(screen.getByTestId("leg-estimate-composite-std")).toHaveTextContent("0.04");
    expect(screen.getByTestId("leg-estimate-composite-n")).toHaveTextContent("n300");
    expect(screen.getByTestId("leg-estimate-composite-as-of")).toHaveTextContent("2026-10-07");
    expect(screen.getByTestId("leg-estimate-age-age-days")).toHaveTextContent("129");
  });

  it("N/A states carry their reason", async () => {
    await mount(response());
    await waitFor(() =>
      expect(screen.getByTestId("leg-estimate-age-na")).toHaveTextContent(
        "N/A: N/A: 0 earlier completed confirmed legs, at least 3 needed",
      ),
    );
    expect(screen.queryByTestId("leg-estimate-age-label")).toBeNull();
  });

  it("unavailable state with reason, and no zero legs", async () => {
    await mount(
      response({ available: false, reason: "no BTC 1d bars in the cache", bar_count: 0, btc: [], legs: [], boundaries: [], current_leg: null, estimate: null, first_bar_ts: null, last_bar_ts: null }),
    );
    await waitFor(() =>
      expect(screen.getByTestId("btc-leg-unavailable")).toHaveTextContent("no BTC 1d bars in the cache"),
    );
    expect(screen.queryByTestId("btc-leg-count")).toBeNull();
    expect(screen.queryByTestId("leg-estimate")).toBeNull();
  });

  it("current-leg readouts", async () => {
    await mount(response());
    await waitFor(() => expect(screen.getByTestId("btc-current-leg-start")).toHaveTextContent("2026-06-01"));
    expect(screen.getByTestId("btc-current-leg-days")).toHaveTextContent("129");
    expect(screen.getByTestId("btc-current-leg-boundary-z")).toHaveTextContent("+2");
    expect(screen.getByTestId("btc-current-leg-composite")).toHaveTextContent("0.21 as of 2026-10-07");
    expect(screen.getByTestId("btc-current-leg-change-14d")).toHaveTextContent("-0.034");
    expect(screen.getByTestId("btc-current-leg-latest-candidate")).toHaveTextContent("2026-09-01, z +1.7, unconfirmed");
  });

  it("fetch error surfaces, not a blank chart", async () => {
    const fetchData = vi.fn(async () => {
      throw new Error("API request failed: /api/regime/btc-legs -> 500");
    });
    render(<BtcLegChart fetchData={fetchData} />);
    await waitFor(() => expect(screen.getByTestId("btc-leg-error")).toHaveTextContent("500"));
  });
});
