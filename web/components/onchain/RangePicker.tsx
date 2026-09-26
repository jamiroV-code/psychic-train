import { INK, RANGE_OPTIONS, type RangeKey } from "@/lib/onchain-view-model";

/** One range control for the whole page; changing it re-fetches `?start=` (Python rebases). */
export function RangePicker({ value, onChange }: { value: RangeKey; onChange: (r: RangeKey) => void }) {
  return (
    <div role="radiogroup" aria-label="Range" style={{ display: "inline-flex", gap: 4 }}>
      {RANGE_OPTIONS.map((o) => (
        <button
          key={o.key}
          type="button"
          role="radio"
          aria-checked={value === o.key}
          data-testid={`onchain-range-${o.key}`}
          onClick={() => onChange(o.key)}
          style={{ fontWeight: value === o.key ? 700 : 400, color: INK.primary }}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
