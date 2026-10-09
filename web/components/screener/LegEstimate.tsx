import {
  ESTIMATE_HEADING,
  ageEstimatePart,
  compositeEstimatePart,
  type EstimatePart,
} from "@/lib/btc-leg-lines";
import type { LegEstimate as LegEstimateData } from "@/lib/types/btc-legs";

export interface LegEstimateProps {
  estimate: LegEstimateData | null;
  /** Shown when there is no estimate at all (no confirmed boundary yet). */
  missingReason?: string;
}

function Part({ part, testId }: { part: EstimatePart; testId: string }) {
  return (
    <div className="leg-estimate__part" data-testid={testId}>
      <p className="leg-estimate__label">
        <span className="leg-estimate__title">{part.title}:</span>{" "}
        {part.label !== null ? (
          <strong data-testid={`${testId}-label`}>{part.label}</strong>
        ) : (
          <span data-testid={`${testId}-na`}>N/A: {part.reason}</span>
        )}
      </p>
      <dl className="leg-estimate__inputs">
        {part.inputs.map((input) => (
          <div key={input.key} data-testid={`${testId}-${input.key}`}>
            <dt>{input.label}</dt>
            <dd>{input.value}</dd>
          </div>
        ))}
      </dl>
      <p className="leg-estimate__rule">Rule: {part.rule}</p>
    </div>
  );
}

/**
 * T38 / S7: the D-14 estimate under the BTC leg chart. Two labels, each
 * beside every number its rule used, never merged into one; the payload
 * carries the rule text, so this component only lays it out.
 */
export function LegEstimate({ estimate, missingReason }: LegEstimateProps) {
  return (
    <section className="leg-estimate" data-testid="leg-estimate" aria-label={ESTIMATE_HEADING}>
      <h3 className="leg-estimate__heading" data-testid="leg-estimate-heading">
        {estimate?.heading ?? ESTIMATE_HEADING}
      </h3>
      {estimate ? (
        <>
          <Part part={ageEstimatePart(estimate.age)} testId="leg-estimate-age" />
          <Part part={compositeEstimatePart(estimate.composite)} testId="leg-estimate-composite" />
        </>
      ) : (
        <p data-testid="leg-estimate-na">N/A: {missingReason ?? "no confirmed boundary, so there is no current leg"}</p>
      )}
    </section>
  );
}
