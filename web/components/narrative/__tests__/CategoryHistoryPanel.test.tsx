import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("lightweight-charts", () => import("@/test/mocks/lightweight-charts"));

import { mockCharts, resetMockCharts } from "@/test/mocks/lightweight-charts";
import { CategoryHistoryPanel } from "@/components/narrative/CategoryHistoryPanel";
import { HIDDEN_SEGMENT_COLOR } from "@/lib/regime-line-segments";
import { category, series } from "./fixtures";

beforeEach(() => resetMockCharts());

describe("CategoryHistoryPanel", () => {
  it("labels the legacy CoinGecko count as legacy-map and excluded from the composite", () => {
    const c = category("ai", 0.5, {
      series: [series({ source: "coingecko", label: "CoinGecko (legacy map)", in_composite: false, reason: "legacy-map-count: counts BTC/ETH/HYPE only; excluded from composite" })],
    });
    render(<CategoryHistoryPanel category={c} />);
    const el = screen.getByTestId("narrative-legacy-count-ai");
    expect(el).toHaveTextContent("legacy-map count: 20 (as of 2026-09-22)");
    expect(el).toHaveTextContent(/excluded from the composite/);
    // not plotted: only composite line series, no legacy legend entry
    expect(screen.queryByTestId("narrative-legend-ai-coingecko")).toBeNull();
  });

  it("labels narrative-only coins", () => {
    const c = category("ai", 0.5, { coins: [{ symbol: "FET", narrative_only: true }, { symbol: "TAO", narrative_only: false }] });
    render(<CategoryHistoryPanel category={c} />);
    expect(screen.getByTestId("narrative-coin-ai-FET")).toHaveTextContent("(narrative-only)");
    expect(screen.getByTestId("narrative-coin-ai-FET")).toHaveAttribute("data-narrative-only", "true");
    expect(screen.getByTestId("narrative-coin-ai-TAO")).not.toHaveTextContent("narrative-only");
  });

  it("marks mixed-scale composite points visibly and draws them as a marker series", () => {
    const c = category("ai", 0.5);
    c.composite.points[1].mixed_scale = true;
    render(<CategoryHistoryPanel category={c} />);
    expect(screen.getByTestId("narrative-mixed-scale-ai")).toHaveAttribute("data-count", "1");
    const markers = mockCharts[0].series.find((s) => s.options.lineVisible === false && s.options.pointMarkersRadius === 3);
    expect(markers).toBeDefined();
    expect((markers!.data as { value?: number }[]).filter((p) => p.value !== undefined)).toHaveLength(1);
  });

  it("keeps pytrends nightly-7d and backfill-269d as separate lines", () => {
    const c = category("ai", 0.5, {
      series: [
        series({ source: "pytrends", variant: "nightly-7d", label: "Google Trends" }),
        series({ source: "pytrends", variant: "backfill-269d", label: "Google Trends" }),
      ],
    });
    render(<CategoryHistoryPanel category={c} />);
    expect(screen.getByTestId("narrative-legend-ai-pytrends-nightly-7d")).toBeInTheDocument();
    expect(screen.getByTestId("narrative-legend-ai-pytrends-backfill-269d")).toBeInTheDocument();
    // two source lines + composite
    expect(mockCharts[0].series.filter((s) => s.options.lineVisible !== false)).toHaveLength(3);
  });

  it("renders unavailable / stale / presumed-dead series explicitly with their reasons", () => {
    const c = category("ai", 0.5, {
      series: [
        series({ source: "reddit", label: "Reddit", status: "unavailable", reason: "no-archived-data", points: [] }),
        series({ source: "coingecko-narrative", label: "CoinGecko", status: "stale", reason: "last-point-9-days-old" }),
        series({ source: "pytrends", variant: "nightly-7d", label: "Google Trends", status: "presumed-dead", reason: null }),
      ],
    });
    render(<CategoryHistoryPanel category={c} />);
    expect(screen.getByTestId("narrative-notice-ai-reddit")).toHaveTextContent("Reddit [unavailable]: Unavailable — no archived data for this source yet");
    expect(screen.getByTestId("narrative-notice-ai-coingecko-narrative")).toHaveTextContent("9 days old");
    expect(screen.getByTestId("narrative-notice-ai-pytrends-nightly-7d")).toHaveTextContent(/Presumed dead/);
  });

  it("renders an unavailable composite with its reason, never as 0", () => {
    render(<CategoryHistoryPanel category={category("ai", null)} />);
    expect(screen.getByTestId("narrative-composite-notice-ai")).toHaveTextContent("Composite unavailable — Unranked — no composite data");
  });

  it("shows no-baseline-yet new listings with its own copy, not 0", () => {
    const c = category("ai", 0.5, {
      series: [
        series({
          source: "exchange_new_listings",
          in_composite: false,
          status: "unavailable",
          reason: "no-baseline-yet",
          points: [{ date: "2026-09-22", raw_value: null, normalized_value: null, point_status: "unavailable", reason: "no-baseline-yet", gap_before: false }],
        }),
      ],
    });
    render(<CategoryHistoryPanel category={c} />);
    const el = screen.getByTestId("narrative-new-listings-ai");
    expect(el).toHaveTextContent("Not enough history yet to detect new listings");
    expect(el.textContent).not.toMatch(/\b0\b/);
  });

  it("passes gap_before through so the line is not bridged", () => {
    const c = category("ai", 0.5);
    c.composite.points[1].gap_before = true;
    render(<CategoryHistoryPanel category={c} />);
    const composite = mockCharts[0].series.find((s) => s.options.lineWidth === 3)!;
    expect((composite.data[0] as { color?: string }).color).toBe(HIDDEN_SEGMENT_COLOR);
  });

  it("shows a personal-use badge when any series is not redistributable", () => {
    render(<CategoryHistoryPanel category={category("ai", 0.5)} />);
    expect(screen.getByTestId("narrative-redistribution-ai")).toBeInTheDocument();
  });
});
