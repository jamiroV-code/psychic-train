import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { ComparisonView } from "@/components/narrative/ComparisonView";
import { ChangeInAttentionView } from "@/components/narrative/ChangeInAttentionView";

const labels = { a: "Alpha", b: "Beta", c: "Gamma" };

describe("ComparisonView", () => {
  it("orders by rank, puts unranked rows last with '—' and a reason, never 0", () => {
    render(
      <ComparisonView
        labels={labels}
        comparison={{
          as_of: "2026-09-22",
          entries: [
            { category_id: "c", rank: null, value: null, mixed_scale: false, status: "unavailable", reason: "no-composite-on-as-of" },
            { category_id: "b", rank: 2, value: 0.4, mixed_scale: true, status: "ok", reason: null },
            { category_id: "a", rank: 1, value: 0.9, mixed_scale: false, status: "ok", reason: null },
          ],
        }}
      />
    );
    const rows = screen.getAllByTestId(/^narrative-comparison-row-/);
    expect(rows.map((r) => r.getAttribute("data-testid"))).toEqual([
      "narrative-comparison-row-a",
      "narrative-comparison-row-b",
      "narrative-comparison-row-c",
    ]);
    const c = within(rows[2]);
    expect(rows[2]).toHaveTextContent("—");
    expect(c.getByText(/no composite value on the as-of date/)).toBeInTheDocument();
    expect(screen.getByTestId("narrative-comparison-mixed-b")).toBeInTheDocument();
    expect(screen.queryByTestId(/^narrative-caveat/)).toBeNull(); // caveat lives once on the page (ADR-6)
  });
});

describe("ChangeInAttentionView", () => {
  it("shows signed deltas with baseline dates and a reason for missing baselines", () => {
    render(
      <ChangeInAttentionView
        labels={labels}
        change={{
          window_days: 7,
          baseline_tolerance_days: 2,
          as_of: "2026-09-22",
          entries: [
            { category_id: "a", delta: 0.25, rank: 1, baseline_date: "2026-09-15", mixed_scale: false, status: "ok", reason: null },
            { category_id: "b", delta: -0.1, rank: 2, baseline_date: "2026-09-14", mixed_scale: false, status: "ok", reason: null },
            { category_id: "c", delta: null, rank: null, baseline_date: null, mixed_scale: false, status: "unavailable", reason: "no-baseline-in-window" },
          ],
        }}
      />
    );
    expect(screen.getByTestId("narrative-change-row-a")).toHaveTextContent("+0.25");
    expect(screen.getByTestId("narrative-change-row-a")).toHaveTextContent("2026-09-15");
    expect(screen.getByTestId("narrative-change-row-b")).toHaveTextContent("-0.10");
    const c = screen.getByTestId("narrative-change-row-c");
    expect(c).toHaveTextContent(/7–9 days earlier/);
    expect(c).toHaveAttribute("data-rank", "");
    expect(screen.getByText(/baseline 7–9 days earlier/)).toBeInTheDocument();
    expect(screen.queryByTestId(/^narrative-caveat/)).toBeNull(); // caveat lives once on the page (ADR-6)
  });

  it("renders a null delta as '—' with its reason, never 0, and a non-null delta as its formatted value", () => {
    render(
      <ChangeInAttentionView
        labels={labels}
        change={{
          window_days: 7,
          baseline_tolerance_days: 2,
          as_of: "2026-09-22",
          entries: [
            { category_id: "a", delta: 0.25, rank: 1, baseline_date: "2026-09-15", mixed_scale: false, status: "ok", reason: null },
            { category_id: "c", delta: null, rank: null, baseline_date: null, mixed_scale: false, status: "unavailable", reason: "no-baseline-in-window" },
          ],
        }}
      />
    );
    const nullDelta = screen.getByTestId("change-delta-c");
    expect(nullDelta.textContent).toBe("—");
    expect(nullDelta.textContent).not.toContain("0");
    const row = screen.getByTestId("narrative-change-row-c");
    expect(within(row).getByText(/no composite value 7–9 days earlier/)).toBeInTheDocument();
    expect(screen.getByTestId("change-delta-a").textContent).toBe("+0.25");
  });
});
