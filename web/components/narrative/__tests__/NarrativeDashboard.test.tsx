import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { NarrativeDashboard } from "@/components/narrative/NarrativeDashboard";
import { category, response } from "./fixtures";
import type { NarrativeMindshareResponse, NarrativeMomentumResponse } from "@/lib/types/narrative";

const stubViews = {
  fetchMomentum: (): Promise<NarrativeMomentumResponse> =>
    Promise.resolve({ generated_utc: "2026-09-28T00:00:00Z", window_days: 7, acceleration_window_days: 14, tolerance_days: 2, entries: [] }),
  fetchMindshare: (): Promise<NarrativeMindshareResponse> =>
    Promise.resolve({
      generated_utc: "2026-09-28T00:00:00Z", date: null, available_dates: [], sources_present: [], n_sources: 0,
      only_one_source: false, no_sources_available: true, entries: [],
    }),
};

const twelve = Array.from({ length: 12 }, (_, i) => category(`c${String(i).padStart(2, "0")}`, (12 - i) / 12));

describe("NarrativeDashboard", () => {
  it("shows the loading state before data arrives", () => {
    render(<NarrativeDashboard fetchData={() => new Promise(() => {})} />);
    expect(screen.getByTestId("narrative-loading")).toBeInTheDocument();
  });

  it("renders one panel per category up to the soft cap of 10, rest in an overflow list", async () => {
    render(<NarrativeDashboard fetchData={() => Promise.resolve(response(twelve))} />);
    await screen.findByTestId("narrative-dashboard");
    expect(screen.getAllByTestId(/^narrative-panel-/)).toHaveLength(10);
    expect(screen.queryByTestId("narrative-panel-c10")).toBeNull();
    const toggle = screen.getByTestId("narrative-overflow-toggle");
    expect(toggle).toHaveTextContent("+2 more categories");
    fireEvent.click(toggle);
    expect(screen.getByTestId("narrative-overflow-list")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("narrative-overflow-item-c11"));
    expect(screen.getByTestId("narrative-panel-c11")).toBeInTheDocument();
    expect(screen.getAllByTestId(/^narrative-panel-/)).toHaveLength(11);
  });

  it("has no overflow toggle when categories fit under the cap", async () => {
    render(<NarrativeDashboard fetchData={() => Promise.resolve(response(twelve.slice(0, 3)))} />);
    await screen.findByTestId("narrative-dashboard");
    expect(screen.queryByTestId("narrative-overflow-toggle")).toBeNull();
  });

  it.each([6, 15])("exactly one caveat instance regardless of narrative count (%i narratives)", async (n) => {
    const cats = Array.from({ length: n }, (_, i) => category(`n${String(i).padStart(2, "0")}`, (n - i) / n));
    render(<NarrativeDashboard fetchData={() => Promise.resolve(response(cats))} {...stubViews} />);
    await screen.findByTestId("narrative-dashboard");
    expect(screen.getAllByTestId("narrative-caveat")).toHaveLength(1);
    expect(screen.getAllByTestId(/^narrative-caveat/)).toHaveLength(2); // wrapper + its one inner caveat
    const caveat = screen.getByTestId("narrative-caveat");
    expect(caveat).toHaveStyle({ position: "sticky" });
    expect(caveat).toHaveTextContent(/unofficial/);
    expect(caveat).toHaveTextContent(/not comparable across/);
    expect(caveat).toHaveTextContent(/lower weight/);
    for (const v of ["history", "comparison", "change"]) {
      expect(screen.queryByTestId(`narrative-caveat-${v}`)).toBeNull();
    }
  });

  it("mounts the momentum and mindshare views on the page", async () => {
    render(<NarrativeDashboard fetchData={() => Promise.resolve(response(twelve.slice(0, 3)))} {...stubViews} />);
    expect(await screen.findByTestId("narrative-momentum")).toBeInTheDocument();
    expect(await screen.findByTestId("narrative-mindshare")).toBeInTheDocument();
    expect(screen.getAllByTestId("narrative-caveat")).toHaveLength(1);
  });

  it("shows a notice (not a crash) when momentum or mindshare fail, keeping history visible", async () => {
    render(
      <NarrativeDashboard
        fetchData={() => Promise.resolve(response(twelve.slice(0, 2)))}
        fetchMomentum={() => Promise.reject(new Error("momentum 500"))}
        fetchMindshare={() => Promise.reject(new Error("mindshare 500"))}
      />
    );
    expect(await screen.findByTestId("narrative-momentum-error")).toHaveTextContent(/momentum 500/);
    expect(await screen.findByTestId("narrative-mindshare-error")).toHaveTextContent(/mindshare 500/);
    expect(screen.getByTestId("narrative-history")).toBeInTheDocument();
  });

  it("shows the personal-use badge when redistributable_all is false", async () => {
    render(<NarrativeDashboard fetchData={() => Promise.resolve(response([category("a", 0.5)]))} />);
    expect(await screen.findByTestId("narrative-redistribution-badge")).toHaveTextContent(/Personal use only/);
  });

  it("renders an injected fetcher error as a notice, with the caveat still visible", async () => {
    render(<NarrativeDashboard fetchData={() => Promise.reject(new Error("API request failed: /x -> 500"))} />);
    expect(await screen.findByTestId("narrative-error")).toHaveTextContent(/500/);
    expect(screen.getAllByTestId("narrative-caveat")).toHaveLength(1);
  });

  it("renders an empty state when no categories are tracked", async () => {
    render(<NarrativeDashboard fetchData={() => Promise.resolve(response([]))} />);
    expect(await screen.findByTestId("narrative-empty")).toHaveTextContent(/No narrative categories/);
    expect(screen.getByTestId("narrative-comparison-empty")).toBeInTheDocument();
  });
});
