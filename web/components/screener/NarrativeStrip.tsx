"use client";

import { useEffect, useState } from "react";
import { DeadDataNotice } from "@/components/screener/DeadDataNotice";
import { fetchNarrativeCategories } from "@/lib/api/screener";
import type { NarrativeCategory } from "@/lib/types/screener";

export interface NarrativeStripProps {
  fetchData?: () => Promise<NarrativeCategory[]>;
}

function trustLabel(trustWeight: number): string {
  return `trust ${(trustWeight * 100).toFixed(0)}%`;
}

/**
 * RFC-003 item 60. Confirmed-emerging vs. unconfirmed-emerging visual
 * distinction (ADR-3: a triggered-but-unconfirmed category is never
 * hidden, only lower trust_weight) — mirrors LegTimelineBanner's
 * confirmed/candidate split at the narrative layer.
 */
export function NarrativeStrip({ fetchData = fetchNarrativeCategories }: NarrativeStripProps) {
  const [categories, setCategories] = useState<NarrativeCategory[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    fetchData()
      .then((res) => {
        if (!cancelled) setCategories(res);
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
      <section data-testid="narrative-strip" aria-label="Narrative categories">
        <DeadDataNotice testId="narrative-error" message={error} />
      </section>
    );
  }

  if (!categories) {
    return (
      <section data-testid="narrative-strip" aria-label="Narrative categories">
        <span data-testid="narrative-loading">Loading narrative categories…</span>
      </section>
    );
  }

  const triggered = categories.filter((c) => c.triggered);
  const confirmed = triggered.filter((c) => c.confirmed);
  // ADR-3: every triggered category is already in `categories` regardless
  // of `confirmed` — the unconfirmed-emerging list below is derived, never
  // a second fetch that could silently drop one.
  const unconfirmedEmerging = triggered.filter((c) => !c.confirmed);

  return (
    <section data-testid="narrative-strip" aria-label="Narrative categories">
      <div data-testid="narrative-confirmed" aria-label="Confirmed narrative categories">
        <h3>In Focus</h3>
        {confirmed.length === 0 ? (
          <span data-testid="narrative-confirmed-empty">No confirmed narrative categories yet</span>
        ) : (
          <ul>
            {confirmed.map((c) => (
              <li key={c.id} data-testid={`narrative-category-${c.id}`} data-triggered="true" data-confirmed="true">
                {c.label} — {trustLabel(c.trust_weight)}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div data-testid="narrative-unconfirmed" aria-label="Unconfirmed emerging narrative categories">
        <h3>Emerging (unconfirmed)</h3>
        {unconfirmedEmerging.length === 0 ? (
          <span data-testid="narrative-unconfirmed-empty">No unconfirmed emerging categories</span>
        ) : (
          <ul>
            {unconfirmedEmerging.map((c) => (
              <li key={c.id} data-testid={`narrative-category-${c.id}`} data-triggered="true" data-confirmed="false">
                {c.label} — {trustLabel(c.trust_weight)}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
