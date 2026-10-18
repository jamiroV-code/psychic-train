"use client";

import { useEffect, useMemo, useState, type KeyboardEvent, type PointerEvent } from "react";
import {
  fetchCategoryHistory as fetchCategoryHistoryDefault,
  fetchCoinHistory as fetchCoinHistoryDefault,
  fetchDiscoveryPrice as fetchPriceDefault,
} from "@/lib/api/discovery";
import {
  bandPoints,
  linePath,
  shapeCategoryChart,
  shapeCoinChart,
  thinDayCount,
  valueDomain,
} from "@/lib/discovery-chart";
import { formatSigned } from "@/lib/attention-lines";
import type {
  DiscoveryCategoryHistory,
  DiscoveryCoinHistory,
  DiscoveryPrice,
  DiscoverySelection,
  DiscoveryWindow,
} from "@/lib/types/discovery";

export interface DiscoveryHistoryChartProps {
  selection: DiscoverySelection;
  /** Shared with the table's selector; a change refetches. */
  window: DiscoveryWindow;
  /** Max covered weight today, for the honest one-liner. */
  liveWeight: number;
  onClose: () => void;
  fetchCoinHistory?: (symbol: string, window: DiscoveryWindow) => Promise<DiscoveryCoinHistory>;
  fetchCategoryHistory?: (id: string, window: DiscoveryWindow) => Promise<DiscoveryCategoryHistory>;
  fetchPrice?: (symbol: string, window: DiscoveryWindow) => Promise<DiscoveryPrice>;
}

type Loaded =
  | { kind: "coin"; history: DiscoveryCoinHistory; price: DiscoveryPrice | null }
  | { kind: "category"; history: DiscoveryCategoryHistory };

const W = 640;
const LEFT = 52;
const RIGHT = 12;
const MAIN_TOP = 8;
const MAIN_H = 176;
const STRIP_TOP = 198;
const STRIP_H = 40;
const AXIS_Y = 256;
const H = 266;
const PLOT_W = W - LEFT - RIGHT;

const NO_DATA_LINE = "No history to chart for this window yet.";

function formatPrice(v: number): string {
  return Math.abs(v) >= 1 ? v.toLocaleString("en-US", { maximumFractionDigits: 2 }) : v.toPrecision(3);
}

/**
 * Point-in-time history for one coin or one category (T104 W3).
 * Coin: weighted score line, price as percent change since the first day both exist (same unit and axis as
 * the score, so the two lines compare directly), stored trigger days as markers, covered weight as a 0-100 band
 * with the floor. Category: average score, plus the share of coins triggered as a second line.
 */
export function DiscoveryHistoryChart({
  selection,
  window,
  liveWeight,
  onClose,
  fetchCoinHistory = fetchCoinHistoryDefault,
  fetchCategoryHistory = fetchCategoryHistoryDefault,
  fetchPrice = fetchPriceDefault,
}: DiscoveryHistoryChartProps) {
  const [attempt, setAttempt] = useState(0);
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [active, setActive] = useState<number | null>(null);
  const subject = selection.kind === "coin" ? selection.symbol : selection.id;

  useEffect(() => {
    let cancelled = false;
    setLoaded(null);
    setError(null);
    setActive(null);
    const request: Promise<Loaded> =
      selection.kind === "coin"
        ? Promise.all([
            fetchCoinHistory(selection.symbol, window),
            // The price is a bonus: a failed request reads as "price unavailable", not as a chart error.
            fetchPrice(selection.symbol, window).catch(() => null),
          ]).then(([history, price]) => ({ kind: "coin", history, price }))
        : fetchCategoryHistory(selection.id, window).then((history) => ({ kind: "category", history }));
    request
      .then((l) => {
        if (!cancelled) setLoaded(l);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      cancelled = true;
    };
    // fetchers are stable defaults or injected test doubles.
  }, [selection.kind, subject, window, attempt]);

  const shape = useMemo(() => {
    if (!loaded) return null;
    if (loaded.kind === "coin") return { kind: "coin" as const, ...shapeCoinChart(loaded.history, loaded.price), price: loaded.price };
    return { kind: "category" as const, ...shapeCategoryChart(loaded.history) };
  }, [loaded]);

  const title = selection.kind === "coin" ? selection.symbol : selection.name;
  const n = shape?.rows.length ?? 0;
  const idx = n === 0 ? 0 : Math.min(active ?? n - 1, n - 1);

  const head = (
    <header className="basket-chart__head">
      <h3 className="basket-chart__title" data-testid="history-title">{`${title} history, ${window}d`}</h3>
      <button type="button" className="board-button" data-testid="history-close" onClick={onClose}>
        Close chart
      </button>
    </header>
  );

  let body;
  if (error !== null) {
    body = (
      <div data-testid="history-error" role="alert">
        <p className="basket-note basket-note--error">History could not be loaded.</p>
        <button type="button" className="board-button" data-testid="history-retry" onClick={() => setAttempt((a) => a + 1)}>
          Retry
        </button>
      </div>
    );
  } else if (shape === null) {
    body = (
      <p data-testid="history-loading" className="basket-note" aria-busy="true">
        Loading history...
      </p>
    );
  } else if (n === 0) {
    body = (
      <p data-testid="history-nodata" className="basket-note">
        {NO_DATA_LINE}
      </p>
    );
  } else {
    const x = (i: number) => LEFT + (n === 1 ? PLOT_W / 2 : (i * PLOT_W) / (n - 1));
    const scores = shape.rows.map((r) => r.score);
    const changes = shape.kind === "coin" ? shape.rows.map((r) => r.priceChange) : [];
    const [lo, hi] = valueDomain([...scores, ...changes]);
    const pad = (hi - lo) * 0.08;
    const yMain = (v: number) => MAIN_TOP + MAIN_H - ((v - (lo - pad)) / (hi - lo + 2 * pad)) * MAIN_H;
    const yStrip = (pct: number) => STRIP_TOP + STRIP_H - (pct / 100) * STRIP_H;
    const step = n === 1 ? PLOT_W : PLOT_W / (n - 1);
    const barW = Math.max(1, Math.min(step * 0.8, 24));
    const ticks = Array.from(new Set([lo, 0, hi]));
    const onKey = (e: KeyboardEvent) => {
      const moves: Record<string, number> = { ArrowLeft: Math.max(0, idx - 1), ArrowRight: Math.min(n - 1, idx + 1), Home: 0, End: n - 1 };
      if (e.key in moves) {
        e.preventDefault();
        setActive(moves[e.key]);
      }
    };
    const onMove = (e: PointerEvent<HTMLDivElement>) => {
      const box = e.currentTarget.getBoundingClientRect();
      if (box.width <= 0) return;
      const px = ((e.clientX - box.left) / box.width) * W;
      setActive(Math.min(n - 1, Math.max(0, Math.round(((px - LEFT) / PLOT_W) * (n - 1)))));
    };

    let readout: string;
    if (shape.kind === "coin") {
      const r = shape.rows[idx];
      readout = [
        r.date,
        `score ${formatSigned(r.score)}%`,
        `covered ${Math.round(r.covered)} of 100${r.thin ? " (thin)" : ""}`,
        `rising ${Math.round(r.rising)}`,
        r.trigger ? "trigger" : "no trigger",
        r.price === null ? "price unavailable" : `price ${formatPrice(r.price)}`,
      ].join(" · ");
    } else {
      const r = shape.rows[idx];
      readout = [
        r.date,
        `avg score ${formatSigned(r.score)}%`,
        `coins used ${r.coinsUsed}`,
        `triggered ${r.triggered} of ${r.coinsUsed} (${Math.round(r.sharePct)}%)`,
      ].join(" · ");
    }

    const thin = shape.kind === "coin" ? thinDayCount(shape.rows) : 0;
    body = (
      <>
        <ul className="plot-legend basket-legend" aria-label="Legend" data-testid="history-legend">
          <li><span className="legend-glyph" style={{ color: "var(--accent)" }} aria-hidden="true">―</span> {shape.kind === "coin" ? "Score (weighted, %)" : "Average score (%)"}</li>
          {shape.kind === "coin" ? (
            <>
              <li><span className="legend-glyph" style={{ color: "var(--sev-prov)" }} aria-hidden="true">―</span> Price (% since first day)</li>
              <li><span className="legend-glyph" style={{ color: "var(--sev-mature)" }} aria-hidden="true">●</span> Trigger day</li>
              <li><span className="legend-glyph" style={{ color: "var(--ink-3)" }} aria-hidden="true">▮</span> Covered weight (0-100), dashed = min {Math.round(shape.floor)}</li>
            </>
          ) : (
            <li><span className="legend-glyph" style={{ color: "var(--sev-mature)" }} aria-hidden="true">―</span> Coins triggered (% of coins used)</li>
          )}
        </ul>
        <div
          className="discovery-history__plot"
          data-testid="history-plot"
          tabIndex={0}
          role="figure"
          aria-label={`${title} history chart. Arrow keys move between days.`}
          onKeyDown={onKey}
          onPointerMove={onMove}
          onPointerLeave={() => setActive(null)}
        >
          <svg data-testid="history-svg" viewBox={`0 0 ${W} ${H}`} role="img" aria-hidden="true" className="discovery-history__svg">
            {ticks.map((t) => (
              <g key={t}>
                <line x1={LEFT} x2={W - RIGHT} y1={yMain(t)} y2={yMain(t)} stroke="var(--sh-rule)" strokeDasharray={t === 0 ? "4 3" : undefined} strokeWidth={t === 0 ? 1 : 0.5} />
                <text x={LEFT - 6} y={yMain(t) + 3} textAnchor="end" fontSize="12" fill="var(--ink-3)">{`${t > 0 ? "+" : ""}${t.toFixed(0)}%`}</text>
              </g>
            ))}
            {shape.kind === "coin" && shape.priceAvailable && (
              <path data-testid="history-price-line" d={linePath(shape.rows.map((r) => r.priceChange), x, yMain)} fill="none" stroke="var(--sev-prov)" strokeWidth="1.5" />
            )}
            <path data-testid="history-score-line" d={linePath(scores, x, yMain)} fill="none" stroke="var(--accent)" strokeWidth="2" />
            {shape.kind === "coin" &&
              shape.rows.map((r, i) =>
                r.trigger ? <circle key={r.date} data-testid="history-trigger-marker" cx={x(i)} cy={yMain(r.score)} r="4" fill="var(--sev-mature)" stroke="var(--sh-0)" strokeWidth="1" /> : null,
              )}
            <line x1={x(idx)} x2={x(idx)} y1={MAIN_TOP} y2={STRIP_TOP + STRIP_H} stroke="var(--ink-2)" strokeWidth="1" strokeDasharray="2 2" />
            {shape.kind === "coin" ? (
              <g data-testid="history-band">
                {bandPoints(shape.rows).map((v, i) => (
                  <rect key={shape.rows[i].date} x={x(i) - barW / 2} y={yStrip(v)} width={barW} height={STRIP_TOP + STRIP_H - yStrip(v)} fill={shape.rows[i].thin ? "var(--sev-prov)" : "var(--ink-3)"} opacity="0.55" />
                ))}
                <line data-testid="history-band-floor" x1={LEFT} x2={W - RIGHT} y1={yStrip(shape.floor)} y2={yStrip(shape.floor)} stroke="var(--ink-2)" strokeDasharray="4 3" strokeWidth="1" />
                <text x={LEFT - 6} y={STRIP_TOP + 8} textAnchor="end" fontSize="12" fill="var(--ink-3)">100</text>
                <text x={LEFT - 6} y={STRIP_TOP + STRIP_H} textAnchor="end" fontSize="12" fill="var(--ink-3)">0</text>
              </g>
            ) : (
              <g>
                <line x1={LEFT} x2={W - RIGHT} y1={STRIP_TOP + STRIP_H} y2={STRIP_TOP + STRIP_H} stroke="var(--sh-rule)" />
                <path data-testid="history-share-line" d={linePath(shape.rows.map((r) => r.sharePct), x, yStrip)} fill="none" stroke="var(--sev-mature)" strokeWidth="1.5" />
                <text x={LEFT - 6} y={STRIP_TOP + 8} textAnchor="end" fontSize="12" fill="var(--ink-3)">100%</text>
                <text x={LEFT - 6} y={STRIP_TOP + STRIP_H} textAnchor="end" fontSize="12" fill="var(--ink-3)">0%</text>
              </g>
            )}
            <circle cx={x(idx)} cy={yMain(scores[idx])} r="3" fill="var(--ink-1)" />
            <text x={LEFT} y={AXIS_Y} fontSize="12" fill="var(--ink-3)">{shape.rows[0].date}</text>
            <text x={W - RIGHT} y={AXIS_Y} textAnchor="end" fontSize="12" fill="var(--ink-3)">{shape.rows[n - 1].date}</text>
          </svg>
        </div>
        <p className="basket-note" data-testid="history-readout" role="status" aria-live="polite">
          {readout}
        </p>
        {shape.kind === "coin" && (
          <p className="basket-note" data-testid="history-weight-note">
            {`Live weight today: ${Math.round(liveWeight)} of 100.`}
            {thin > 0 && ` Early days have little history: ${thin} of ${n} days cover under ${Math.round(shape.floor)} of 100, so those scores are thin and cannot trigger.`}
          </p>
        )}
        {shape.kind === "coin" && !shape.priceAvailable && (
          <p className="basket-note" data-testid="history-price-unavailable">
            Price unavailable for this coin in this window.
          </p>
        )}
        {shape.kind === "coin" && shape.priceAvailable && shape.priceBase && (
          <p className="basket-note" data-testid="history-price-base">
            {`Price is shown as percent change since ${shape.priceBase.date}, the first day with both a score and a price.`}
          </p>
        )}
      </>
    );
  }

  return (
    <section data-testid="discovery-history" aria-label={`${title} history`} className="basket-chart discovery-history">
      {head}
      {body}
    </section>
  );
}
