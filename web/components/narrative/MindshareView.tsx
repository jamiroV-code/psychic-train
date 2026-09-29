import type { NarrativeMindshareResponse, NarrativeMindshareSource } from "@/lib/types/narrative";
import { CATEGORICAL } from "@/lib/chart-palette";

const SOURCE_LABEL: Record<NarrativeMindshareSource, string> = {
  pytrends: "Google Trends",
  coingecko: "CoinGecko trending",
  reddit: "Reddit",
};
const SOURCES: NarrativeMindshareSource[] = ["pytrends", "coingecko", "reddit"];
// The eight validated categorical slots. The UI audit measured the previous
// hand-picked eight at a worst adjacent pair of ΔE 5.1 — for a protanopic
// reader two series were the same colour, on the view whose whole job is
// comparing narratives by colour. See lib/chart-palette.ts.
const PALETTE = CATEGORICAL;

function pct(v: number | null): string {
  return v === null ? "—" : `${(v * 100).toFixed(1)}%`;
}

/**
 * Daily social mindshare (ADR-5): a 100%-stacked bar of each narrative's
 * headline share for the picked day, plus every source's own share so
 * disagreement stays visible. Narrative count drives the layout (6 or 15).
 */
export function MindshareView({
  mindshare,
  onDateChange,
}: {
  mindshare: NarrativeMindshareResponse;
  onDateChange?: (date: string) => void;
}) {
  const included = mindshare.entries.filter((e) => e.mindshare !== null);
  const excluded = mindshare.entries.filter((e) => e.mindshare === null);
  return (
    <section data-testid="narrative-mindshare">
      <h2>Daily mindshare{mindshare.date ? ` — ${mindshare.date}` : ""}</h2>
      <div data-testid="mindshare-proxy-label" role="note" style={{ fontSize: 12, color: "#8a8f98" }}>
        Proxy, not a measurement: share of free attention signals ({SOURCES.map((s) => SOURCE_LABEL[s]).join(", ")})
        among the tracked narratives only.
      </div>
      <label style={{ fontSize: 12 }}>
        Day{" "}
        <select
          data-testid="mindshare-date-picker"
          value={mindshare.date ?? ""}
          disabled={mindshare.available_dates.length === 0}
          onChange={(e) => onDateChange?.(e.target.value)}
        >
          {mindshare.available_dates.length === 0 && <option value="">no archived days</option>}
          {[...mindshare.available_dates].reverse().map((d) => (
            <option key={d} value={d}>{d}</option>
          ))}
        </select>
      </label>
      {mindshare.no_sources_available ? (
        <div data-testid="mindshare-no-sources">No source has data for this day</div>
      ) : (
        <>
          {mindshare.only_one_source && (
            <div data-testid="mindshare-only-one-source" style={{ fontSize: 12, color: "#d29922" }}>
              Only one source ({SOURCE_LABEL[mindshare.sources_present[0]]}) has data this day — not a consensus.
            </div>
          )}
          <div data-testid="mindshare-bar" style={{ display: "flex", height: 18, width: "100%", margin: "6px 0" }}>
            {included.map((e, i) => (
              <div
                key={e.category_id}
                data-testid={`mindshare-segment-${e.category_id}`}
                title={`${e.label}: ${pct(e.mindshare)}`}
                style={{ width: `${(e.mindshare as number) * 100}%`, background: PALETTE[i % PALETTE.length] }}
              />
            ))}
          </div>
          <table style={{ fontSize: 12 }}>
            <thead>
              <tr>
                <th align="left">Narrative</th>
                <th>Mindshare</th>
                {SOURCES.map((s) => <th key={s}>{SOURCE_LABEL[s]}</th>)}
              </tr>
            </thead>
            <tbody>
              {included.map((e) => (
                <tr key={e.category_id} data-testid={`mindshare-row-${e.category_id}`}>
                  <td>{e.label}</td>
                  <td data-testid={`mindshare-value-${e.category_id}`}>{pct(e.mindshare)}</td>
                  {SOURCES.map((s) => <td key={s}>{pct(e.sources[s])}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
      {excluded.map((e) => (
        <div key={e.category_id} data-testid={`mindshare-excluded-${e.category_id}`} style={{ fontSize: 12 }}>
          {e.label}: {e.reason ?? "no data this day"}
        </div>
      ))}
    </section>
  );
}
