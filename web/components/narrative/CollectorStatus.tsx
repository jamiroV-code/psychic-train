import {
  accountText, browserText, coverageText, doctorText, isRedditAccount, methodText, queryIdText, redditAccountText,
  reportLines, utc,
} from "@/lib/source-health";
import type {
  DiscoveryAccountHealth, DiscoveryCollectorSource, DiscoveryCollectorStatus, DiscoverySourceHealth,
} from "@/lib/types/discovery";

export interface CollectorStatusProps {
  /** null or undefined: an older API that does not report the collector (shown as unknown, never as running). */
  collector: DiscoveryCollectorStatus | null | undefined;
  /** Reuse sources[xsearch].health; never create another per-account wire list. */
  xHealth?: DiscoverySourceHealth | null;
  /** Reuse sources[reddit].health for the Reddit accounts (their own model); absent while none is configured. */
  redditHealth?: DiscoverySourceHealth | null;
}

const UNKNOWN = "unknown";

const MODE_TEXT: Record<NonNullable<DiscoveryCollectorStatus["mode"]>, string> = {
  standalone: "standalone process",
  in_api: "inside the API",
};

const STOPPED_TEXT: Record<string, string> = {
  stopped_cleanly: "stopped cleanly",
  heartbeat_stale: "no heartbeat for over 90 s",
  process_gone: "process not running",
};

/** Seconds as "N s", "N min", "N h" or "N days" ago; the API computes the age, this only words it. */
function ago(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds)) return UNKNOWN;
  if (seconds < 120) return `${Math.round(seconds)} s ago`;
  if (seconds < 7200) return `${Math.floor(seconds / 60)} min ago`;
  if (seconds < 172800) return `${Math.floor(seconds / 3600)} h ago`;
  return `${Math.floor(seconds / 86400)} days ago`;
}

function headText(c: DiscoveryCollectorStatus | null | undefined): string {
  if (!c) return "Collector: Status unknown (not reported by the API)";
  switch (c.state) {
    case "running": {
      const mode = c.mode ? MODE_TEXT[c.mode] : "mode unknown";
      const code = c.version ? `, code ${c.version}` : "";
      return `Collector: Running (${mode}), since ${utc(c.started_at)}, last heartbeat ${ago(c.age_s)}${code}`;
    }
    case "stopped":
      return `Collector: Stopped (${STOPPED_TEXT[c.reason] ?? "reason unknown"}), last heartbeat ${ago(c.age_s)} at ${utc(c.last_beat)}`;
    case "never_started":
      return "Collector: Not started (no heartbeat yet)";
    default:
      return "Collector: Status unknown (heartbeat file unreadable)";
  }
}

function sourceText(s: DiscoveryCollectorSource): string {
  if (!s.has_state) return `${s.label}: no worker state yet`;
  const paused =
    s.paused === null
      ? "pause unknown"
      : s.paused
        ? `paused: ${s.pause_reason ?? "reason unknown"}${s.pause_until === null ? ", owner action needed" : ` until ${utc(s.pause_until)}`}`
        : "not paused";
  const stale = s.stale === null ? "staleness unknown" : s.stale ? "stale" : "not stale";
  return `${s.label}: last unit ${utc(s.last_unit_at)}; ${paused}; ${stale}; budget used ${s.budget_used ?? UNKNOWN} of ${s.effective_budget ?? UNKNOWN}`;
}

function sizingText(s: DiscoveryCollectorSource): string {
  return `Capacity for ${s.sizing_day ?? UNKNOWN}: ${s.capacity_reads ?? UNKNOWN} reads available, ` +
    `${s.need_reads ?? UNKNOWN} needed; shortfall ${s.shortfall_reads ?? UNKNOWN} reads; ` +
    `older backlog ${s.backlog_reads ?? UNKNOWN} reads`;
}

const LINE = { margin: 0 } as const;
const LIST = { margin: 0, paddingLeft: "1.25em" } as const;

/** Whether the attention collector (X and Reddit) is running, in plain visible text. */
export function CollectorStatus({ collector, xHealth, redditHealth }: CollectorStatusProps) {
  const sources = collector?.sources ?? [];
  const xAccounts = (xHealth?.accounts ?? []).filter((a): a is DiscoveryAccountHealth => !isRedditAccount(a));
  const redditAccounts = (redditHealth?.accounts ?? []).filter(isRedditAccount);
  return (
    <div
      role="status"
      aria-live="polite"
      data-testid="collector-status"
      data-state={collector?.state ?? "unknown"}
      className="basket-note"
      style={{ whiteSpace: "normal", overflowWrap: "anywhere", minWidth: 0, maxWidth: "100%" }}
    >
      <p data-testid="collector-status-head" style={LINE}>{headText(collector)}</p>
      {sources.length > 0 && (
        <ul style={LIST}>
          {sources.map((s) => (
            <li key={s.id} data-testid={`collector-source-${s.id}`}>
              {sourceText(s)}
              {s.methods && s.methods.length > 0 && (
                <ul aria-label={`${s.label} methods`} style={LIST}>
                  {s.methods.map((m) => (
                    <li key={m.method} data-testid={`collector-method-${m.method}`}>{methodText(m)}</li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      )}
      {sources.filter((s) => s.id === "xsearch" && s.has_state).map((s) => (
        <p key={s.id} data-testid="collector-capacity" style={LINE}>{sizingText(s)}</p>
      ))}
      {xHealth ? (
        <>
          {(xHealth.accounts_total !== null || xAccounts.length > 0) && (
            <p data-testid="collector-x-accounts" style={LINE}>
              {`X accounts: ${xHealth.accounts_active ?? UNKNOWN} of ${xHealth.accounts_total ?? UNKNOWN} active`}
            </p>
          )}
          <ul style={LIST}>
            {xAccounts.length === 0 && <li>X accounts: unknown</li>}
            {xAccounts.map((a) => (
              <li key={a.label} data-testid={`collector-account-${a.label}`}>{accountText(a)}</li>
            ))}
          </ul>
          {xHealth.queryids && <p data-testid="collector-queryids" style={LINE}>{queryIdText(xHealth.queryids)}</p>}
          <p style={LINE}>{coverageText(xHealth)}</p>
        </>
      ) : <p style={LINE}>X accounts and coverage: unknown</p>}
      {redditHealth && redditAccounts.length > 0 && (
        <div data-testid="collector-reddit-accounts">
          <p style={LINE}>
            {`Reddit accounts: ${redditHealth.accounts_active ?? UNKNOWN} of ${redditHealth.accounts_total ?? UNKNOWN} active`}
          </p>
          <ul style={LIST}>
            {redditAccounts.map((a) => (
              <li key={a.label} data-testid={`collector-reddit-account-${a.label}`}>{redditAccountText(a)}</li>
            ))}
          </ul>
        </div>
      )}
      {collector?.daily_report && (
        <div data-testid="collector-daily-report">
          {reportLines(collector.daily_report).map((line, i) => (
            <p key={line} style={i === 0 ? LINE : { ...LINE, paddingLeft: "1.25em" }}>{line}</p>
          ))}
        </div>
      )}
      {collector?.doctor && <p data-testid="collector-doctor" style={LINE}>{doctorText(collector.doctor)}</p>}
      {collector?.browser && <p data-testid="collector-browser" style={LINE}>{browserText(collector.browser)}</p>}
    </div>
  );
}
