import { INK } from "@/lib/onchain-view-model";
import { formatOnchainReason } from "@/lib/format-unavailable-reason";
import type { ChainGrowth } from "@/lib/types/onchain";

/** A chain with no source: a labelled card, never a chart and never a zero. */
export function UnavailableChainCard({ chain }: { chain: ChainGrowth }) {
  return (
    <section
      data-testid={`onchain-unavailable-${chain.id}`}
      data-reason={chain.unavailable_reason ?? undefined}
      style={{ border: `1px dashed ${INK.baseline}`, borderRadius: 4, padding: "8px 10px" }}
    >
      <strong style={{ color: INK.primary }}>{chain.label}</strong>
      <div style={{ fontSize: 12, color: INK.secondary }}>
        {formatOnchainReason(chain.unavailable_reason ?? "source-unavailable")}
      </div>
    </section>
  );
}
