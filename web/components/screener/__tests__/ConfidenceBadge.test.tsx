// SANDBOX NOTE: see ScreenerBoard.test.tsx / NarrativeStrip.test.tsx — same
// environment limitation (Next.js/vitest toolchain unavailable in this
// sandbox session). Written to spec, spot-read for correctness, not run.
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ConfidenceBadge } from "@/components/screener/ConfidenceBadge";
import type { ConfidenceState } from "@/lib/types/screener";

const STATES: ConfidenceState[] = ["aligned", "mixed", "conflicting", "insufficient-data"];

describe("ConfidenceBadge", () => {
  it.each(STATES)("renders a distinct visual for state %s, with no numeric-score text", (state) => {
    render(<ConfidenceBadge state={state} />);
    const badge = screen.getByTestId("confidence-badge");
    expect(badge.dataset.state).toBe(state);
    expect(badge.className).toContain(`confidence-badge--${state}`);
    // ADR-4/Risk Prediction #1: never a numeric or percentage rendering.
    expect(badge.textContent).not.toMatch(/\d/);
  });

  it("renders all four states with mutually distinct visual markers", () => {
    const classNames = STATES.map((state) => {
      const { unmount } = render(<ConfidenceBadge state={state} />);
      const cls = screen.getByTestId("confidence-badge").className;
      unmount();
      return cls;
    });
    expect(new Set(classNames).size).toBe(STATES.length);
  });

  it("fires onClick when clicked/tapped", () => {
    const onClick = vi.fn();
    render(<ConfidenceBadge state="aligned" onClick={onClick} />);
    screen.getByTestId("confidence-badge").click();
    expect(onClick).toHaveBeenCalledTimes(1);
  });
});
