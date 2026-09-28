import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MomentumView } from "@/components/narrative/MomentumView";
import type { NarrativeMomentumEntry, NarrativeMomentumResponse } from "@/lib/types/narrative";

function entry(p: Partial<NarrativeMomentumEntry> & { category_id: string }): NarrativeMomentumEntry {
  return {
    label: p.category_id.toUpperCase(), momentum_basis: "pytrends-blended", rank: null, as_of: "2026-09-27",
    change: null, prev_change: null, acceleration: null, direction: null, trend: null,
    baseline_date: null, prior_baseline_date: null, status: "ok", reason: null, ...p,
  };
}

const response: NarrativeMomentumResponse = {
  generated_utc: "2026-09-28T00:00:00Z", window_days: 7, acceleration_window_days: 14, tolerance_days: 2,
  entries: [
    entry({ category_id: "ai", rank: 1, change: 0.3, acceleration: 0.1, direction: "up", trend: "accelerating" }),
    entry({ category_id: "rwa", rank: 2, change: -0.2, acceleration: 0.4, direction: "down", trend: "decelerating",
            momentum_basis: "composite" }),
    entry({ category_id: "l2s", momentum_basis: "insufficient", status: "insufficient",
            reason: "not enough history for momentum yet: no mature pytrends-blended or composite series" }),
  ],
};

describe("MomentumView", () => {
  it("renders populated view for pytrends-backfilled narrative", () => {
    render(<MomentumView momentum={response} />);
    const rows = screen.getAllByTestId(/^momentum-row-/);
    expect(rows.map((r) => r.getAttribute("data-testid"))).toEqual(["momentum-row-ai", "momentum-row-rwa"]);
    expect(screen.getByTestId("momentum-arrow-ai")).toHaveTextContent("↑ accelerating");
    expect(screen.getByTestId("momentum-arrow-rwa")).toHaveTextContent("↓ decelerating");
    expect(screen.getByTestId("momentum-change-ai")).toHaveTextContent("+0.30");
    expect(screen.getByTestId("momentum-basis-ai")).toHaveTextContent("Google Trends (blended)");
    expect(screen.getByTestId("momentum-basis-rwa")).toHaveTextContent("composite");
    expect(screen.getByTestId("momentum-insufficient-l2s")).toHaveTextContent("not enough history for momentum yet");
    expect(screen.queryByTestId("momentum-row-l2s")).toBeNull();
  });

  it("shows an explicit empty state when nothing has enough history", () => {
    render(<MomentumView momentum={{ ...response, entries: [response.entries[2]] }} />);
    expect(screen.getByTestId("narrative-momentum-empty")).toBeInTheDocument();
  });
});
