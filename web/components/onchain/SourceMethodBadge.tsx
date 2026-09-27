import { INK } from "@/lib/onchain-view-model";

/** Per-series source + counting method, as visible text on the panel (AC-2, not hover-only). */
export function SourceMethodBadge({ chainId, source, method }: { chainId: string; source: string; method: string }) {
  return (
    <div data-testid={`onchain-panel-${chainId}-source`} style={{ fontSize: 12, color: INK.secondary }}>
      Source: {source} · Method: {method}
    </div>
  );
}
