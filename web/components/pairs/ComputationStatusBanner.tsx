import type { PairsEnvelope } from "@/lib/types/pairs";

/**
 * Response-level freshness banner shared by the table and the detail view.
 * `fresh` renders nothing; `stale` and `results_unavailable` show the API's
 * `stale_reason` verbatim.
 */
export function ComputationStatusBanner({ envelope }: { envelope: PairsEnvelope }) {
  const reason = envelope.stale_reason ?? "no reason given";
  if (envelope.computation_status === "stale") {
    return (
      <div data-testid="pairs-status-banner" data-status="stale" role="status" style={bannerStyle}>
        These results are out of date: {reason}. Showing the last computed results from{" "}
        {envelope.computed_at ?? "an unknown time"}.
      </div>
    );
  }
  if (envelope.computation_status === "results_unavailable") {
    return (
      <div data-testid="pairs-status-banner" data-status="results_unavailable" role="status" style={bannerStyle}>
        No pair results available: {reason}.
      </div>
    );
  }
  return null;
}

/**
 * Fetch failure notice. An HTTP error (lib/api/pairs.ts prefixes these with
 * "API request failed:") means the API answered — e.g. 404 unknown ticker or
 * 422 self-pair — so it is not reported as unreachable.
 */
export function ApiUnavailableNotice({ error }: { error: string }) {
  const answered = error.startsWith("API request failed:");
  return (
    <div data-testid="pairs-api-error" data-kind={answered ? "http" : "unreachable"} role="alert" style={bannerStyle}>
      {answered
        ? `Pair screener request failed (${error}).`
        : `Pair screener unavailable — could not reach the API (${error}).`}
    </div>
  );
}

const bannerStyle = { border: "1px solid #ff9800", padding: "8px 12px", margin: "8px 0" } as const;
