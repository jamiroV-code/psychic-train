import { DataQualityCaveat } from "@/components/narrative/DataQualityCaveat";
import { formatNarrativeReason } from "@/lib/format-unavailable-reason";
import { orderByRank } from "@/lib/narrative-view-model";
import type { NarrativeComparison } from "@/lib/types/narrative";

/** Current composite rank per category (ADR-5). Unranked rows show "—" + reason, after ranked rows. */
export function ComparisonView({ comparison, labels }: { comparison: NarrativeComparison; labels: Record<string, string> }) {
  const rows = orderByRank(comparison.entries);
  return (
    <section data-testid="narrative-comparison">
      <h2>Comparison — current attention rank</h2>
      <div style={{ fontSize: 12, color: "#8a8f98" }}>as of {comparison.as_of ?? "no data"}</div>
      <DataQualityCaveat view="comparison" />
      {rows.length === 0 ? (
        <div data-testid="narrative-comparison-empty">No categories to compare yet</div>
      ) : (
        <table style={{ fontSize: 13, borderCollapse: "collapse" }}>
          <thead>
            <tr>
              <th>Rank</th>
              <th>Category</th>
              <th>Composite</th>
              <th>Notes</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((e) => (
              <tr key={e.category_id} data-testid={`narrative-comparison-row-${e.category_id}`} data-rank={e.rank ?? ""}>
                <td>{e.rank ?? "—"}</td>
                <td>{labels[e.category_id] ?? e.category_id}</td>
                <td>{e.value === null ? "—" : e.value.toFixed(2)}</td>
                <td>
                  {e.status !== "ok" && formatNarrativeReason(e.reason ?? "unavailable")}
                  {e.mixed_scale && <span data-testid={`narrative-comparison-mixed-${e.category_id}`}> mixed scale (backfilled pytrends)</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
