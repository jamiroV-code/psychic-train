// SANDBOX NOTE: see ScreenerBoard.test.tsx — same environment limitation
// (Next.js/vitest toolchain unavailable in this sandbox session).
import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { NarrativeStrip } from "@/components/screener/NarrativeStrip";
import type { NarrativeCategory } from "@/lib/types/screener";

function makeCategory(overrides: Partial<NarrativeCategory> = {}): NarrativeCategory {
  return {
    id: "ai",
    label: "AI",
    keywords: ["AI crypto"],
    seed: true,
    triggered: false,
    confirmed: false,
    trust_weight: 0,
    source_availability: { pytrends: "ok", reddit: "ok", coingecko: "ok" },
    ...overrides,
  };
}

describe("NarrativeStrip", () => {
  it("shows a loading state before data arrives", () => {
    const fetchData = vi.fn(() => new Promise<NarrativeCategory[]>(() => {})); // never resolves
    render(<NarrativeStrip fetchData={fetchData} />);
    expect(screen.getByTestId("narrative-loading")).toBeInTheDocument();
  });

  it("renders confirmed and unconfirmed-emerging categories in visually distinct sections (ADR-3: unconfirmed never hidden)", async () => {
    const categories = [
      makeCategory({ id: "ai", triggered: true, confirmed: true, trust_weight: 0.9 }),
      makeCategory({ id: "rwa", label: "RWA", triggered: true, confirmed: false, trust_weight: 0.6 }),
    ];
    const fetchData = vi.fn(async () => categories);
    render(<NarrativeStrip fetchData={fetchData} />);

    await waitFor(() => expect(screen.getByTestId("narrative-category-ai")).toBeInTheDocument());
    expect(screen.getByTestId("narrative-category-ai").dataset.confirmed).toBe("true");

    expect(screen.getByTestId("narrative-category-rwa")).toBeInTheDocument();
    expect(screen.getByTestId("narrative-category-rwa").dataset.confirmed).toBe("false");

    // A category is either in the confirmed list or the unconfirmed list, never both.
    expect(screen.getAllByTestId("narrative-category-ai")).toHaveLength(1);
  });

  it("shows empty-state messages, never a blank section, when nothing has triggered", async () => {
    const fetchData = vi.fn(async () => [makeCategory({ triggered: false })]);
    render(<NarrativeStrip fetchData={fetchData} />);

    await waitFor(() => expect(screen.getByTestId("narrative-confirmed-empty")).toBeInTheDocument());
    expect(screen.getByTestId("narrative-unconfirmed-empty")).toBeInTheDocument();
  });

  it("surfaces degraded trust_weight for a reduced-confidence category (AC-11)", async () => {
    const fetchData = vi.fn(async () => [
      makeCategory({ id: "ai", triggered: true, confirmed: false, trust_weight: 0.4 }),
    ]);
    render(<NarrativeStrip fetchData={fetchData} />);

    await waitFor(() => expect(screen.getByTestId("narrative-category-ai")).toBeInTheDocument());
    expect(screen.getByTestId("narrative-category-ai").textContent).toContain("40%");
  });

  // SANDBOX NOTE (RFC-006 getjson-timeout-catch): the case below was written
  // but NOT executed in the session that added it — no shell was reachable on
  // the machine holding this repo, so vitest never ran. Same limitation as the
  // file-level note above; treat as written-to-spec only.
  it("replaces the whole section with narrative-error when the fetch rejects (AC-3)", async () => {
    const fetchData = vi.fn(async (): Promise<NarrativeCategory[]> => {
      throw new Error("API request timed out after 10000ms: /api/narrative/categories");
    });
    render(<NarrativeStrip fetchData={fetchData} />);

    await waitFor(() => expect(screen.getByTestId("narrative-error")).toBeInTheDocument());
    expect(screen.getByTestId("narrative-error").textContent).toContain(
      "API request timed out after 10000ms"
    );

    // Whole-section-replace: the strip section itself stays, its body does not.
    const section = screen.getByTestId("narrative-strip");
    expect(section).toBeInTheDocument();
    expect(section.getAttribute("aria-label")).toBe("Narrative categories");
    expect(screen.queryByTestId("narrative-loading")).not.toBeInTheDocument();
    expect(screen.queryByTestId("narrative-confirmed")).not.toBeInTheDocument();
    expect(screen.queryByTestId("narrative-unconfirmed")).not.toBeInTheDocument();
  });
});
