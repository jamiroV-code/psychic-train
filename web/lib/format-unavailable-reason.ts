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
