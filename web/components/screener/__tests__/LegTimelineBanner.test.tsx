// SANDBOX NOTE: see ScreenerBoard.test.tsx — same environment limitation
// (Next.js/vitest toolchain unavailable in this sandbox session).
import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { LegTimelineBanner } from "@/components/screener/LegTimelineBanner";
import type { LegBoundaryResponse } from "@/lib/types/screener";

function makeResponse(overrides: Partial<LegBoundaryResponse> = {}): LegBoundaryResponse {
  return {
    composite_variant: "reduced",
    candidate_boundaries: [],
    confirmed_boundaries: [],
    active_benchmark_reason: "BTC-dominant / early in the current leg — most recent leg-boundary event is not yet confirmed",
    ...overrides,
  };
}

describe("LegTimelineBanner", () => {
  it("shows a loading state before data arrives", () => {
    const fetchData = vi.fn(() => new Promise<LegBoundaryResponse>(() => {})); // never resolves
    render(<LegTimelineBanner fetchData={fetchData} />);
    expect(screen.getByTestId("leg-timeline-loading")).toBeInTheDocument();
  });

  it("renders confirmed and unconfirmed boundaries in visually distinct sections (ADR-3: unconfirmed never hidden)", async () => {
    const response = makeResponse({
      candidate_boundaries: [
        { date: "2024-06-01", z_score: 1.8, confirmed: true, confirmed_date: "2024-06-03" },
        { date: "2024-09-01", z_score: -1.6, confirmed: false, confirmed_date: null },
      ],
      confirmed_boundaries: [
        { date: "2024-06-01", z_score: 1.8, confirmed: true, confirmed_date: "2024-06-03" },
      ],
    });
    const fetchData = vi.fn(async () => response);
    render(<LegTimelineBanner fetchData={fetchData} />);

    await waitFor(() => expect(screen.getByTestId("leg-confirmed-2024-06-01")).toBeInTheDocument());
    expect(screen.getByTestId("leg-confirmed-2024-06-01").dataset.confirmed).toBe("true");

    expect(screen.getByTestId("leg-candidate-2024-09-01")).toBeInTheDocument();
    expect(screen.getByTestId("leg-candidate-2024-09-01").dataset.confirmed).toBe("false");

    // The confirmed boundary must NOT also appear in the unconfirmed list.
    expect(screen.queryByTestId("leg-candidate-2024-06-01")).not.toBeInTheDocument();
  });

  it("shows empty-state messages, never a blank section, when there is nothing to show", async () => {
    const fetchData = vi.fn(async () => makeResponse());
    render(<LegTimelineBanner fetchData={fetchData} />);

    await waitFor(() => expect(screen.getByTestId("leg-confirmed-empty")).toBeInTheDocument());
    expect(screen.getByTestId("leg-candidate-empty")).toBeInTheDocument();
  });

  it("surfaces the active-benchmark reason and composite variant (SPEC AC-3)", async () => {
    const fetchData = vi.fn(async () => makeResponse({ composite_variant: "full" }));
    render(<LegTimelineBanner fetchData={fetchData} />);

    await waitFor(() => expect(screen.getByTestId("leg-active-benchmark-reason")).toBeInTheDocument());
    expect(screen.getByTestId("leg-composite-variant").textContent).toContain("full");
  });

  // dead-data-notice-unification: closes the pre-existing zero-coverage gap on
  // this component's error branch — mirrors NarrativeStrip.test.tsx's
  // equivalent case exactly (same vi.fn()-mock-rejects-then-assert pattern).
  it("replaces the whole section with leg-timeline-error when the fetch rejects, keeping the confirmed/candidate body absent", async () => {
    const fetchData = vi.fn(async (): Promise<LegBoundaryResponse> => {
      throw new Error("API request timed out after 10000ms: /api/screener/legs");
    });
    render(<LegTimelineBanner fetchData={fetchData} />);

    await waitFor(() => expect(screen.getByTestId("leg-timeline-error")).toBeInTheDocument());
    expect(screen.getByTestId("leg-timeline-error").textContent).toContain(
      "API request timed out after 10000ms"
    );

    // Whole-section-replace: the banner section itself stays, its body does not.
    const section = screen.getByTestId("leg-timeline-banner");
    expect(section).toBeInTheDocument();
    expect(section.getAttribute("aria-label")).toBe("Leg timeline");
    expect(screen.queryByTestId("leg-timeline-loading")).not.toBeInTheDocument();
    expect(screen.queryByTestId("leg-confirmed-boundaries")).not.toBeInTheDocument();
    expect(screen.queryByTestId("leg-candidate-boundaries")).not.toBeInTheDocument();
    expect(screen.queryByTestId("leg-composite-variant")).not.toBeInTheDocument();
  });
});
