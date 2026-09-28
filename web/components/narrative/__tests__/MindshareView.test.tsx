import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MindshareView } from "@/components/narrative/MindshareView";
import type { NarrativeMindshareEntry, NarrativeMindshareResponse } from "@/lib/types/narrative";

function entry(id: string, m: number | null, cg: number | null): NarrativeMindshareEntry {
  return {
    category_id: id, label: id.toUpperCase(), mindshare: m,
    sources: { pytrends: null, coingecko: cg, reddit: null },
    status: m === null ? "excluded" : "ok", reason: m === null ? "no data from any available source on this day" : null,
  };
}

function response(p: Partial<NarrativeMindshareResponse> = {}): NarrativeMindshareResponse {
  return {
    generated_utc: "2026-09-28T00:00:00Z", date: "2026-09-27", available_dates: ["2026-09-26", "2026-09-27"],
    sources_present: ["coingecko"], n_sources: 1, only_one_source: true, no_sources_available: false,
    entries: [entry("ai", 0.75, 0.75), entry("rwa", 0.25, 0.25), entry("l2s", null, null)], ...p,
  };
}

describe("MindshareView", () => {
  it("renders proxy-labelled caveat on this view", () => {
    render(<MindshareView mindshare={response()} />);
    expect(screen.getByTestId("mindshare-proxy-label").textContent).toMatch(/Proxy/);
  });

  it("renders a 100%-stacked bar, per-source shares and the only-one-source label", () => {
    render(<MindshareView mindshare={response()} />);
    expect(screen.getByTestId("mindshare-segment-ai").style.width).toBe("75%");
    expect(screen.getByTestId("mindshare-value-rwa").textContent).toBe("25.0%");
    expect(screen.getByTestId("mindshare-only-one-source")).toBeTruthy();
    expect(screen.getByTestId("mindshare-excluded-l2s").textContent).toMatch(/no data/);
    expect(screen.queryByTestId("mindshare-segment-l2s")).toBeNull();
  });

  it("shows no-sources state and a date picker that reports changes", () => {
    const onDateChange = vi.fn();
    render(<MindshareView mindshare={response({ no_sources_available: true, only_one_source: false,
      n_sources: 0, sources_present: [] })} onDateChange={onDateChange} />);
    expect(screen.getByTestId("mindshare-no-sources")).toBeTruthy();
    fireEvent.change(screen.getByTestId("mindshare-date-picker"), { target: { value: "2026-09-26" } });
    expect(onDateChange).toHaveBeenCalledWith("2026-09-26");
  });

  it("scales to 15 narratives with no fixed slot count", () => {
    const entries = Array.from({ length: 15 }, (_, i) => entry(`n${i}`, 1 / 15, 1 / 15));
    render(<MindshareView mindshare={response({ entries })} />);
    expect(screen.getAllByTestId(/^mindshare-segment-/)).toHaveLength(15);
  });
});
