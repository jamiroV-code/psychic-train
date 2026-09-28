import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";

vi.mock("lightweight-charts", () => import("@/test/mocks/onchain-lightweight-charts"));

import { markerCalls, mockCharts, resetMarkerCalls, resetMockCharts } from "@/test/mocks/onchain-lightweight-charts";
import { OnchainDashboard } from "@/components/onchain/OnchainDashboard";
import { isoDateToUtcSeconds } from "@/lib/regime-chart-sync";
import type { OnchainGrowthResponse, OnchainMetric } from "@/lib/types/onchain";
import { ATTRIBUTION, GRID, allUnavailableResponse, makeResponse } from "./fixtures";

const LIVE = ["ethereum", "base", "arbitrum", "optimism", "polygon", "robinhood"];

function fetcher(make: (m: OnchainMetric, s?: string) => OnchainGrowthResponse = (m, s) => makeResponse(m, s)) {
  return vi.fn((m: OnchainMetric, s?: string) => Promise.resolve(make(m, s)));
}

async function renderLoaded(fetchData = fetcher()) {
  render(<OnchainDashboard fetchData={fetchData} />);
  await screen.findByTestId("onchain-dashboard");
  return fetchData;
}

beforeEach(() => {
  resetMockCharts();
  resetMarkerCalls();
});

describe("OnchainDashboard", () => {
  it("shows loading, then 6 live panels and 3 unavailable cards with no zero", async () => {
    render(<OnchainDashboard fetchData={fetcher()} />);
    expect(screen.getByTestId("onchain-loading")).toBeInTheDocument();
    await screen.findByTestId("onchain-dashboard");
    for (const id of LIVE) expect(screen.getByTestId(`onchain-panel-${id}`)).toBeInTheDocument();
    for (const id of ["solana", "bnb", "tron"]) {
      const card = screen.getByTestId(`onchain-unavailable-${id}`);
      expect(card).toHaveTextContent("Source unavailable");
      expect(card.textContent).not.toMatch(/\b0\b/);
      expect(screen.queryByTestId(`onchain-panel-${id}`)).toBeNull();
    }
  });

  it("first load uses the API default range; metric and range changes re-fetch with ?start=", async () => {
    const f = await renderLoaded();
    expect(f).toHaveBeenLastCalledWith("active_addresses", undefined);

    await act(async () => fireEvent.click(screen.getByTestId("onchain-metric-transactions")));
    await waitFor(() => expect(screen.getByTestId("onchain-dashboard")).toHaveAttribute("data-metric", "transactions"));
    expect(f).toHaveBeenLastCalledWith("transactions", "2025-09-20"); // last grid date - 365 days

    await act(async () => fireEvent.click(screen.getByTestId("onchain-range-2y")));
    expect(f).toHaveBeenLastCalledWith("transactions", "2024-09-20");
    await act(async () => fireEvent.click(screen.getByTestId("onchain-range-all")));
    expect(f).toHaveBeenLastCalledWith("transactions", GRID[0]);
    expect(screen.getByTestId("onchain-range-all")).toHaveAttribute("aria-checked", "true");
  });

  it("keeps the previous render dimmed while re-fetching", async () => {
    let resolve: (r: OnchainGrowthResponse) => void = () => {};
    const f = vi.fn((m: OnchainMetric, s?: string) =>
      f.mock.calls.length === 1 ? Promise.resolve(makeResponse(m, s)) : new Promise<OnchainGrowthResponse>((r) => (resolve = r))
    );
    await renderLoaded(f);
    await act(async () => fireEvent.click(screen.getByTestId("onchain-range-5y")));
    expect(screen.getByTestId("onchain-refetching")).toBeInTheDocument();
    expect(screen.getByTestId("onchain-panel-ethereum")).toBeInTheDocument();
    await act(async () => resolve(makeResponse("active_addresses", "2021-09-21")));
    expect(screen.queryByTestId("onchain-refetching")).toBeNull();
  });

  it("shows source and method as visible text on every live panel (AC-2)", async () => {
    await renderLoaded();
    for (const id of LIVE) {
      const badge = screen.getByTestId(`onchain-panel-${id}-source`);
      expect(badge).toBeVisible();
      expect(badge).toHaveTextContent("Source: growthepie");
      expect(badge).toHaveTextContent("unique addresses active per UTC day");
    }
    expect(screen.getByTestId("onchain-method-note")).toHaveTextContent("180-day low");
  });

  it("renders the growthepie attribution once, verbatim, with a link (E6)", async () => {
    await renderLoaded();
    const footers = screen.getAllByTestId("onchain-attribution");
    expect(footers).toHaveLength(1);
    expect(screen.getByTestId("onchain-attribution-text").textContent).toBe(ATTRIBUTION);
    expect(within(footers[0]).getByRole("link")).toHaveAttribute("href", "https://www.growthepie.com");
  });

  it("omits the attribution footer and shows the empty state when no chain is live", async () => {
    render(<OnchainDashboard fetchData={fetcher(() => allUnavailableResponse())} />);
    await screen.findByTestId("onchain-empty");
    expect(screen.queryByTestId("onchain-attribution")).toBeNull();
    expect(screen.queryByTestId("onchain-comparison")).toBeNull();
    expect(screen.getByTestId("onchain-unavailable-solana")).toBeInTheDocument();
  });

  it("shows Robinhood's limited-history copy with the API gate date", async () => {
    await renderLoaded();
    expect(screen.getByTestId("onchain-panel-robinhood-limited-history")).toHaveTextContent(
      "Limited history — floor/ramp markers from 2027-01-10"
    );
    expect(screen.queryByTestId("onchain-panel-ethereum-limited-history")).toBeNull();
  });

  it("maps every floor/ramp state; 'Near floor' only for state=floor", async () => {
    await renderLoaded();
    const expected: Record<string, string> = {
      ethereum: "Neutral",
      base: "Ramping",
      arbitrum: "Declining",
      optimism: "Neutral",
      polygon: "Near floor",
      robinhood: "Not enough history",
    };
    for (const [id, text] of Object.entries(expected)) {
      expect(screen.getByTestId(`onchain-panel-${id}-state`)).toHaveTextContent(text);
    }
    expect(screen.getAllByText("Near floor")).toHaveLength(1);
    expect(screen.getByTestId("onchain-panel-polygon-state")).toHaveAttribute("data-state", "floor");
  });

  it("shows stale badges and banner, and the redistribution badge only when not redistributable", async () => {
    await renderLoaded(fetcher((m, s) => makeResponse("transactions", s)));
    expect(screen.getByTestId("onchain-panel-base-stale")).toHaveTextContent("5 days ago");
    expect(screen.getByTestId("onchain-stale-banner")).toHaveTextContent("Base last updated 5 days ago");
    expect(screen.queryByTestId("onchain-panel-ethereum-stale")).toBeNull();
    expect(screen.queryByTestId("onchain-panel-ethereum-redistribution")).toBeNull();
    expect(screen.getByTestId("onchain-panel-base-crosscheck-redistribution")).toHaveAttribute("data-redistributable", "false");
  });

  it("renders the L2BEAT cross-check as display-only text, only when present", async () => {
    await renderLoaded(fetcher((m, s) => makeResponse("transactions", s)));
    const note = screen.getByTestId("onchain-panel-base-crosscheck");
    expect(note).toHaveTextContent("display only");
    expect(note).toHaveTextContent("-0.05%");
    expect(screen.queryByTestId("onchain-panel-ethereum-crosscheck")).toBeNull();
  });

  it("shades pre-launch points, draws markers from the API, and breaks lines at gap_before", async () => {
    await renderLoaded();
    expect(screen.getByTestId("onchain-panel-polygon-prelaunch")).toHaveTextContent("before launch (2025-09-22)");
    expect(screen.queryByTestId("onchain-panel-ethereum-prelaunch")).toBeNull();
    const ethMarkers = markerCalls.find((c) => (c.markers as { text: string }[]).length === 2);
    expect(ethMarkers?.markers).toEqual([
      expect.objectContaining({ time: isoDateToUtcSeconds(GRID[1]), text: "floor" }),
      expect.objectContaining({ time: isoDateToUtcSeconds(GRID[4]), text: "ramp" }),
    ]);
    expect(screen.getByTestId("onchain-chart-ethereum")).toHaveAttribute("data-gap-dates", "2025-09-25");
  });

  it("syncs crosshair across panels and updates every readout", async () => {
    await renderLoaded();
    const panelCharts = mockCharts.filter((c) => (c.container as HTMLElement).dataset.testid?.startsWith("onchain-chart-"));
    expect(panelCharts).toHaveLength(6);
    act(() => panelCharts[0].fireCrosshair(isoDateToUtcSeconds(GRID[4])));
    expect(screen.getByTestId("onchain-panel-arbitrum-readout")).toHaveTextContent("1,400 on 2026-09-19");
    expect(panelCharts[2].setCrosshairPosition).toHaveBeenCalled();
    // the comparison chart is not in the sync group
    const overlay = mockCharts.find((c) => (c.container as HTMLElement).dataset.testid === "onchain-comparison-chart");
    expect(overlay?.setCrosshairPosition).not.toHaveBeenCalled();
  });

  it("shows an error with retry when the first load fails", async () => {
    const f = vi
      .fn<(m: OnchainMetric, s?: string) => Promise<OnchainGrowthResponse>>()
      .mockRejectedValueOnce(new Error("boom"))
      .mockImplementation((m, s) => Promise.resolve(makeResponse(m, s)));
    render(<OnchainDashboard fetchData={f} />);
    expect(await screen.findByTestId("onchain-error")).toHaveTextContent("boom");
    await act(async () => fireEvent.click(screen.getByTestId("onchain-retry")));
    await screen.findByTestId("onchain-dashboard");
  });
});
