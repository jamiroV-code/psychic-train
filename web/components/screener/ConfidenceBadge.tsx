import type { ConfidenceState } from "@/lib/types/screener";

export interface ConfidenceBadgeProps {
  state: ConfidenceState;
  onClick?: () => void;
}

// ADR-4: a distinct, non-numeric label per state — never a score or percent.
// `SignalDetailPanel` renders this as its always-visible tap/click target.
const LABELS: Record<ConfidenceState, string> = {
  aligned: "Aligned",
  mixed: "Mixed",
  conflicting: "Conflicting",
  "insufficient-data": "Insufficient data",
};

/**
 * RFC-004 item 66: one of ADR-4's 4 closed states, rendered as a distinct
 * (non-numeric) visual per state — `data-state` carries the enum value
 * itself for styling/testing, never a derived number.
 */
export function ConfidenceBadge({ state, onClick }: ConfidenceBadgeProps) {
  const clickable = typeof onClick === "function";
  return (
    <button
      type="button"
      data-testid="confidence-badge"
      data-state={state}
      className={`confidence-badge confidence-badge--${state}`}
      onClick={onClick}
      // A badge with no onClick still renders as a real element for visual
      // tests, but shouldn't act as an interactive control in that case.
      disabled={!clickable}
      aria-label={`Confidence: ${LABELS[state]}`}
    >
      {LABELS[state]}
    </button>
  );
}
