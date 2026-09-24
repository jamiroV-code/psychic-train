import { DataQualityCaveat } from "@/components/narrative/DataQualityCaveat";
import { formatNarrativeReason } from "@/lib/format-unavailable-reason";
import { orderByRank } from "@/lib/narrative-view-model";
import type { NarrativeChange } from "@/lib/types/narrative";

function formatDelta(d: number): string {
  return `${d > 0 ? "+" : ""}${d.toFixed(2)}`;
}

/** Ranked change in composite over the API's window (ADR-5). Null delta shows "—" + reason, never 0. */
export function ChangeInAttentionView({ change, labels }: { change: NarrativeChange; labels: Record<string, string> }) {
  const rows = orderByRank(change.entries);
  const lo = change.window_days;
  const hi = change.window_days + change.baseline_tolerance_days;
  return (
    <section data-testid="narrative-change">
      <h2>Change in attention — {change.window_days}-day</h2>
      <div style={{ fontSize: 12, color: "#8a8f98" }}>
        as of {change.as_of ?? "no data"}; baseline {lo}–{hi} days earlier
      </div>
      <DataQualityCaveat view="change" />
      {rows.length === 0 ? (
        <div data-testid="narrative-change-empty">No categories to compare yet</div>
      ) : (
        <table style={{ fontSize: 13, borderCollapse: "collapse" }}>
          <thead>
            <tr>
              <th>Rank</th>
              <th>Category</th>
              <th>Change</th>
              <th>Baseline</th>
              <th>Notes</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((e) => (
              <tr key={e.category_id} data-testid={`narrative-change-row-${e.category_id}`} data-rank={e.rank ?? ""}>
                <td>{e.rank ?? "—"}</td>
                <td>{labels[e.category_id] ?? e.category_id}</td>
                <td data-testid={`change-delta-${e.category_id}`}>{e.delta === null ? "—" : formatDelta(e.delta)}</td>
                <td>{e.baseline_date ?? "—"}</td>
                <td>
                  {e.status !== "ok" && formatNarrativeReason(e.reason ?? "unavailable")}
                  {e.mixed_scale && <span data-testid={`narrative-change-mixed-${e.category_id}`}> mixed scale (backfilled pytrends)</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
