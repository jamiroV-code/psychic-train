import { RedistributionBadge } from "@/components/narrative/RedistributionBadge";
import { INK, formatSignedPct } from "@/lib/onchain-view-model";
import type { CrossCheck } from "@/lib/types/onchain";

/** L2BEAT divergence: display-only text, never a plotted series. */
export function CrossCheckNote({ chainId, check }: { chainId: string; check: CrossCheck | null }) {
  if (check === null || check.latest_common_date === null) return null;
  const median = check.median_abs_divergence_pct_90d;
  return (
    <div data-testid={`onchain-panel-${chainId}-crosscheck`} style={{ fontSize: 12, color: INK.secondary }}>
      Cross-check vs {check.source.toUpperCase()} (display only): {formatSignedPct(check.latest_divergence_pct)} on{" "}
      {check.latest_common_date}; 90-day median gap {median === null ? "—" : `${median.toFixed(2)}%`}
      <RedistributionBadge redistributable={check.redistributable} testId={`onchain-panel-${chainId}-crosscheck-redistribution`} />
    </div>
  );
}
