import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

vi.mock("lightweight-charts", () => import("@/test/mocks/lightweight-charts"));

import { resetMockCharts } from "@/test/mocks/lightweight-charts";
import { NarrativeDashboard } from "@/components/narrative/NarrativeDashboard";
import { category, response } from "./fixtures";

beforeEach(() => resetMockCharts());

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

  it("shows the caveat at the top and on all three views", async () => {
    render(<NarrativeDashboard fetchData={() => Promise.resolve(response(twelve.slice(0, 2)))} />);
    await screen.findByTestId("narrative-dashboard");
    for (const v of ["page", "history", "comparison", "change"]) {
      expect(screen.getByTestId(`narrative-caveat-${v}`)).toHaveTextContent(/not comparable across/);
    }
    expect(screen.getByTestId("narrative-caveat-page")).toHaveTextContent(/unofficial/);
    expect(screen.getByTestId("narrative-caveat-page")).toHaveTextContent(/lower weight/);
  });

  it("shows the personal-use badge when redistributable_all is false", async () => {
    render(<NarrativeDashboard fetchData={() => Promise.resolve(response([category("a", 0.5)]))} />);
    expect(await screen.findByTestId("narrative-redistribution-badge")).toHaveTextContent(/Personal use only/);
  });

  it("renders an injected fetcher error as a notice, with the caveat still visible", async () => {
    render(<NarrativeDashboard fetchData={() => Promise.reject(new Error("API request failed: /x -> 500"))} />);
    expect(await screen.findByTestId("narrative-error")).toHaveTextContent(/500/);
    expect(screen.getByTestId("narrative-caveat-page")).toBeInTheDocument();
  });

  it("renders an empty state when no categories are tracked", async () => {
    render(<NarrativeDashboard fetchData={() => Promise.resolve(response([]))} />);
    expect(await screen.findByTestId("narrative-empty")).toHaveTextContent(/No narrative categories/);
    expect(screen.getByTestId("narrative-comparison-empty")).toBeInTheDocument();
  });
});
