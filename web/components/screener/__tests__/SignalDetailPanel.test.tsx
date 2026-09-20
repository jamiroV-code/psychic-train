// SANDBOX NOTE: see ScreenerBoard.test.tsx / NarrativeStrip.test.tsx — same
// environment limitation (Next.js/vitest toolchain unavailable in this
// sandbox session). Written to spec, spot-read for correctness, not run.
import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { SignalDetailPanel } from "@/components/screener/SignalDetailPanel";
import type { MomentumState, TrendState } from "@/lib/types/screener";

const MOMENTUM: MomentumState = { state: "PASS", daily_value: 65, weekly_value: 60 };
const TREND: TrendState = { direction: "up", sma_value: 123.4 };

describe("SignalDetailPanel", () => {
  it("does not render the detail content until tapped/clicked", () => {
    render(
      <SignalDetailPanel
        confidence="aligned"
        momentum={MOMENTUM}
        trend={TREND}
        legContext="confirmed"
        narrativeState="in-focus"
      />
    );
    expect(screen.queryByTestId("signal-detail-panel-content")).not.toBeInTheDocument();
  });

  it("becomes visible on a simulated tap/click event (touch-emulated)", () => {
    render(
      <SignalDetailPanel
        confidence="mixed"
        momentum={MOMENTUM}
        trend={TREND}
        legContext="candidate-pending"
        narrativeState="unconfirmed-emerging"
      />
    );
    fireEvent.click(screen.getByTestId("confidence-badge"));
    expect(screen.getByTestId("signal-detail-panel-content")).toBeInTheDocument();
  });

  it("renders each signal from its own typed state, not derived from the aggregate badge (Risk Prediction #4)", () => {
    // insufficient-data badge, but momentum/trend are both perfectly
    // healthy — only leg_context is what's driving the insufficiency. The
    // detail view must show that distinction, not report every signal as
    // insufficient.
    render(
      <SignalDetailPanel
        confidence="insufficient-data"
        momentum={MOMENTUM}
        trend={TREND}
        legContext="unavailable"
        narrativeState="in-focus"
      />
    );
    fireEvent.click(screen.getByTestId("confidence-badge"));

    expect(screen.getByTestId("signal-detail-momentum").dataset.state).toBe("PASS");
    expect(screen.getByTestId("signal-detail-trend").dataset.state).toBe("up");
    expect(screen.getByTestId("signal-detail-leg-context").dataset.state).toBe("unavailable");
    expect(screen.getByTestId("signal-detail-narrative").dataset.state).toBe("in-focus");
  });

  it("toggles closed again on a second tap/click", () => {
    render(
      <SignalDetailPanel
        confidence="conflicting"
        momentum={MOMENTUM}
        trend={TREND}
        legContext="confirmed"
        narrativeState="rotated-out"
      />
    );
    const badge = screen.getByTestId("confidence-badge");
    fireEvent.click(badge);
    expect(screen.getByTestId("signal-detail-panel-content")).toBeInTheDocument();
    fireEvent.click(badge);
    expect(screen.queryByTestId("signal-detail-panel-content")).not.toBeInTheDocument();
  });
});
