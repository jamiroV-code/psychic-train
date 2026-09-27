import { INK, limitedHistoryText } from "@/lib/onchain-view-model";
import type { ChainGrowth } from "@/lib/types/onchain";

/** "Limited history" copy for chains flagged in chains.json; the gate date comes from the API. */
export function LimitedHistoryFlag({ chain }: { chain: ChainGrowth }) {
  const text = limitedHistoryText(chain);
  if (text === null) return null;
  return (
    <div
      data-testid={`onchain-panel-${chain.id}-limited-history`}
      role="note"
      style={{ fontSize: 12, color: INK.secondary, borderLeft: `3px solid ${INK.baseline}`, paddingLeft: 6, margin: "2px 0" }}
    >
      {text}
    </div>
  );
}
