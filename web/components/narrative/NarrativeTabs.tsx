"use client";

import { useEffect, useState } from "react";
import { BasketAttentionChart } from "@/components/narrative/BasketAttentionChart";
import { BasketTable } from "@/components/narrative/BasketTable";
import { fetchBasketAttention } from "@/lib/api/attention";
import type { AttentionResponse, AttentionWindow } from "@/lib/types/attention";

export interface NarrativeTabsProps {
  fetchAttention?: (window: AttentionWindow) => Promise<AttentionResponse>;
}

type TabId = "baskets" | "discovery";

const TABS: readonly { id: TabId; label: string }[] = [
  { id: "baskets", label: "My baskets" },
  { id: "discovery", label: "Discovery" },
];

/** /narrative body: My baskets (chart, then ranked table) and Discovery (placeholder until F2). */
export function NarrativeTabs({ fetchAttention = fetchBasketAttention }: NarrativeTabsProps) {
  const [tab, setTab] = useState<TabId>("baskets");
  const [window, setWindow] = useState<AttentionWindow>(30);
  const [data, setData] = useState<AttentionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError(null);
    fetchAttention(window)
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      cancelled = true;
    };
    // fetchAttention is a stable default or an injected test double.
  }, [window]);

  return (
    <div className="narrative-tabs">
      <div role="tablist" aria-label="Narrative" className="narrative-tabs__list">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            id={`narrative-tab-${t.id}`}
            aria-selected={tab === t.id}
            aria-controls={`narrative-panel-${t.id}`}
            data-testid={`narrative-tab-${t.id}`}
            className="narrative-tabs__tab"
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tab === "baskets" ? (
        <div role="tabpanel" id="narrative-panel-baskets" aria-labelledby="narrative-tab-baskets">
          <BasketAttentionChart data={data} window={window} onWindowChange={setWindow} error={error} />
          {data && <BasketTable baskets={data.baskets} />}
        </div>
      ) : (
        <div role="tabpanel" id="narrative-panel-discovery" aria-labelledby="narrative-tab-discovery">
          <p data-testid="discovery-placeholder" className="basket-note">
            Discovery of new narratives is coming.
          </p>
        </div>
      )}
    </div>
  );
}
