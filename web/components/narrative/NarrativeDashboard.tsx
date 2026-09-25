"use client";

import { useEffect, useMemo, useState } from "react";
import { CategoryHistoryPanel } from "@/components/narrative/CategoryHistoryPanel";
import { ChangeInAttentionView } from "@/components/narrative/ChangeInAttentionView";
import { ComparisonView } from "@/components/narrative/ComparisonView";
import { DataQualityCaveat } from "@/components/narrative/DataQualityCaveat";
import { RedistributionBadge } from "@/components/narrative/RedistributionBadge";
import { DeadDataNotice } from "@/components/screener/DeadDataNotice";
import { fetchNarrativeHistory } from "@/lib/api/narrative";
import { splitSoftCap } from "@/lib/narrative-view-model";
import type { NarrativeHistoryResponse } from "@/lib/types/narrative";

export interface NarrativeDashboardProps {
  fetchData?: () => Promise<NarrativeHistoryResponse>;
}

/**
 * /narrative page body (ADR-9, RFC-5): fetch once, one scrolling page with the
 * caveat at the top and on each of the three stacked views (history,
 * comparison, change-in-attention). History panels are soft-capped at 10 with
 * an expandable overflow list — no category is ever dropped.
 */
export function NarrativeDashboard({ fetchData = () => fetchNarrativeHistory() }: NarrativeDashboardProps) {
  const [data, setData] = useState<NarrativeHistoryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [openOverflow, setOpenOverflow] = useState<Set<string>>(new Set());
  const [showOverflow, setShowOverflow] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchData()
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      cancelled = true;
    };
    // Fetch once on mount: one endpoint, full history.
  }, []);

  const split = useMemo(() => (data ? splitSoftCap(data.categories) : null), [data]);
  const labels = useMemo(
    () => Object.fromEntries((data?.categories ?? []).map((c) => [c.category_id, c.label])),
    [data]
  );

  if (error) {
    return (
      <div data-testid="narrative-dashboard">
        <DataQualityCaveat view="page" />
        <DeadDataNotice testId="narrative-error" message={`Narrative history unavailable — ${error}`} />
      </div>
    );
  }
  if (!data || !split) {
    return <div data-testid="narrative-loading">Loading narrative history…</div>;
  }

  const toggleItem = (id: string) =>
    setOpenOverflow((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  return (
    <div data-testid="narrative-dashboard">
      <div style={{ fontSize: 12, color: "#8a8f98" }}>
        generated {data.generated_utc}
        <RedistributionBadge redistributable={data.redistributable_all} testId="narrative-redistribution-badge" />
      </div>
      <DataQualityCaveat view="page" />

      <section data-testid="narrative-history">
        <h2>Attention history by category</h2>
        <DataQualityCaveat view="history" />
        {data.categories.length === 0 ? (
          <DeadDataNotice testId="narrative-empty" message="No narrative categories tracked yet" />
        ) : (
          <>
            {split.visible.map((c) => (
              <CategoryHistoryPanel key={c.category_id} category={c} />
            ))}
            {split.overflow.length > 0 && (
              <div>
                <button
                  type="button"
                  data-testid="narrative-overflow-toggle"
                  aria-expanded={showOverflow}
                  onClick={() => setShowOverflow((s) => !s)}
                >
                  {showOverflow ? "Hide" : `+${split.overflow.length} more categories`}
                </button>
                {showOverflow && (
                  <ul data-testid="narrative-overflow-list" style={{ listStyle: "none", paddingLeft: 0 }}>
                    {split.overflow.map((c) => (
                      <li key={c.category_id}>
                        <button
                          type="button"
                          data-testid={`narrative-overflow-item-${c.category_id}`}
                          aria-expanded={openOverflow.has(c.category_id)}
                          onClick={() => toggleItem(c.category_id)}
                        >
                          {c.label}
                        </button>
                        {openOverflow.has(c.category_id) && <CategoryHistoryPanel category={c} />}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </>
        )}
      </section>

      <ComparisonView comparison={data.comparison} labels={labels} />
      <ChangeInAttentionView change={data.change_in_attention} labels={labels} />
    </div>
  );
}
