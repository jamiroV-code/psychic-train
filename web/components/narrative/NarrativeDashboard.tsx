"use client";

import { useEffect, useMemo, useState } from "react";
import { CategoryHistoryPanel } from "@/components/narrative/CategoryHistoryPanel";
import { ChangeInAttentionView } from "@/components/narrative/ChangeInAttentionView";
import { ComparisonView } from "@/components/narrative/ComparisonView";
import { DataQualityCaveat } from "@/components/narrative/DataQualityCaveat";
import { MindshareView } from "@/components/narrative/MindshareView";
import { MomentumView } from "@/components/narrative/MomentumView";
import { RedistributionBadge } from "@/components/narrative/RedistributionBadge";
import { DeadDataNotice } from "@/components/screener/DeadDataNotice";
import { fetchNarrativeHistory, fetchNarrativeMindshare, fetchNarrativeMomentum } from "@/lib/api/narrative";
import { splitSoftCap } from "@/lib/narrative-view-model";
import type {
  NarrativeHistoryResponse,
  NarrativeMindshareResponse,
  NarrativeMomentumResponse,
} from "@/lib/types/narrative";

export interface NarrativeDashboardProps {
  fetchData?: () => Promise<NarrativeHistoryResponse>;
  fetchMomentum?: () => Promise<NarrativeMomentumResponse>;
  fetchMindshare?: (date?: string) => Promise<NarrativeMindshareResponse>;
}

/** The single, pinned data-quality caveat for the whole page (v2 ADR-6, AC-12). */
function PinnedCaveat() {
  return (
    <div data-testid="narrative-caveat" style={{ position: "sticky", top: 0, zIndex: 2, background: "Canvas" }}>
      <DataQualityCaveat view="page" />
    </div>
  );
}

/**
 * /narrative page body: fetch history once, one scrolling page with a single
 * pinned data-quality caveat (v2 ADR-6) above the stacked views (history,
 * comparison, change-in-attention, momentum, mindshare). History panels are
 * soft-capped at 10 with an expandable overflow list — no category is ever
 * dropped. Momentum and mindshare load independently, so a failure in one
 * never hides the history views.
 */
export function NarrativeDashboard({
  fetchData = () => fetchNarrativeHistory(),
  fetchMomentum = () => fetchNarrativeMomentum(),
  fetchMindshare = (date?: string) => fetchNarrativeMindshare(date),
}: NarrativeDashboardProps) {
  const [data, setData] = useState<NarrativeHistoryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [openOverflow, setOpenOverflow] = useState<Set<string>>(new Set());
  const [showOverflow, setShowOverflow] = useState(false);
  const [momentum, setMomentum] = useState<NarrativeMomentumResponse | null>(null);
  const [momentumError, setMomentumError] = useState<string | null>(null);
  const [mindshare, setMindshare] = useState<NarrativeMindshareResponse | null>(null);
  const [mindshareError, setMindshareError] = useState<string | null>(null);
  const [mindshareDate, setMindshareDate] = useState<string | undefined>(undefined);

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

  useEffect(() => {
    let cancelled = false;
    fetchMomentum()
      .then((m) => {
        if (!cancelled) setMomentum(m);
      })
      .catch((err: unknown) => {
        if (!cancelled) setMomentumError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setMindshareError(null);
    fetchMindshare(mindshareDate)
      .then((m) => {
        if (!cancelled) setMindshare(m);
      })
      .catch((err: unknown) => {
        if (!cancelled) setMindshareError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      cancelled = true;
    };
  }, [mindshareDate]);

  const split = useMemo(() => (data ? splitSoftCap(data.categories) : null), [data]);
  const labels = useMemo(
    () => Object.fromEntries((data?.categories ?? []).map((c) => [c.category_id, c.label])),
    [data]
  );

  if (error) {
    return (
      <div data-testid="narrative-dashboard">
        <PinnedCaveat />
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
      <PinnedCaveat />

      <section data-testid="narrative-history">
        <h2>Attention history by category</h2>
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

      {momentumError ? (
        <DeadDataNotice testId="narrative-momentum-error" message={`Narrative momentum unavailable — ${momentumError}`} />
      ) : momentum ? (
        <MomentumView momentum={momentum} />
      ) : (
        <div data-testid="narrative-momentum-loading">Loading momentum…</div>
      )}

      {mindshareError ? (
        <DeadDataNotice testId="narrative-mindshare-error" message={`Narrative mindshare unavailable — ${mindshareError}`} />
      ) : mindshare ? (
        <MindshareView mindshare={mindshare} onDateChange={setMindshareDate} />
      ) : (
        <div data-testid="narrative-mindshare-loading">Loading mindshare…</div>
      )}
    </div>
  );
}
