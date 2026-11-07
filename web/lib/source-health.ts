import type {
  DiscoveryAccountHealth, DiscoveryBrowserHealth, DiscoveryDailyReportStatus, DiscoveryDoctorStatus,
  DiscoveryQueryIdHealth, DiscoveryRedditAccountHealth, DiscoveryRedditMethodHealth, DiscoverySourceHealth,
  DiscoverySourceReason, DiscoverySourceRow,
} from "@/lib/types/discovery";

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

/** ISO timestamp as "YYYY-MM-DD HH:MM UTC"; unknown when null or unparseable. Shared with the collector box. */
export function utc(iso: string | null): string {
  const ms = iso === null ? NaN : Date.parse(iso);
  if (Number.isNaN(ms)) return UNKNOWN;
  return `${new Date(ms).toISOString().slice(0, 16).replace("T", " ")} UTC`;
}

function n(v: number | null | undefined): string {
  return v == null || !Number.isFinite(v) ? UNKNOWN : String(v);
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

const PROXY_STATES: Record<string, true> = { direct: true, unknown: true, healthy: true, quarantined: true, blocked: true };
const PROXY_REASONS: Record<string, true> = {
  proxy_config: true, proxy_private: true, proxy_assignment: true, proxy_policy: true, proxy_address: true,
  proxy_transport: true, proxy_timeout: true, proxy_redirect: true, proxy_response: true, proxy_exit: true,
  proxy_region: true, proxy_feed: true, proxy_baseline: true, proxy_budget: true, proxy_quarantine: true,
  proxy_revision: true, proxy_lock: true,
};

function proxyText(a: DiscoveryAccountHealth): string {
  const state = a.proxy_state && Object.prototype.hasOwnProperty.call(PROXY_STATES, a.proxy_state) ? a.proxy_state : UNKNOWN;
  const reason = a.proxy_reason && Object.prototype.hasOwnProperty.call(PROXY_REASONS, a.proxy_reason) ? ` (${a.proxy_reason})` : "";
  const region = a.region && /^[A-Z]{2}(?:-[A-Z0-9]{1,3})?$/.test(a.region) ? a.region : UNKNOWN;
  const style = a.connection_style === "plain" || a.connection_style === "curl" ? a.connection_style : UNKNOWN;
  return `proxy ${state}${reason}, proxy checked ${utc(a.proxy_checked_at ?? null)}, ` +
    `quarantine until ${utc(a.proxy_quarantine_until ?? null)}, region ${region}, connection style ${style}`;
}

/** Closed-code lookup: a code outside the table (a newer or malformed API value) reads unknown, never healthy. */
function word(table: Record<string, string>, code: string | null | undefined): string {
  return code != null && Object.prototype.hasOwnProperty.call(table, code) ? table[code] : UNKNOWN;
}

const ENDPOINT_TEXT: Record<string, string> = { ok: "ok", restricted: "restricted" };
const HARVEST_TEXT: Record<string, string> = {
  none: "none", ok: "ok", needs_owner: "needs owner", refused: "refused", failed: "failed",
};

/** S-StatusAPI X fields; each group appears only when the API sends it, so the default-off line is unchanged. */
function xFinishText(a: DiscoveryAccountHealth): string {
  const parts: string[] = [];
  if (a.endpoint_state !== undefined) parts.push(`endpoint ${word(ENDPOINT_TEXT, a.endpoint_state)}`);
  const b = a.behaviour;
  if (b) {
    parts.push(`quiet until ${utc(b.quiet_until)}, cooldown until ${utc(b.cooldown_until)}` +
      `${b.cooldown_reason ? ` (${b.cooldown_reason})` : ""}, warmup stage ${n(b.warmup_stage)}, ` +
      `effective cap ${n(b.effective_cap)}, mixed calls today ${n(b.mixed_calls_today)}`);
  }
  const hv = a.harvest;
  if (hv) {
    parts.push(`cookie harvest ${word(HARVEST_TEXT, hv.state)}${hv.reason ? ` (${hv.reason})` : ""}` +
      (hv.last_at ? ` at ${utc(hv.last_at)}` : ""));
  }
  if (a.ct0_rotations_seen !== undefined) parts.push(`ct0 rotations seen ${n(a.ct0_rotations_seen)}`);
  return parts.map((p) => `, ${p}`).join("");
}

export function accountText(a: DiscoveryAccountHealth): string {
  const ready = a.ready == null ? UNKNOWN : a.ready ? "yes" : "no";
  return `${a.label} ${a.state}${a.reason ? ` (${a.reason})` : ""}, ` +
    (a.cookie_age_days == null ? `cookie age ${UNKNOWN}` : `cookie ${a.cookie_age_days} days old`) +
    `, reads today ${n(a.reads_today)} / ${a.cap == null ? "no limit" : n(a.cap)}` +
    `, rest until ${utc(a.rest_until ?? null)}, ready ${ready}, last used ${utc(a.last_used)}` +
    `, parse strikes ${n(a.parse_strikes)}, last strike ${utc(a.parse_strike_last_at ?? null)}, ${proxyText(a)}` +
    xFinishText(a);
}

/** The API tags Reddit accounts with `site: "reddit"`; X accounts carry no site. */
export function isRedditAccount(
  a: DiscoveryAccountHealth | DiscoveryRedditAccountHealth,
): a is DiscoveryRedditAccountHealth {
  return "site" in a && a.site === "reddit";
}

const REDDIT_ACCOUNT_STATES: Record<string, string> = {
  active: "active", resting: "resting", paused: "paused", locked: "locked",
};

export function redditAccountText(a: DiscoveryRedditAccountHealth): string {
  const state = word(REDDIT_ACCOUNT_STATES, a.state);
  const ready = a.ready == null ? UNKNOWN : a.ready ? "yes" : "no";
  return `${a.label} ${state === UNKNOWN ? "state unknown" : state}${a.reason ? ` (${a.reason})` : ""}` +
    `, reads today ${n(a.reads_today)} / ${a.cap == null ? "no limit" : n(a.cap)}` +
    `, rest until ${utc(a.rest_until)}, ready ${ready}` +
    `, session ${a.session_state ?? UNKNOWN} (checked ${utc(a.session_checked_at)})` +
    `, proxy ${a.proxy_state && Object.prototype.hasOwnProperty.call(PROXY_STATES, a.proxy_state) ? a.proxy_state : UNKNOWN}`;
}

const METHOD_STATES: Record<string, string> = {
  ok: "ok", degraded: "degraded", needs_probe: "needs probe", disabled: "off", blocked: "blocked", stale: "stale",
};

function share(v: number | undefined): string {
  return v == null || !Number.isFinite(v) ? UNKNOWN : `${Math.round(v * 100)}%`;
}

export function methodText(m: DiscoveryRedditMethodHealth): string {
  const lanes = m.lanes
    ? `lanes posts ${share(m.lanes.posts)}, comments ${share(m.lanes.comments)}` +
      (m.comments_scope === "threads_opened" ? " (threads opened only)" : "")
    : `lanes ${UNKNOWN}`;
  return `${m.label}: ${word(METHOD_STATES, m.state)}${m.reason ? ` (${m.reason})` : ""}` +
    `, last settled ${m.last_settled_day ?? UNKNOWN}, ${lanes}, requests today ${n(m.requests_today)} of ${n(m.cap)}`;
}

const QUERYID_STATES: Record<string, string> = {
  ok: "ok", candidate: "candidate pending", stale: "stale", blocked: "blocked", refused_by_policy: "refused by policy",
};

export function queryIdText(q: DiscoveryQueryIdHealth): string {
  return `Query ids (${q.mode}): ${word(QUERYID_STATES, q.state)}, source ${q.active_source ?? UNKNOWN}` +
    `, active for ${n(q.active_age_days)} days, last check ${utc(q.last_check ?? null)}`;
}

const DOCTOR_STATES: Record<string, string> = { PASS: "pass", WARN: "warnings", FAIL: "failing" };

export function doctorText(d: DiscoveryDoctorStatus): string {
  return `Doctor: ${word(DOCTOR_STATES, d.state)}, checked ${utc(d.checked_at)}` +
    `, ${n(d.failures)} failures, ${n(d.warnings)} warnings`;
}

/** Head line plus one line per source/method; absent counts are unknown, never zero. */
export function reportLines(r: DiscoveryDailyReportStatus): string[] {
  const counts = r.per_source_method;
  const verdict = counts == null ? "counts unknown"
    : r.complete == null ? "completeness unknown" : r.complete ? "complete" : "incomplete";
  const head = `Daily report ${r.day} (revision ${n(r.revision)}): ${verdict}`;
  return [head, ...Object.entries(counts ?? {}).map(([key, c]) =>
    `${key}: eligible ${c.eligible}, stored ${c.stored}, exact ${c.exact}, estimated ${c.estimated}, ` +
    missingText(c.missing, c.reasons))];
}

const PROFILE_STATES: Record<string, string> = { ok: "ok", missing: "missing", policy_unsatisfied: "policy not satisfied" };

export function browserText(b: DiscoveryBrowserHealth): string {
  const refused = b.relay_refusals.map((r) => `${r.host} ${r.count}`).join(", ") || "none";
  return `Browser profile: ${word(PROFILE_STATES, b.profile_state)}; relay refused ${refused}`;
}

/** Only sums/differences of the API's target-day counts, never today's counts or a reconstructed queue. */
export function coverageText(h: DiscoverySourceHealth): string {
  const fetched = h.completeness_fetched;
  const eligible = fetched == null || h.missing == null ? null : fetched + h.missing;
  const exact = fetched == null || h.capped == null ? null : fetched - h.capped;
  return `Coverage ${h.completeness_day}: eligible ${n(eligible)}, stored ${n(fetched)}, ` +
    `exact ${n(exact)}, estimated ${n(h.capped)}, ${missingText(h.missing, h.missing_reasons)}`;
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
        ? h.pause_reason === "layout_changed"
          ? "Stopped: layout_changed, owner action needed"
          : `Paused: ${h.pause_reason ?? "reason unknown"}, ${h.pause_until === null ? "owner action needed" : `until ${utc(h.pause_until)}`}`
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
  const redditAccounts = h.accounts.filter(isRedditAccount);
  const xAccounts = h.accounts.filter((a): a is DiscoveryAccountHealth => !isRedditAccount(a));
  if (row.id === "xsearch" || h.accounts_total !== null || h.accounts.length > 0) {
    const reddit = row.id === "reddit" || redditAccounts.length > 0;
    const per = reddit ? redditAccounts.map(redditAccountText) : xAccounts.map(accountText);
    const head = `${reddit ? "Reddit" : "X"} accounts: ${n(h.accounts_active)} of ${n(h.accounts_total)} active`;
    lines.push({ key: "accounts", text: per.length ? `${head}. ${per.join("; ")}` : head });
    lines.push({ key: "coverage", text: coverageText(h) });
  }
  if (h.queryids) lines.push({ key: "queryids", text: queryIdText(h.queryids) });
  for (const m of h.methods ?? []) lines.push({ key: `method-${m.method}`, text: methodText(m) });
  lines.push(
    {
      key: "late",
      text: `One day late: completeness covers ${h.completeness_day}, the last full day; today's counts are still in progress.`,
    },
    { key: "disk", text: `Free disk: ${diskText(h.free_disk_bytes)}` },
  );
  return lines;
}
