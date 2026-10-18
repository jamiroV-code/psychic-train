"use client";

import { useEffect, useMemo, useState, type KeyboardEvent, type PointerEvent, type ReactNode } from "react";
import {
  fetchCategoryHistory as fetchCategoryHistoryDefault,
  fetchCoinHistory as fetchCoinHistoryDefault,
  fetchDiscoveryPrice as fetchPriceDefault,
} from "@/lib/api/discovery";
import {
  axisTicks,
  coverageBars,
  dayIndexAt,
  fitScale,
  isConstant,
  linePath,
  shapeCategoryChart,
  shapeCoinChart,
  thinDayCount,
  xTickIndices,
  type PanelScale,
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

// Panels are drawn in real pixels (viewBox = measured width), so the 11px text never scales with the chart.
const DEFAULT_W = 640;
const MIN_W = 240;
const LEFT = 46;
const RIGHT = 10;
const PAD = 6;
const FONT = 11;
const AXIS_H = 20;
const H_MAIN = 112;
const H_SIDE = 84;
const H_COVER = 64;
const H_COVER_COMPACT = 40;

const NO_DATA_LINE = "No history to chart for this window yet.";

function formatPrice(v: number): string {
  return Math.abs(v) >= 1 ? v.toLocaleString("en-US", { maximumFractionDigits: 2 }) : v.toPrecision(3);
}

/**
 * Point-in-time history for one coin or one category (T104 W3).
 * Stacked panels on one shared date axis, each with its own y-scale fitted to its data so no line looks flat
 * next to a bigger one. Coin: weighted score (+ stored trigger days), price as percent change since the first
 * day both exist, data coverage bars against the trigger floor. Category: average score, share of coins
 * triggered. One crosshair runs through every panel.
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
  const [plotEl, setPlotEl] = useState<HTMLDivElement | null>(null);
  const [width, setWidth] = useState(DEFAULT_W);
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

  useEffect(() => {
    if (!plotEl) return;
    const measure = () => {
      const w = Math.floor(plotEl.getBoundingClientRect().width);
      if (w > 0) setWidth(Math.max(MIN_W, w));
    };
    measure();
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(measure);
    ro.observe(plotEl);
    return () => ro.disconnect();
  }, [plotEl]);

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
    const W = width;
    const plotW = W - LEFT - RIGHT;
    const x = (i: number) => LEFT + (n === 1 ? plotW / 2 : (i * plotW) / (n - 1));
    const step = n === 1 ? plotW : plotW / (n - 1);
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
      setActive(dayIndexAt(((e.clientX - box.left) / box.width) * W, LEFT, plotW, n));
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
        r.price === null || r.priceChange === null
          ? "price unavailable"
          : `price ${formatPrice(r.price)} (${formatSigned(r.priceChange)}% since first day)`,
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
    const scores = shape.rows.map((r) => r.score);
    const lastPanel = shape.kind === "coin" ? "coverage" : "share";
    const crosshair = (h: number, cy: number | null, color: string) => (
      <>
        <line x1={x(idx)} x2={x(idx)} y1={PAD} y2={PAD + h} stroke="var(--ink-2)" strokeWidth="1" strokeDasharray="2 2" />
        {cy !== null && <circle cx={x(idx)} cy={cy} r="3" fill={color} stroke="var(--sh-0)" strokeWidth="1" />}
      </>
    );
    const xAxis = (h: number) => (
      <g data-testid="history-xaxis">
        {xTickIndices(n).map((i, k, all) => (
          <text
            key={i}
            x={x(i)}
            y={PAD + h + 15}
            fontSize={FONT}
            fill="var(--ink-3)"
            textAnchor={k === 0 ? "start" : k === all.length - 1 ? "end" : "middle"}
          >
            {shape.rows[i].date}
          </text>
        ))}
      </g>
    );
    /** One panel: own scale, its own y labels (max 3), gridlines, zero line; content drawn by the caller. */
    const panel = (
      id: string,
      title: ReactNode,
      h: number,
      scale: PanelScale,
      opts: { includeZero: boolean; fmt?: (v: number, span: number) => string },
      content: (y: (v: number) => number) => ReactNode,
    ) => {
      const y = (v: number) => PAD + ((scale.hi - v) / (scale.hi - scale.lo)) * h;
      const ticks = axisTicks(scale, { height: h, includeZero: opts.includeZero, fmt: opts.fmt });
      const showZero = opts.includeZero && scale.lo < 0 && scale.hi > 0;
      const last = id === lastPanel;
      return (
        <div className="discovery-history__panel" data-testid={`history-panel-${id}`} key={id}>
          <p className="discovery-history__title" data-testid={`history-panel-title-${id}`}>{title}</p>
          <svg
            data-testid={id === "score" ? "history-svg" : undefined}
            width={W}
            height={h + 2 * PAD + (last ? AXIS_H : 0)}
            viewBox={`0 0 ${W} ${h + 2 * PAD + (last ? AXIS_H : 0)}`}
            aria-hidden="true"
            className="discovery-history__svg"
          >
            {ticks.map((t) => (
              <g key={t.label}>
                <line x1={LEFT} x2={W - RIGHT} y1={PAD + t.y} y2={PAD + t.y} stroke="var(--sh-rule)" strokeWidth="0.5" />
                <text x={LEFT - 6} y={PAD + t.y + 4} textAnchor="end" fontSize={FONT} fill="var(--ink-3)">{t.label}</text>
              </g>
            ))}
            {showZero && <line data-testid="history-zero-line" x1={LEFT} x2={W - RIGHT} y1={y(0)} y2={y(0)} stroke="var(--ink-3)" strokeDasharray="4 3" strokeWidth="1" />}
            {content(y)}
            {last && xAxis(h)}
          </svg>
        </div>
      );
    };

    const panels: ReactNode[] = [];
    if (shape.kind === "coin") {
      const triggers = shape.rows.filter((r) => r.trigger).length;
      const sScale = fitScale(scores, { includeZero: true });
      panels.push(
        panel(
          "score",
          <>
            <span className="discovery-history__swatch" style={{ color: "var(--accent)" }} aria-hidden="true">―</span> Weighted score (%)
            {triggers > 0 && (
              <>
                {" "}
                <span className="discovery-history__swatch" style={{ color: "var(--sev-mature)" }} aria-hidden="true">●</span> trigger day
              </>
            )}
          </>,
          H_MAIN,
          sScale,
          { includeZero: true },
          (y) => (
            <>
              {shape.rows.map((r, i) =>
                r.trigger ? <circle key={r.date} data-testid="history-trigger-marker" cx={x(i)} cy={y(r.score)} r="3" fill="var(--sev-mature)" fillOpacity="0.55" stroke="var(--sev-mature)" strokeOpacity="0.9" strokeWidth="1" /> : null,
              )}
              <path data-testid="history-score-line" d={linePath(scores, x, y)} fill="none" stroke="var(--accent)" strokeWidth="2" />
              {crosshair(H_MAIN, y(scores[idx]), "var(--accent)")}
            </>
          ),
        ),
      );
      if (shape.priceAvailable) {
        const changes = shape.rows.map((r) => r.priceChange);
        const pScale = fitScale(changes, { includeZero: true });
        const pc = changes[idx];
        panels.push(
          panel(
            "price",
            <>
              <span className="discovery-history__swatch" style={{ color: "var(--sev-prov)" }} aria-hidden="true">―</span> Price, % change since first common day
            </>,
            H_SIDE,
            pScale,
            { includeZero: true },
            (y) => (
              <>
                <path data-testid="history-price-line" d={linePath(changes, x, y)} fill="none" stroke="var(--sev-prov)" strokeWidth="1.75" />
                {crosshair(H_SIDE, pc === null || pc === undefined ? null : y(pc), "var(--sev-prov)")}
              </>
            ),
          ),
        );
      }
      const bars = coverageBars(shape.rows, shape.floor);
      const compact = isConstant(bars.map((b) => b.value));
      const hc = compact ? H_COVER_COMPACT : H_COVER;
      const barW = Math.max(1, Math.min(step * 0.7, 10));
      const floorLabel = `needs ${Math.round(shape.floor)} to fire`;
      panels.push(
        panel(
          "coverage",
          "Data coverage (weight of sources with data, out of 100)",
          hc,
          { lo: 0, hi: 100, min: 0, max: 100 },
          { includeZero: false, fmt: (v) => String(Math.round(v)) },
          (y) => (
            <g data-testid="history-band">
              {bars.map((b, i) => (
                <rect
                  key={shape.rows[i].date}
                  data-testid={b.muted ? "history-band-bar-muted" : "history-band-bar"}
                  x={x(i) - barW / 2}
                  y={y(b.value)}
                  width={barW}
                  height={Math.max(0, y(0) - y(b.value))}
                  fill={b.muted ? "var(--ink-3)" : "var(--ink-2)"}
                  opacity={b.muted ? 0.35 : 0.85}
                />
              ))}
              <line data-testid="history-band-floor" x1={LEFT} x2={W - RIGHT} y1={y(shape.floor)} y2={y(shape.floor)} stroke="var(--ink-1)" strokeDasharray="4 3" strokeWidth="1" />
              <text x={W - RIGHT - 2} y={y(shape.floor) - 3} textAnchor="end" fontSize={FONT} fill="var(--ink-1)" stroke="var(--sh-0)" strokeWidth="3" paintOrder="stroke">{floorLabel}</text>
              {crosshair(hc, null, "var(--ink-1)")}
            </g>
          ),
        ),
      );
    } else {
      const shares = shape.rows.map((r) => r.sharePct);
      const sScale = fitScale(scores, { includeZero: true });
      const shScale = fitScale(shares, { includeZero: false, clamp: [0, 100] });
      panels.push(
        panel(
          "score",
          <>
            <span className="discovery-history__swatch" style={{ color: "var(--accent)" }} aria-hidden="true">―</span> Average score (%)
          </>,
          H_MAIN,
          sScale,
          { includeZero: true },
          (y) => (
            <>
              <path data-testid="history-score-line" d={linePath(scores, x, y)} fill="none" stroke="var(--accent)" strokeWidth="2" />
              {crosshair(H_MAIN, y(scores[idx]), "var(--accent)")}
            </>
          ),
        ),
        panel(
          "share",
          <>
            <span className="discovery-history__swatch" style={{ color: "var(--sev-mature)" }} aria-hidden="true">―</span> Coins triggered (% of coins used)
          </>,
          H_SIDE,
          shScale,
          { includeZero: false, fmt: (v) => `${Math.round(v)}%` },
          (y) => (
            <>
              <path data-testid="history-share-line" d={linePath(shares, x, y)} fill="none" stroke="var(--sev-mature)" strokeWidth="1.75" />
              {crosshair(H_SIDE, y(shares[idx]), "var(--sev-mature)")}
            </>
          ),
        ),
      );
    }

    body = (
      <>
        <div
          ref={setPlotEl}
          className="discovery-history__plot"
          data-testid="history-plot"
          tabIndex={0}
          role="figure"
          aria-label={`${title} history chart. Arrow keys move between days.`}
          onKeyDown={onKey}
          onPointerMove={onMove}
          onPointerLeave={() => setActive(null)}
        >
          {panels}
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
