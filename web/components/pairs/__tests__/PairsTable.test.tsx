import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { PairsTable } from "@/components/pairs/PairsTable";
import { RAW_ONLY_TAG } from "@/lib/format-pairs-value";
import { DISCLOSURE, tableResponse } from "@/components/pairs/__tests__/fixtures";
import type { PairsResponse } from "@/lib/types/pairs";

function renderWith(data: PairsResponse) {
  return render(<PairsTable fetchData={() => Promise.resolve(data)} />);
}

describe("PairsTable", () => {
  it("renders one row per pair (C(4,2) = 6) in the fixed order", async () => {
    renderWith(tableResponse());
    const table = await screen.findByTestId("pairs-table");
    const rows = within(table).getAllByTestId(/^pairs-row-/);
    expect(rows).toHaveLength(6);
    expect(rows.map((r) => r.getAttribute("data-testid"))).toEqual([
      "pairs-row-DOGE-BCH",
      "pairs-row-ETH-BCH",
      "pairs-row-BCH-DOGE",
      "pairs-row-ETH-DOGE",
      "pairs-row-BCH-NEW",
      "pairs-row-DOGE-DEAD",
    ]);
  });

  it("shows raw and corrected p side by side, overlap days and formatted stats", async () => {
    renderWith(tableResponse());
    const row = await screen.findByTestId("pairs-row-DOGE-BCH");
    const text = row.textContent ?? "";
    expect(text).toContain("0.00057");
    expect(text).toContain("0.087");
    expect(text).toContain("2,183");
    expect(text).toContain("DOGE on BCH");
    expect(text).toContain("114 d");
    expect(text).toContain("−0.12");
    expect(text).toContain("No"); // Johansen yes/no
  });

  it("shows the significance banner and the verbatim disclosure", async () => {
    renderWith(tableResponse());
    expect(await screen.findByTestId("pairs-significance-banner")).toHaveTextContent(
      "No pair is significant after correcting for 4 tests (5% level). Closest: DOGE/BCH, corrected p 0.087."
    );
    expect(screen.getByTestId("pairs-disclosure").textContent).toBe(DISCLOSURE);
  });

  it("tags rows that pass raw p but not after correction, without hiding them", async () => {
    renderWith(tableResponse());
    expect(await screen.findByTestId("pairs-raw-only-DOGE-BCH")).toHaveTextContent(RAW_ONLY_TAG);
    expect(screen.getByTestId("pairs-raw-only-ETH-BCH")).toBeInTheDocument();
    expect(screen.queryByTestId("pairs-raw-only-BCH-DOGE")).toBeNull();
  });

  it("renders insufficient_overlap and coin_unavailable rows with reason text and no stat cells", async () => {
    renderWith(tableResponse());
    const insufficient = await screen.findByTestId("pairs-row-BCH-NEW");
    expect(within(insufficient).getByTestId("pairs-reason-BCH-NEW")).toHaveTextContent(
      "only 240 days of overlapping history available, need 365"
    );
    expect(insufficient.textContent).toContain("240");
    expect(insufficient.querySelectorAll("td")).toHaveLength(4);

    const unavailable = screen.getByTestId("pairs-row-DOGE-DEAD");
    expect(within(unavailable).getByTestId("pairs-reason-DOGE-DEAD")).toHaveTextContent(
      "DEAD: bad_symbol — not found on Hyperliquid market list"
    );
    expect(unavailable.textContent).toContain("—"); // overlap days null
  });

  it("keeps a Johansen-refused pair ok, ranked, with the reason in the Johansen cell", async () => {
    renderWith(tableResponse());
    const row = await screen.findByTestId("pairs-row-ETH-DOGE");
    expect(row).toHaveAttribute("data-status", "ok");
    expect(within(row).getByTestId("pairs-johansen-reason-ETH-DOGE")).toHaveTextContent(
      "— Johansen refused: singular matrix"
    );
    expect(row.textContent).toContain("Not mean-reverting — no half-life");
  });

  it("shows the stale banner with stale_reason and keeps the table", async () => {
    renderWith(tableResponse({ computation_status: "stale", stale_reason: "BTC has a newer last bar than the results" }));
    const banner = await screen.findByTestId("pairs-status-banner");
    expect(banner).toHaveTextContent(
      "These results are out of date: BTC has a newer last bar than the results. Showing the last computed results from 2026-09-27T17:05:13Z."
    );
    expect(screen.getByTestId("pairs-table")).toBeInTheDocument();
  });

  it("shows results_unavailable with its reason and no table", async () => {
    renderWith(
      tableResponse({ computation_status: "results_unavailable", stale_reason: "no results file — run compute_pairs.py", pairs: [] })
    );
    expect(await screen.findByTestId("pairs-status-banner")).toHaveTextContent(
      "No pair results available: no results file — run compute_pairs.py."
    );
    expect(screen.queryByTestId("pairs-table")).toBeNull();
    expect(screen.queryByTestId("pairs-significance-banner")).toBeNull();
  });

  it("renders nothing extra when fresh", async () => {
    renderWith(tableResponse());
    await screen.findByTestId("pairs-table");
    expect(screen.queryByTestId("pairs-status-banner")).toBeNull();
  });

  it("shows an explicit notice when the API is unreachable (AC-8)", async () => {
    render(<PairsTable fetchData={() => Promise.reject(new Error("fetch failed"))} />);
    expect(await screen.findByTestId("pairs-api-error")).toHaveTextContent(
      "Pair screener unavailable — could not reach the API (fetch failed)."
    );
    expect(screen.queryByTestId("pairs-table")).toBeNull();
  });

  it("never renders NaN, Infinity or undefined", async () => {
    const { container } = renderWith(tableResponse());
    await screen.findByTestId("pairs-table");
    expect(container.textContent).not.toMatch(/NaN|Infinity|undefined/);
  });

  it("links each pair to its detail route", async () => {
    renderWith(tableResponse());
    const row = await screen.findByTestId("pairs-row-DOGE-BCH");
    expect(within(row).getByRole("link", { name: "DOGE/BCH" })).toHaveAttribute("href", "/pairs/DOGE/BCH");
  });
});
