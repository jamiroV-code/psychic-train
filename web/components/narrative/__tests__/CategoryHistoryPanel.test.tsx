import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { CategoryHistoryPanel } from "@/components/narrative/CategoryHistoryPanel";
import { buildPanelAxis, seriesKey } from "@/lib/narrative-view-model";
import { buildNarrativeLines } from "@/lib/narrative-panel-lines";
import { toLineSegments } from "@/lib/chart-segments";
import { category, series } from "./fixtures";

/**
 * The plot is a Svelte/LayerChart island (ADR-1) and jsdom does not mount it,
 * so what used to be asserted against a mocked lightweight-charts instance is
 * asserted here against the real mapping that feeds the island. That is a
 * stronger check, not a weaker one: a mock-shaped assertion only ever proved
 * the mock. That the island then draws is covered by e2e/narrative.spec.ts.
 */

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
    // Exactly one composite point is on the backfill scale, so exactly one
    // marker is handed to the plot.
    const axis = buildPanelAxis(c);
    expect(axis.mixedScaleCount).toBe(1);
    expect(axis.mixedScale.filter((v) => v !== null)).toHaveLength(1);
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
    // Both windows are drawn as their own line, separated by the dash rather
    // than by a near-identical hue (see lib/chart-palette.ts).
    const lines = buildNarrativeLines(buildPanelAxis(c).series, new Set());
    expect(lines.map((l) => l.key)).toEqual(["pytrends-nightly-7d", "pytrends-backfill-269d"]);
    expect(lines.map((l) => l.dashed)).toEqual([false, true]);
    expect(new Set(lines.map((l) => l.color)).size).toBe(1);
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
          points: [{ date: "2026-09-22", raw_value: null, normalized_value: null, point_status: "unavailable", reason: "no-baseline-yet", gap_before: false, sufficiency: "provisional" }],
        }),
      ],
    });
    render(<CategoryHistoryPanel category={c} />);
    const el = screen.getByTestId("narrative-new-listings-ai");
    expect(el).toHaveTextContent("Not enough history yet to detect new listings");
    expect(el.textContent).not.toMatch(/\b0\b/);
  });

  it("renders provisional marker below mature threshold", () => {
    const c = category("ai", 0.5, { series: [series({ source: "reddit", label: "Reddit" })] });
    render(<CategoryHistoryPanel category={c} />);
    const el = screen.getByTestId("narrative-provisional-ai-reddit");
    expect(el).toHaveAttribute("data-sufficiency", "provisional");
    expect(el).toHaveTextContent("provisional — thin history (2 points)");
    expect(screen.getByTestId("narrative-legend-ai-reddit")).toHaveTextContent("(provisional)");
  });

  it("renders no provisional marker for a mature series", () => {
    const pts = ["2026-09-18", "2026-09-19", "2026-09-20", "2026-09-21", "2026-09-22"].map((date, i) => ({
      date, raw_value: i, normalized_value: i / 4, point_status: "ok", reason: null, gap_before: false, sufficiency: "mature" as const,
    }));
    const c = category("ai", 0.5, { series: [series({ source: "reddit", label: "Reddit", points: pts })] });
    render(<CategoryHistoryPanel category={c} />);
    expect(screen.queryByTestId("narrative-provisional-ai-reddit")).toBeNull();
    expect(screen.getByTestId("narrative-legend-ai-reddit")).not.toHaveTextContent("provisional");
  });

  it("renders insufficient-history marker not a line", () => {
    const c = category("ai", 0.5, {
      series: [
        series({ source: "pytrends", variant: "nightly-7d", label: "Google Trends" }),
        series({
          source: "reddit",
          label: "Reddit",
          points: [{ date: "2026-09-22", raw_value: 7, normalized_value: null, point_status: "ok", reason: null, gap_before: false, sufficiency: "insufficient" }],
        }),
      ],
    });
    render(<CategoryHistoryPanel category={c} />);
    const el = screen.getByTestId("narrative-insufficient-ai-reddit");
    expect(el).toHaveAttribute("data-sufficiency", "insufficient");
    expect(el).toHaveTextContent("not enough history yet (1 point)");
    expect(screen.queryByTestId("narrative-legend-ai-reddit")).toBeNull();
    // The insufficient series is reported as a marker and never reaches the
    // plot: hiding it leaves only the sufficient pytrends line.
    const reddit = c.series.find((x) => x.source === "reddit")!;
    const lines = buildNarrativeLines(buildPanelAxis(c).series, new Set([seriesKey(reddit)]));
    expect(lines.map((l) => l.key)).toEqual(["pytrends-nightly-7d"]);
  });

  it("passes gap_before through so the line is not bridged", () => {
    const c = category("ai", 0.5);
    c.composite.points[1].gap_before = true;
    render(<CategoryHistoryPanel category={c} />);
    const axis = buildPanelAxis(c);
    // The flagged point starts a new segment, so no line is drawn across it.
    const segments = toLineSegments(axis.dates, axis.composite.values, axis.composite.gapBefore);
    expect(segments.length).toBeGreaterThan(1);
    expect(segments[1][0].i).toBe(1);
  });

  it("shows a personal-use badge when any series is not redistributable", () => {
    render(<CategoryHistoryPanel category={category("ai", 0.5)} />);
    expect(screen.getByTestId("narrative-redistribution-ai")).toBeInTheDocument();
  });
});
