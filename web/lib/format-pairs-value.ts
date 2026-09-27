import type { HalfLife, Johansen, PairSummary } from "@/lib/types/pairs";

/**
 * Display formatting for the /pairs pages (cointegration-screener RFC-004).
 * Formatting, ordering and counting only — every statistic comes from the
 * API and nothing is recomputed here. Mirrors format-regime-value.ts: one
 * module so the table, banner and detail view cannot drift apart.
 */

/** The single significance level used by the banner and the row tag (Stage 0 decision 1). */
export const SIGNIFICANCE_LEVEL = 0.05;

export const NO_VALUE = "—";

export const NOT_MEAN_REVERTING_TEXT = "Not mean-reverting — no half-life";

export const OPTIMISM_NOTE =
  "The table ranks each pair by the better of these two tests. Picking the better of two related " +
  "tests makes the result look slightly more significant than a single test chosen in advance.";

export const RAW_ONLY_TAG = "passes raw, not after correction";

function finite(value: number | null | undefined): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function signed(abs: string, value: number): string {
  return value > 0 ? `+${abs}` : value < 0 ? `−${abs}` : abs;
}

/** p ≥ 0.01 → 3 decimals; 0.0001 ≤ p < 0.01 → 2 significant figures; p < 0.0001 → "< 0.0001". */
export function formatPValue(p: number | null | undefined): string {
  if (!finite(p)) return NO_VALUE;
  if (p >= 0.01) return p.toFixed(3);
  if (p >= 0.0001) return p.toPrecision(2);
  return "< 0.0001";
}

/** Whole days at ≥ 10, one decimal below; explicit text when not mean-reverting. */
export function formatHalfLife(halfLife: HalfLife | null | undefined): string {
  if (!halfLife) return NO_VALUE;
  if (halfLife.state === "not_mean_reverting") return NOT_MEAN_REVERTING_TEXT;
  if (!finite(halfLife.days)) return NO_VALUE;
  return halfLife.days >= 10 ? `${halfLife.days.toFixed(0)} d` : `${halfLife.days.toFixed(1)} d`;
}

/** 2 decimals, signed, U+2212 minus. */
export function formatZScore(z: number | null | undefined): string {
  if (!finite(z)) return NO_VALUE;
  return signed(Math.abs(z).toFixed(2), z);
}

/** Generic fixed-decimal number (hedge ratio, t-stat); U+2212 minus. */
export function formatNumber(value: number | null | undefined, decimals: number): string {
  if (!finite(value)) return NO_VALUE;
  const abs = Math.abs(value).toFixed(decimals);
  return value < 0 ? `−${abs}` : abs;
}

/** "18.31 vs 15.49 — Yes" (the yes/no is the API's boolean, not recomputed). */
export function formatJohansen(j: Johansen | null | undefined): string {
  if (!j || !finite(j.trace_stat) || !finite(j.crit_value_95)) return NO_VALUE;
  return `${j.trace_stat.toFixed(2)} vs ${j.crit_value_95.toFixed(2)} — ${j.rank_at_least_1 ? "Yes" : "No"}`;
}

/** "ETH~BTC" → "ETH on BTC". */
export function formatDirection(direction: string | null | undefined): string {
  if (!direction) return NO_VALUE;
  const [dep, indep] = direction.split("~");
  return indep ? `${dep} on ${indep}` : direction;
}

/** "2021-01-01 → 2026-09-24 (1,820 days)". */
export function formatSampleWindow(start: string | null, end: string | null, overlapDays: number | null): string {
  if (!start || !end) return NO_VALUE;
  const days = finite(overlapDays) ? ` (${overlapDays.toLocaleString("en-US")} days)` : "";
  return `${start} → ${end}${days}`;
}

export function formatOverlapDays(days: number | null | undefined): string {
  return finite(days) ? days.toLocaleString("en-US") : NO_VALUE;
}

export function pairLabel(pair: Pick<PairSummary, "coin_a" | "coin_b">): string {
  return `${pair.coin_a}/${pair.coin_b}`;
}

function byCoins(a: PairSummary, b: PairSummary): number {
  return a.coin_a.localeCompare(b.coin_a) || a.coin_b.localeCompare(b.coin_b);
}

const NON_OK_ORDER: Record<PairSummary["status"], number> = {
  ok: 0,
  insufficient_overlap: 1,
  coin_unavailable: 2,
};

/** A row the BH-sorted group can rank: status ok with a finite corrected p. */
function isRankable(p: PairSummary): boolean {
  return p.status === "ok" && finite(p.eg_p_bh);
}

/**
 * Fixed default order (AC-4): rankable rows ascending by corrected p, ties on
 * raw p then coin names; then a structurally separate group of the rest
 * (insufficient_overlap, then coin_unavailable, alphabetical). The second
 * group never enters the p-value sort. Returns a new array.
 */
export function sortPairs(pairs: readonly PairSummary[]): PairSummary[] {
  const ranked = pairs.filter(isRankable);
  const rest = pairs.filter((p) => !isRankable(p));
  ranked.sort(
    (a, b) =>
      (a.eg_p_bh as number) - (b.eg_p_bh as number) ||
      (finite(a.eg_p_raw) && finite(b.eg_p_raw) ? a.eg_p_raw - b.eg_p_raw : 0) ||
      byCoins(a, b)
  );
  rest.sort((a, b) => NON_OK_ORDER[a.status] - NON_OK_ORDER[b.status] || byCoins(a, b));
  return [...ranked, ...rest];
}

/** Row passes on raw p but not after correction — tagged, never hidden. */
export function isRawOnlySignificant(p: PairSummary): boolean {
  return (
    p.status === "ok" &&
    finite(p.eg_p_raw) &&
    finite(p.eg_p_bh) &&
    p.eg_p_raw < SIGNIFICANCE_LEVEL &&
    p.eg_p_bh >= SIGNIFICANCE_LEVEL
  );
}

/**
 * Significance banner text, counted from API values only. The number of
 * tests is the BH denominator: rows that carry a corrected p.
 */
export function significanceSummary(pairs: readonly PairSummary[]): string {
  const tested = pairs.filter(isRankable);
  if (tested.length === 0) return "No pair has enough data to test.";
  const pct = `${Math.round(SIGNIFICANCE_LEVEL * 100)}%`;
  const significant = tested.filter((p) => (p.eg_p_bh as number) < SIGNIFICANCE_LEVEL).length;
  if (significant > 0) {
    return `${significant} of ${tested.length} pairs are significant after correcting for ${tested.length} tests (${pct} level).`;
  }
  const closest = sortPairs(tested)[0];
  return (
    `No pair is significant after correcting for ${tested.length} tests (${pct} level). ` +
    `Closest: ${pairLabel(closest)}, corrected p ${formatPValue(closest.eg_p_bh)}.`
  );
}
