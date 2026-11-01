"use client";

import { Fragment, useEffect, useState } from "react";
import { fetchDiscoverySources as fetchDefault } from "@/lib/api/discovery";
import { formatNarrativeReason } from "@/lib/format-unavailable-reason";
import { sourceHealthLines } from "@/lib/source-health";
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

/** Watch-list file cap (api trends_runs.WATCH_MAX_FILES): a streak this long reads "30+". */
const WATCH_CAP = 30;

/** The Trends row's note gains the keyword coverage and the coins without a keyword (T180), grouped by detail
 * (stage 2): no keyword or no entry yet, waiting for the owner's approval, or an invalid keyword file. */
function note(r: DiscoverySourceRow, d: DiscoverySourcesResponse): string {
  const tk = d.trends_keyword;
  if (r.id !== "trends" || !tk) return r.note;
  const parts = [r.note, `Trends keyword: ${tk.with_keyword} of ${tk.eligible_size} eligible coins`];
  const syms = (details: string[]) => tk.missing.filter((g) => details.includes(g.detail)).map((g) => g.symbol);
  const none = syms(["no-keyword", "no-entry"]);
  if (none.length) parts.push(`${formatNarrativeReason("no-trends-keyword")}: ${none.join(", ")}`);
  const waiting = syms(["skipped-unqualified"]);
  if (waiting.length) parts.push(`Waiting for owner approval: ${waiting.join(", ")}`);
  if (syms(["bad-file"]).length) parts.push("Keyword file invalid");
  return parts.filter(Boolean).join(". ");
}

/** Stage 2 (D-30): coins waking up in the daily pulls, with days held; shown only, never scored. */
function watchText(d: DiscoverySourcesResponse): string | null {
  const w = d.trends_watch;
  if (!w || w.length === 0) return null;
  const items = w.map((x) => {
    const n = x.days_held >= WATCH_CAP ? `${WATCH_CAP}+` : String(x.days_held);
    return `${x.symbol} (${n} ${x.days_held === 1 ? "day" : "days"})`;
  });
  return `Waking up (daily pulls): ${items.join(", ")}`;
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
            {data.sources.map((r) => {
              const health = sourceHealthLines(r);
              const watch = r.id === "trends" ? watchText(data) : null;
              return (
                <Fragment key={r.id}>
                  <tr data-testid={`sources-row-${r.id}`} className={r.kind === "exchange-member" ? "discovery-sources__sub" : undefined}>
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
                  {watch && (
                    <tr data-testid="sources-trends-watch">
                      <td colSpan={7} className="discovery-muted" style={{ whiteSpace: "normal", overflowWrap: "anywhere" }}>{watch}</td>
                    </tr>
                  )}
                  {health && (
                    <tr data-testid={`sources-health-${r.id}`}>
                      {/* One cell over all columns: the lines wrap instead of widening the table on phones. */}
                      <td colSpan={7} className="discovery-muted" style={{ whiteSpace: "normal", overflowWrap: "anywhere" }}>
                        <ul style={{ margin: 0, paddingLeft: "1.25em", maxWidth: "min(100%, 80ch)" }}>
                          {health.map((l) => (
                            <li key={l.key} data-testid={`sources-health-${r.id}-${l.key}`}>{l.text}</li>
                          ))}
                        </ul>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </details>
  );
}
