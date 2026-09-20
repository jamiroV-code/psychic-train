"use client";

import { useEffect, useState } from "react";
import { DeadDataNotice } from "@/components/screener/DeadDataNotice";
import { fetchLegs } from "@/lib/api/screener";
import type { LegBoundary, LegBoundaryResponse } from "@/lib/types/screener";

export interface LegTimelineBannerProps {
  fetchData?: () => Promise<LegBoundaryResponse>;
}

function formatBoundary(b: LegBoundary): string {
  return `${b.date} (z=${b.z_score.toFixed(2)})`;
}

/**
 * RFC-002 item 46. Confirmed-vs-candidate-pending visual distinction
 * (ADR-3: a candidate is never hidden just because it isn't confirmed yet)
 * plus the currently-active BTC/HYPE benchmark and why (SPEC AC-3).
 */
export function LegTimelineBanner({ fetchData = fetchLegs }: LegTimelineBannerProps) {
  const [data, setData] = useState<LegBoundaryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchData()
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [fetchData]);

  if (error) {
    return (
      <section data-testid="leg-timeline-banner" aria-label="Leg timeline">
        <DeadDataNotice testId="leg-timeline-error" message={error} />
      </section>
    );
  }

  if (!data) {
    return (
      <section data-testid="leg-timeline-banner" aria-label="Leg timeline">
        <span data-testid="leg-timeline-loading">Loading leg timeline…</span>
      </section>
    );
  }

  const confirmedDates = new Set(data.confirmed_boundaries.map((b) => b.date));
  // ADR-3: candidate_boundaries already lists every detected candidate
  // (its own `confirmed` flag says whether it was later confirmed) — the
  // unconfirmed ones are rendered distinctly here, never omitted.
  const unconfirmed = data.candidate_boundaries.filter((b) => !confirmedDates.has(b.date));

  return (
    <section data-testid="leg-timeline-banner" aria-label="Leg timeline">
      <div data-testid="leg-composite-variant">
        Composite: <strong>{data.composite_variant === "full" ? "full (LiqTide)" : "reduced (FRED + DefiLlama)"}</strong>
      </div>

      <div data-testid="leg-active-benchmark-reason" role="status">
        {data.active_benchmark_reason}
      </div>

      <div data-testid="leg-confirmed-boundaries" aria-label="Confirmed leg boundaries">
        <h3>Confirmed</h3>
        {data.confirmed_boundaries.length === 0 ? (
          <span data-testid="leg-confirmed-empty">No confirmed leg boundaries yet</span>
        ) : (
          <ul>
            {data.confirmed_boundaries.map((b) => (
              <li key={b.date} data-testid={`leg-confirmed-${b.date}`} data-confirmed="true">
                {formatBoundary(b)}
                {b.confirmed_date ? ` — confirmed ${b.confirmed_date}` : ""}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div data-testid="leg-candidate-boundaries" aria-label="Candidate (unconfirmed) leg boundaries">
        <h3>Candidate (unconfirmed)</h3>
        {unconfirmed.length === 0 ? (
          <span data-testid="leg-candidate-empty">No unconfirmed candidates</span>
        ) : (
          <ul>
            {unconfirmed.map((b) => (
              <li key={b.date} data-testid={`leg-candidate-${b.date}`} data-confirmed="false">
                {formatBoundary(b)}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
