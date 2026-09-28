import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

vi.mock("lightweight-charts", () => import("@/test/mocks/lightweight-charts"));

import { mockCharts, resetMockCharts } from "@/test/mocks/lightweight-charts";
import { PairDetailView } from "@/components/pairs/PairDetailView";
import { OPTIMISM_NOTE } from "@/lib/format-pairs-value";
import { DISCLOSURE, detailResponse, okDetail } from "@/components/pairs/__tests__/fixtures";
import type { PairDetailResponse } from "@/lib/types/pairs";

function renderWith(data: PairDetailResponse) {
  return render(<PairDetailView a="DOGE" b="BCH" fetchData={() => Promise.resolve(data)} />);
}

beforeEach(() => resetMockCharts());

describe("PairDetailView", () => {
  it("shows both EG directions and the Johansen block at the same time, never merged (AC-6)", async () => {
    renderWith(detailResponse(okDetail({ johansen: { trace_stat: 18.31, crit_value_95: 15.49, rank_at_least_1: true } })));
    const aOnB = await screen.findByTestId("pairs-eg-a-on-b");
    const bOnA = screen.getByTestId("pairs-eg-b-on-a");
    expect(aOnB).toHaveTextContent("DOGE on BCH");
    expect(aOnB).toHaveTextContent("p-value: 0.00057");
    expect(aOnB).toHaveTextContent("Hedge ratio: 0.812");
    expect(aOnB).toHaveTextContent("t-stat: −4.61");
    expect(aOnB).toHaveAttribute("data-used", "true");
    expect(bOnA).toHaveTextContent("BCH on DOGE");
    expect(bOnA).toHaveTextContent("p-value: 0.0061");
    expect(bOnA).toHaveAttribute("data-used", "false");

    const johansen = screen.getByTestId("pairs-johansen-block");
    expect(johansen).toHaveTextContent("Trace statistic: 18.31");
    expect(johansen).toHaveTextContent("95% critical value: 15.49");
    expect(screen.getByTestId("pairs-johansen-verdict")).toHaveTextContent("Cointegrated at 95% (rank ≥ 1): Yes");
    expect(johansen).not.toContainElement(aOnB);
  });

  it("shows the optimism note, the verbatim disclosure, the sample window and the z-score", async () => {
    renderWith(detailResponse(okDetail()));
    expect(await screen.findByTestId("pairs-optimism-note")).toHaveTextContent(OPTIMISM_NOTE);
    expect(screen.getByTestId("pairs-disclosure").textContent).toBe(DISCLOSURE);
    expect(screen.getByTestId("pairs-sample-window")).toHaveTextContent("Sample: 2020-09-24 → 2020-09-27 (4 days)");
    expect(screen.getByTestId("pairs-detail-z")).toHaveTextContent("Latest z-score: −0.12");
    expect(screen.getByTestId("pairs-half-life")).toHaveTextContent("50 d");
    expect(screen.getByTestId("pairs-bh-p")).toHaveTextContent("0.087");
  });

  it("plots every spread point unchanged, over the sample window (AC-7 unit level)", async () => {
    const pair = okDetail();
    renderWith(detailResponse(pair));
    await screen.findByTestId("pairs-spread-chart");
    // SpreadChart creates the chart in a useEffect that can land after findBy* resolves.
    await waitFor(() => expect(mockCharts).toHaveLength(1));
    const series = mockCharts[0].series;
    expect(series).toHaveLength(1);
    const data = series[0].data as { time: string; value: number }[];
    expect(data).toEqual(pair.spread.map((p) => ({ time: p.date, value: p.spread })));
    expect(data[0].time).toBe(pair.sample_start);
    expect(data[data.length - 1].time).toBe(pair.sample_end);
    expect(screen.getByTestId("pairs-chart-range")).toHaveTextContent("Plotted: 2020-09-24 → 2020-09-27 (4 points)");
  });

  it("shows the not-mean-reverting banner instead of a number", async () => {
    renderWith(detailResponse(okDetail({ half_life: { state: "not_mean_reverting", days: null } })));
    expect(await screen.findByTestId("pairs-not-mean-reverting")).toHaveTextContent("Not mean-reverting — no half-life");
  });

  it("shows the Johansen refusal reason while the pair stays ok", async () => {
    renderWith(detailResponse(okDetail({ johansen: null, johansen_reason: "Johansen refused: singular matrix" })));
    expect(await screen.findByTestId("pairs-johansen-reason")).toHaveTextContent("— Johansen refused: singular matrix");
    expect(screen.getByTestId("pairs-eg-a-on-b")).toBeInTheDocument();
    expect(screen.queryByTestId("pairs-johansen-verdict")).toBeNull();
  });

  it("non-ok pair: reason text, no chart, no statistics", async () => {
    renderWith(
      detailResponse(
        okDetail({
          status: "insufficient_overlap",
          reason: "only 240 days of overlapping history available, need 365",
          spread: [],
          eg_a_on_b: null,
          eg_b_on_a: null,
          johansen: null,
          half_life: null,
          z_score: null,
        })
      )
    );
    expect(await screen.findByTestId("pairs-detail-reason")).toHaveTextContent(
      "only 240 days of overlapping history available, need 365"
    );
    expect(screen.queryByTestId("pairs-spread-chart")).toBeNull();
    expect(screen.queryByTestId("pairs-eg-a-on-b")).toBeNull();
    expect(mockCharts).toHaveLength(0);
  });

  it("shows the stale banner on the detail view", async () => {
    renderWith(detailResponse(okDetail(), { computation_status: "stale", stale_reason: "universe changed" }));
    expect(await screen.findByTestId("pairs-status-banner")).toHaveTextContent("These results are out of date: universe changed.");
  });

  it("shows the API's 404 text and an explicit notice on error", async () => {
    render(
      <PairDetailView
        a="DOGE"
        b="ZZZ"
        fetchData={() =>
          Promise.reject(new Error("API request failed: /api/pairs/DOGE/ZZZ -> 404: ZZZ is not in the pair-screener universe"))
        }
      />
    );
    const notice = await screen.findByTestId("pairs-api-error");
    expect(notice).toHaveTextContent(
      "Pair screener request failed (API request failed: /api/pairs/DOGE/ZZZ -> 404: ZZZ is not in the pair-screener universe)."
    );
    expect(notice).not.toHaveTextContent("could not reach the API");
  });

  it("reports an unreachable API as unreachable", async () => {
    render(<PairDetailView a="DOGE" b="BCH" fetchData={() => Promise.reject(new Error("fetch failed"))} />);
    expect(await screen.findByTestId("pairs-api-error")).toHaveTextContent(
      "Pair screener unavailable — could not reach the API (fetch failed)."
    );
  });

  it("null pair renders an explicit notice", async () => {
    renderWith(detailResponse(null));
    expect(await screen.findByTestId("pairs-detail-missing")).toHaveTextContent("No result for DOGE/BCH.");
  });

  it("never renders NaN, Infinity or undefined", async () => {
    const { container } = renderWith(detailResponse(okDetail()));
    await screen.findByTestId("pairs-eg-a-on-b");
    expect(container.textContent).not.toMatch(/NaN|Infinity|undefined/);
  });
});
