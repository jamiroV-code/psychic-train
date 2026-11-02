import { utc } from "@/lib/source-health";
import type { DiscoveryCollectorSource, DiscoveryCollectorStatus } from "@/lib/types/discovery";

export interface CollectorStatusProps {
  /** null or undefined: an older API that does not report the collector (shown as unknown, never as running). */
  collector: DiscoveryCollectorStatus | null | undefined;
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

/** Whether the attention collector (X and Reddit) is running, in plain visible text. */
export function CollectorStatus({ collector }: CollectorStatusProps) {
  const sources = collector?.sources ?? [];
  return (
    <div
      role="status"
      aria-live="polite"
      data-testid="collector-status"
      data-state={collector?.state ?? "unknown"}
      className="basket-note"
      style={{ whiteSpace: "normal", overflowWrap: "anywhere" }}
    >
      <p data-testid="collector-status-head" style={{ margin: 0 }}>{headText(collector)}</p>
      {sources.length > 0 && (
        <ul style={{ margin: 0, paddingLeft: "1.25em" }}>
          {sources.map((s) => (
            <li key={s.id} data-testid={`collector-source-${s.id}`}>{sourceText(s)}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
