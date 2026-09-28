import { INK, STATE_LABELS } from "@/lib/onchain-view-model";
import type { FloorRampState } from "@/lib/types/onchain";

/** Current floor/ramp state, exactly as the API classified it (D3 is applied server-side). */
export function FloorRampStateLabel({ chainId, state }: { chainId: string; state: FloorRampState }) {
  return (
    <span
      data-testid={`onchain-panel-${chainId}-state`}
      data-state={state}
      style={{ fontSize: 12, color: INK.primary, border: `1px solid ${INK.baseline}`, borderRadius: 3, padding: "0 5px", marginLeft: 8 }}
    >
      {STATE_LABELS[state]}
    </span>
  );
}
