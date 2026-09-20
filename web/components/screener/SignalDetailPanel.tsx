"use client";

import { useState } from "react";
import { ConfidenceBadge } from "@/components/screener/ConfidenceBadge";
import type {
  ConfidenceState,
  LegContextLiteral,
  MomentumState,
  NarrativeStateLiteral,
  TrendState,
} from "@/lib/types/screener";

export interface SignalDetailPanelProps {
  confidence: ConfidenceState;
  momentum: MomentumState;
  trend: TrendState;
  legContext: LegContextLiteral;
  narrativeState: NarrativeStateLiteral;
}

/**
 * RFC-004 item 67: tap-to-expand per-signal detail. Owns its own open/
 * closed state, using the `ConfidenceBadge` (item 66) as its always-visible
 * trigger — fires on `onClick` (covers touch taps as well as mouse clicks;
 * this codebase has no hover-only interaction anywhere else either, see
 * `CoinPanel.tsx`'s drill-down button), never `:hover`-only.
 *
 * Risk Prediction #4: each of the four signals below is rendered from its
 * own typed prop (`momentum`, `trend`, `legContext`, `narrativeState`),
 * never re-derived from `confidence` — an `insufficient-data` badge does
 * not imply every individual signal is itself insufficient (e.g. momentum
 * and trend can both be perfectly healthy while `leg_context` alone is
 * `unavailable`), and the detail view must show that distinction rather
 * than collapsing it.
 */
export function SignalDetailPanel({ confidence, momentum, trend, legContext, narrativeState }: SignalDetailPanelProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div data-testid="signal-detail-panel" className="signal-detail-panel">
      <ConfidenceBadge state={confidence} onClick={() => setExpanded((prev) => !prev)} />

      {expanded && (
        <dl data-testid="signal-detail-panel-content" className="signal-detail-panel__content">
          <dt>Momentum</dt>
          <dd data-testid="signal-detail-momentum" data-state={momentum.state}>
            {momentum.state}
          </dd>

          <dt>Trend</dt>
          <dd data-testid="signal-detail-trend" data-state={trend.direction}>
            {trend.direction}
          </dd>

          <dt>Leg timing</dt>
          <dd data-testid="signal-detail-leg-context" data-state={legContext}>
            {legContext}
          </dd>

          <dt>Narrative</dt>
          <dd data-testid="signal-detail-narrative" data-state={narrativeState}>
            {narrativeState}
          </dd>
        </dl>
      )}
    </div>
  );
}
