import type { DiscoverySourceReason, DiscoverySourceRow } from "@/lib/types/discovery";

/** One visible line of a PC worker source's health block (W8g); the API computes, this only formats. */
export interface HealthLine {
  key: string;
  text: string;
}

const UNKNOWN = "unknown";

const REASON_TEXT: Record<DiscoverySourceReason, string> = {
  "": "none",
  parked: "parked",
  x_live_off: "X live collection off",
  not_probed: "not probed",
  stale: "stale",
  insufficient_history: "short history",
  no_stored_data: "no stored data",
  invalid_file: "invalid file",
};

/** ISO timestamp as "YYYY-MM-DD HH:MM UTC"; unknown when null or unparseable. */
function utc(iso: string | null): string {
  const ms = iso === null ? NaN : Date.parse(iso);
  if (Number.isNaN(ms)) return UNKNOWN;
  return `${new Date(ms).toISOString().slice(0, 16).replace("T", " ")} UTC`;
}

function n(v: number | null): string {
  return v === null || !Number.isFinite(v) ? UNKNOWN : String(v);
}

function missingText(missing: number | null, reasons: Record<string, number> | null): string {
  if (missing === null) return `missing ${UNKNOWN}`;
  if (reasons === null) return missing > 0 ? `missing ${missing} (reasons unknown)` : `missing ${missing}`;
  const list = Object.entries(reasons).map(([k, c]) => `${k} ${c}`).join(", ");
  return list ? `missing ${missing} (${list})` : `missing ${missing}`;
}

function diskText(bytes: number | null): string {
  if (bytes === null || !Number.isFinite(bytes)) return UNKNOWN;
  return `${(bytes / 1024 ** 3).toFixed(1)} GB`;
}

/** The health block lines of a row, or null for a row without worker state (it renders as before). */
export function sourceHealthLines(row: DiscoverySourceRow): HealthLine[] | null {
  const h = row.health;
  if (!h) return null;
  const lines: HealthLine[] = [
    { key: "reason", text: `Reason: ${REASON_TEXT[row.reason ?? ""] ?? row.reason}` },
    { key: "impl", text: `Method: ${row.impl ?? UNKNOWN}` },
    { key: "last_unit", text: `Last unit: ${utc(h.last_unit_at)}` },
    {
      key: "paused",
      text: h.paused
        ? `Paused: ${h.pause_reason ?? "reason unknown"}, ${h.pause_until === null ? "owner action needed" : `until ${utc(h.pause_until)}`}`
        : "Paused: no",
    },
    {
      key: "stale",
      text: h.stale === null ? `Stale: ${UNKNOWN}` : h.stale ? "Stale: yes, no unit for over twice the expected gap" : "Stale: no",
    },
    { key: "today", text: `Today ${h.collection_day}: attempted ${n(h.attempted)}, fetched ${n(h.fetched)}` },
    {
      key: "budget",
      text: `Budget: used ${n(h.budget_used)} of ${n(h.effective_budget)}${h.budget_spent ? ", spent" : ""}`,
    },
    {
      key: "completeness",
      text:
        `Completeness ${h.completeness_day}: ${h.completeness}. ` +
        `Attempted ${n(h.completeness_attempted)}, fetched ${n(h.completeness_fetched)}, ` +
        `${missingText(h.missing, h.missing_reasons)}, capped ${n(h.capped)}, ` +
        (h.newest_age_hours === null ? `newest age ${UNKNOWN}` : `newest ${h.newest_age_hours} h old`),
    },
    { key: "mode", text: `Mode: ${h.mode ?? UNKNOWN}` },
  ];
  if (row.id === "x" || h.accounts_total !== null || h.accounts.length > 0) {
    const per = h.accounts.map(
      (a) =>
        `${a.label} ${a.state}${a.reason ? ` (${a.reason})` : ""}, ` +
        (a.cookie_age_days === null ? `cookie age ${UNKNOWN}` : `cookie ${a.cookie_age_days} days old`),
    );
    const head = `X accounts: ${n(h.accounts_active)} of ${n(h.accounts_total)} active`;
    lines.push({ key: "accounts", text: per.length ? `${head}. ${per.join("; ")}` : head });
  }
  lines.push(
    {
      key: "late",
      text: `One day late: completeness covers ${h.completeness_day}, the last full day; today's counts are still in progress.`,
    },
    { key: "disk", text: `Free disk: ${diskText(h.free_disk_bytes)}` },
  );
  return lines;
}
