"use client";

import type { RegimeComponent, RegimeComposite } from "@/lib/types/regime";
import { formatRegimeStatus } from "@/lib/format-regime-value";

// Display copy for the composite drill-down, restating plan ADR-5 (the rule is
// applied in Python, api/analytics/regime/components.py — not here).
const COVERAGE_RULE =
  "A reproduced value is shown only on dates where the components present carry at least 60% of the " +
  "intended weight; weights are renormalised over the components present. Coverage is shown per date.";

export type DrillDownProps =
  | { kind: "component"; component: RegimeComponent; onClose: () => void }
  | { kind: "composite"; composite: RegimeComposite; onClose: () => void };

function Row({ label, value }: { label: string; value: string }) {
  return (
    <>
      <dt style={{ color: "#8a8f98" }}>{label}</dt>
      <dd style={{ margin: 0 }}>{value}</dd>
    </>
  );
}

function num(v: number | null, digits: number): string {
  return v === null ? "not available" : v.toFixed(digits);
}

/**
 * Inline drill-down, same interaction as the screener's DrillDownView: an
 * inline role="dialog" block with a Close button (one drill-down style in the
 * app). Lists the calculation chain; composite shows agreement stats.
 */
export function DrillDown(props: DrillDownProps) {
  const id = props.kind === "component" ? props.component.id : "composite";
  return (
    <div data-testid={`regime-drilldown-${id}`} role="dialog" aria-label={`${id} drill-down`} style={{ fontSize: 12, padding: "6px 0" }}>
      <button type="button" data-testid="regime-drilldown-close" onClick={props.onClose}>
        Close
      </button>
      <dl style={{ display: "grid", gridTemplateColumns: "max-content 1fr", columnGap: 12, rowGap: 2 }}>
        {props.kind === "component" ? (
          <>
            <Row label="Source" value={props.component.source} />
            <Row label="Transform" value={props.component.transform} />
            <Row label="Frequency" value={props.component.frequency} />
            <Row label="Weight" value={`${Math.round(props.component.weight * 100)}%`} />
            <Row label="Unit" value={props.component.unit} />
            <Row
              label="Status"
              value={formatRegimeStatus(props.component.status, props.component.reason) ?? "ok"}
            />
            <Row label="First date" value={props.component.first_date ?? "none"} />
            <Row label="Last date" value={props.component.last_date ?? "none"} />
            <Row label="Points" value={String(props.component.points.length)} />
            <Row label="Last fetched (UTC)" value={props.component.last_fetched_utc ?? "never cached"} />
            <Row label="Notes" value={props.component.notes.length ? props.component.notes.join(" ") : "none"} />
          </>
        ) : (
          <>
            <Row label="Reproduced" value={props.composite.reproduced.label} />
            <Row label="Normalisation" value={props.composite.reproduced.normalisation} />
            <Row label="Coverage rule" value={COVERAGE_RULE} />
            <Row label="Reproduced points" value={String(props.composite.reproduced.points.length)} />
            <Row label="Published" value={`${props.composite.published.label} — ${props.composite.published.attribution}`} />
            <Row label="Published status" value={props.composite.published.status} />
            <Row label="Published points" value={String(props.composite.published.points.length)} />
            <Row label="Regime label" value="LiqTide's own label, shown only for LiqTide's published line (this app assigns none)" />
            <Row label="Overlap days" value={String(props.composite.agreement.overlap_days)} />
            <Row label="Pearson r" value={num(props.composite.agreement.pearson_r, 3)} />
            <Row label="Mean abs diff" value={num(props.composite.agreement.mean_abs_diff, 2)} />
            <Row label="Full-coverage days" value={String(props.composite.agreement.full_coverage_days)} />
            <Row label="Full-coverage mean abs diff" value={num(props.composite.agreement.full_coverage_mean_abs_diff, 2)} />
          </>
        )}
      </dl>
    </div>
  );
}
