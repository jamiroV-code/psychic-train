import { INK, METRIC_LABELS } from "@/lib/onchain-view-model";
import type { OnchainMetric } from "@/lib/types/onchain";

const METRICS: OnchainMetric[] = ["active_addresses", "transactions"];

export function MetricSelector({ value, onChange }: { value: OnchainMetric; onChange: (m: OnchainMetric) => void }) {
  return (
    <div role="radiogroup" aria-label="Metric" style={{ display: "inline-flex", gap: 4 }}>
      {METRICS.map((m) => (
        <button
          key={m}
          type="button"
          role="radio"
          aria-checked={value === m}
          data-testid={`onchain-metric-${m}`}
          onClick={() => onChange(m)}
          style={{ fontWeight: value === m ? 700 : 400, color: INK.primary }}
        >
          {METRIC_LABELS[m]}
        </button>
      ))}
    </div>
  );
}
