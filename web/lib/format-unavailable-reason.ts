import type { UnavailableReason } from "@/lib/types/screener";

/**
 * RFC-006 (reason-value-rendering slice): single shared mapping from the
 * backend's `UnavailableReason` to human-facing copy. Kept in one place so
 * the three render sites (`CoinPanel`, `DrillDownView`,
 * `RelativePerformanceChart`) can't drift from each other — the same
 * discipline `all-context.md`'s "one source of numerical truth" applies to
 * computed numbers, applied here to display copy instead.
 *
 * `context` picks the framing for the `insufficient-history` / `null` case
 * only — `bad-symbol` and `source-unavailable` are structural issues, not a
 * timeframe/window problem, so they never take the suffix.
 *
 * The `insufficient-history` / `null` branch deliberately reproduces the
 * pre-RFC-005 default copy byte-for-byte ("Not enough history at this
 * timeframe") so existing fixtures/tests that don't set `reason` see no
 * change in rendered text.
 */
export function formatUnavailableReason(
  reason: UnavailableReason | null,
  context: "timeframe" | "window"
): string {
  switch (reason) {
    case "bad-symbol":
      return "Symbol configuration issue";
    case "source-unavailable":
      return "Data source unavailable";
    case "insufficient-history":
    case null:
    default:
      return `Not enough history ${context === "timeframe" ? "at this timeframe" : "for this window"}`;
  }
}

/**
 * Narrative dashboard (RFC-5, Stage 0 resolution C1): copy for the open
 * reason codes `GET /api/narrative/history` emits. A sibling of
 * `formatUnavailableReason` rather than new `case` arms there, because that
 * function is typed to the screener's closed `UnavailableReason` union and
 * widening it would touch screener code. Returns null only for a null
 * reason; an unknown code is shown verbatim, never hidden.
 */
const NARRATIVE_REASON_COPY: Record<string, string> = {
  "no-archived-data": "Unavailable — no archived data for this source yet",
  "no-baseline-yet": "Not enough history yet to detect new listings",
  "no-hyperliquid-market": "Not listed on Hyperliquid — no exchange volume for this category",
  "exchange-unavailable": "Exchange data unavailable",
  "zero-total-volume": "Exchange reported zero total volume",
  "empty-market-list": "Exchange returned no markets",
  "credentials-not-configured": "Reddit credentials not configured for the nightly job — source skipped",
  "no-keyword": "No search keyword configured for this category",
  stale: "Stale — showing the last archived data",
  "presumed-dead": "Presumed dead — no fresh data for a long time",
  unavailable: "Unavailable",
  "no-composite-data": "Unranked — no composite data",
  "no-composite-on-as-of": "Unranked — no composite value on the as-of date",
  "no-baseline-in-window": "No change — no composite value 7–9 days earlier to compare against",
};

export function formatNarrativeReason(reason: string | null): string | null {
  if (reason === null) return null;
  const known = NARRATIVE_REASON_COPY[reason];
  if (known) return known;
  const age = /^last-point-(\d+)-days-old$/.exec(reason);
  if (age) return `Stale — last data point is ${age[1]} days old`;
  if (reason.startsWith("fetch-failed:") || reason.startsWith("parse-failed:")) {
    return `Source fetch failed (${reason})`;
  }
  if (reason.startsWith("legacy-map-count")) return "Legacy-map count (BTC/ETH/HYPE only) — excluded from the composite";
  if (reason.startsWith("backfilled history")) return "Backfilled history — 269-day Google window, separate scale";
  return `Unavailable (${reason})`;
}
