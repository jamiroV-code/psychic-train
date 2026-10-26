"use client";

import { useEffect, useState } from "react";
import { fetchDiscoverySources as fetchDefault } from "@/lib/api/discovery";
import { formatNarrativeReason } from "@/lib/format-unavailable-reason";
import type { DiscoverySourceRow, DiscoverySourcesResponse } from "@/lib/types/discovery";

export interface DiscoverySourcesPanelProps {
  fetchSources?: () => Promise<DiscoverySourcesResponse>;
}

const STATE_TEXT: Record<DiscoverySourceRow["state"], string> = {
  ok: "ok",
  "insufficient-history": "short history",
  unavailable: "unavailable",
  "not-probed": "not probed",
  off: "off",
};

function summary(d: DiscoverySourcesResponse): { text: string; tone: "ok" | "partial" | "none" } {
  const tone = d.live_sources === 0 ? "none" : d.live_sources === d.total_sources ? "ok" : "partial";
  const newest = d.newest ? `, newest data ${d.newest}` : "";
  return { text: `Sources: ${d.live_sources} of ${d.total_sources} live, ${Math.round(d.live_weight)} of 100 weight${newest}`, tone };
}

/** The Trends row's note gains the keyword coverage and the coins without a keyword (T180). */
function note(r: DiscoverySourceRow, d: DiscoverySourcesResponse): string {
  const tk = d.trends_keyword;
  if (r.id !== "trends" || !tk) return r.note;
  const parts = [r.note, `Trends keyword: ${tk.with_keyword} of ${tk.eligible_size} eligible coins`];
  if (tk.missing.length) {
    parts.push(`${formatNarrativeReason("no-trends-keyword")}: ${tk.missing.map((g) => g.symbol).join(", ")}`);
  }
  return parts.filter(Boolean).join(". ");
}

/** Compact, collapsed-by-default status of every Discovery input. */
export function DiscoverySourcesPanel({ fetchSources = fetchDefault }: DiscoverySourcesPanelProps) {
  const [data, setData] = useState<DiscoverySourcesResponse | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchSources()
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      });
    return () => {
      cancelled = true;
    };
    // fetchSources is a stable default or an injected test double.
  }, []);

  if (error) {
    return <p data-testid="sources-error" className="basket-note basket-note--error">Source status could not be loaded.</p>;
  }
  if (data === null) {
    return <p data-testid="sources-loading" className="basket-note" aria-busy="true">Loading source status...</p>;
  }
  const { text, tone } = summary(data);
  return (
    <details data-testid="sources-panel" className="discovery-sources">
      <summary data-testid="sources-summary">
        <span className={`discovery-dot discovery-dot--${tone}`} data-testid="sources-dot" data-tone={tone} aria-hidden="true" />
        {text}
      </summary>
      <div className="discovery-scroll">
        <table className="discovery-coins" data-testid="sources-table">
          <thead>
            <tr>
              <th scope="col">Source</th>
              <th scope="col" className="basket-table__num">Weight</th>
              <th scope="col">Status</th>
              <th scope="col" className="basket-table__num">Coins</th>
              <th scope="col" className="basket-table__num">Days</th>
              <th scope="col">Newest</th>
              <th scope="col">Note</th>
            </tr>
          </thead>
          <tbody>
            {data.sources.map((r) => (
              <tr key={r.id} data-testid={`sources-row-${r.id}`} className={r.kind === "exchange-member" ? "discovery-sources__sub" : undefined}>
                <td>{r.label}</td>
                <td className="basket-table__num">{r.weight === null ? "—" : r.weight}</td>
                <td>
                  <span className={`discovery-state discovery-state--${r.state}`}>{STATE_TEXT[r.state]}</span>
                </td>
                <td className="basket-table__num">{r.kind === "helper" ? r.coins_with_data : `${r.coins_with_data} / ${r.eligible_size}`}</td>
                <td className="basket-table__num">{r.kind === "helper" ? "—" : r.history_days}</td>
                <td>{r.newest ?? "—"}</td>
                <td className="discovery-muted">{note(r, data)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
