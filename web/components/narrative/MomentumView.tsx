import type { NarrativeMomentumEntry, NarrativeMomentumResponse } from "@/lib/types/narrative";

const BASIS_LABEL: Record<NarrativeMomentumEntry["momentum_basis"], string> = {
  "pytrends-blended": "Google Trends (blended)",
  composite: "composite",
  insufficient: "—",
};

function arrow(e: NarrativeMomentumEntry): string {
  if (e.direction === null || e.trend === null) return "";
  const a = e.direction === "up" ? "↑" : e.direction === "down" ? "↓" : "→";
  return `${a} ${e.trend}`;
}

function formatChange(d: number): string {
  return `${d > 0 ? "+" : ""}${d.toFixed(2)}`;
}

/**
 * Cross-sectional momentum (ADR-4): narratives ranked against each other on
 * recent change, each with a gaining/slowing arrow and its disclosed basis.
 * Insufficient narratives show an explicit message — never a 0 bar.
 */
export function MomentumView({ momentum }: { momentum: NarrativeMomentumResponse }) {
  const ranked = momentum.entries.filter((e) => e.status === "ok" && e.change !== null);
  const insufficient = momentum.entries.filter((e) => !(e.status === "ok" && e.change !== null));
  const maxAbs = Math.max(0, ...ranked.map((e) => Math.abs(e.change as number))) || 1;
  return (
    <section data-testid="narrative-momentum">
      <h2>Momentum vs the field — {momentum.window_days}-day change</h2>
      <div style={{ fontSize: 12, color: "#8a8f98" }}>
        Ranked on recent change; arrow compares this {momentum.window_days}-day change to the one before it
        ({momentum.acceleration_window_days} days total).
      </div>
      {ranked.length === 0 ? (
        <div data-testid="narrative-momentum-empty">No narrative has enough history for momentum yet</div>
      ) : (
        <ol style={{ listStyle: "none", padding: 0, fontSize: 13 }}>
          {ranked.map((e) => {
            const c = e.change as number;
            return (
              <li key={e.category_id} data-testid={`momentum-row-${e.category_id}`} data-rank={e.rank ?? ""}>
                <span>{e.rank}. {e.label}</span>{" "}
                <span
                  data-testid={`momentum-bar-${e.category_id}`}
                  style={{
                    display: "inline-block",
                    height: 8,
                    width: `${(Math.abs(c) / maxAbs) * 120}px`,
                    background: c >= 0 ? "#3fb950" : "#f85149",
                  }}
                />{" "}
                <span data-testid={`momentum-change-${e.category_id}`}>{formatChange(c)}</span>{" "}
                <span data-testid={`momentum-arrow-${e.category_id}`}>{arrow(e)}</span>{" "}
                <span data-testid={`momentum-basis-${e.category_id}`} style={{ color: "#8a8f98" }}>
                  basis: {BASIS_LABEL[e.momentum_basis]}
                </span>
              </li>
            );
          })}
        </ol>
      )}
      {insufficient.map((e) => (
        <div key={e.category_id} data-testid={`momentum-insufficient-${e.category_id}`} style={{ fontSize: 12 }}>
          {e.label}: {e.reason ?? "not enough history for momentum yet"}
        </div>
      ))}
    </section>
  );
}
