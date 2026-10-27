"use client";

import { useState } from "react";
import { formatSigned, NO_DATA } from "@/lib/attention-lines";
import type { DiscoveryCategory, DiscoveryCoin, DiscoveryHiddenNarrative, DiscoverySelection } from "@/lib/types/discovery";

export interface DiscoveryTableProps {
  categories: readonly DiscoveryCategory[];
  /** What the history chart currently shows, to highlight it. */
  selection?: DiscoverySelection | null;
  /** Opening a category or clicking a coin selects it for the history chart. */
  onSelect?: (selection: DiscoverySelection) => void;
  /** Fewer coins than this and a category is listed apart, unranked. */
  minCategoryCoins?: number;
  /** A source change at or above this percent counts as rising (and at or below its negative, falling). */
  risingThresholdPct?: number;
  /** Covered weight a coin needs before it can fire a signal. */
  minCoveredWeight?: number;
  /** Universe coins in no narrative. */
  unassigned?: readonly string[];
  /** Narratives with fewer than `minCategoryCoins` member coins: listed, not ranked, no chart. */
  hiddenNarratives?: readonly DiscoveryHiddenNarrative[];
}

const SOURCE_SHORT: Record<string, string> = {
  wikipedia: "Wiki",
  trends: "Trends",
  reddit: "Reddit",
  xsearch: "X",
  exchange_activity: "Exchanges",
  coingecko: "CG volume",
  github_dev: "GitHub",
  defillama: "DeFiLlama",
};

const COLUMN_HELP = {
  score: "The coin's attention change over the window, a weighted mean of its sources, capped at the category's 95th percentile.",
  signal: "Trigger when at least 60% of the weight that has data is rising and enough weight has data.",
  sources: "Each source that has data for this coin, with its own change over the window.",
  coverage: "Weight of the sources that have data for this coin, out of 100.",
};

// The response does not carry the threshold, so the tag names no number.
const THIN_HELP = "low 24h volume: label only, not excluded";
const UNKNOWN_HELP = "no fresh Binance or Hyperliquid list has this coin; kept in";

function formatPercent(value: number | null): string {
  if (value === null) return NO_DATA;
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}%`;
}

function chipTone(change: number, threshold: number): "rising" | "falling" | "flat" {
  if (change >= threshold) return "rising";
  if (change <= -threshold) return "falling";
  return "flat";
}

function CoinRow({ coin, id, selected, onSelect, risingThresholdPct, minCoveredWeight }: {
  coin: DiscoveryCoin;
  id: string;
  selected: boolean;
  onSelect?: (selection: DiscoverySelection) => void;
  risingThresholdPct: number;
  minCoveredWeight: number;
}) {
  const covered = Math.round(coin.covered_weight);
  const lowData = !coin.trigger && coin.covered_weight < minCoveredWeight;
  return (
    <tr className={`discovery-coin${selected ? " is-selected" : ""}`} aria-current={selected ? "true" : undefined}>
      <td>
        <button
          type="button"
          className="basket-coins__symbol basket-coins__pick"
          data-testid={`discovery-coin-${id}-${coin.symbol}`}
          title={`Show ${coin.symbol} history`}
          onClick={() => onSelect?.({ kind: "coin", symbol: coin.symbol })}
        >
          {coin.symbol}
        </button>
      </td>
      <td className="basket-table__num">{formatPercent(coin.change)}</td>
      <td>
        {coin.trigger ? (
          <span className="discovery-pill">Trigger</span>
        ) : lowData ? (
          <span className="discovery-muted" title={`Under ${minCoveredWeight} of 100 weight has data, too little to fire a signal.`}>low data</span>
        ) : (
          <span className="discovery-muted">{"\u2014"}</span>
        )}
        {coin.thin_volume && (
          <span className="discovery-tag" data-testid={`discovery-thin-${id}-${coin.symbol}`} title={THIN_HELP}>
            thin volume<span className="visually-hidden">{`: ${THIN_HELP}`}</span>
          </span>
        )}
        {coin.tradeability === "unverified" && (
          <span className="discovery-tag" data-testid={`discovery-tradeability-unknown-${id}-${coin.symbol}`} title={UNKNOWN_HELP}>
            tradeability unknown<span className="visually-hidden">{`: ${UNKNOWN_HELP}`}</span>
          </span>
        )}
      </td>
      <td>
        <span className="discovery-chips">
          {coin.sources.map((src) => (
            <span
              key={src.source}
              className={`discovery-chip discovery-chip--${chipTone(src.change, risingThresholdPct)}`}
              title={`${SOURCE_SHORT[src.source] ?? src.source}: ${formatPercent(src.change)} over the window, data to ${src.as_of.slice(0, 10)}`}
            >
              {`${SOURCE_SHORT[src.source] ?? src.source} ${formatPercent(src.change)}`}
            </span>
          ))}
        </span>
      </td>
      <td
        className="basket-table__num"
        title={`Sources with data for this coin carry ${covered} of 100 weight; ${minCoveredWeight} are needed to fire a signal.`}
      >
        {`${covered} / 100`}
      </td>
    </tr>
  );
}

/** Ranked by score, nulls last. Four columns; coins sit behind the name. */
export function DiscoveryTable({
  categories,
  selection = null,
  onSelect,
  minCategoryCoins = 3,
  risingThresholdPct = 10,
  minCoveredWeight = 30,
  unassigned = [],
  hiddenNarratives = [],
}: DiscoveryTableProps) {
  const [open, setOpen] = useState<ReadonlySet<string>>(() => new Set());

  const empty = categories.filter((c) => c.coins_used === 0);
  const unranked = categories.filter((c) => c.coins_used > 0 && !c.ranked);
  const ranked = categories.filter((c) => c.coins_used > 0 && c.ranked).sort((a, b) => (b.score ?? -Infinity) - (a.score ?? -Infinity));
  const toggle = (c: DiscoveryCategory) => {
    // Opening a category also selects it for the chart; closing it leaves the chart as it is.
    if (!open.has(c.id)) onSelect?.({ kind: "category", id: c.id, name: c.name });
    setOpen((prev) => {
      const id = c.id;
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const emptyLine = empty.length > 0 && (
    <details data-testid="discovery-empty-categories" className="basket-empty-cats">
      <summary>{`${empty.length} ${empty.length === 1 ? "category" : "categories"} without data`}</summary>
      <p className="basket-note">{empty.map((c) => c.name).join(", ")}</p>
    </details>
  );
  const unrankedGroup = unranked.length > 0 && (
    <section data-testid="discovery-unranked" className="discovery-unranked" aria-label="Too few coins to rank">
      <h3 className="discovery-unranked__title">{`Too few coins to rank (need ${minCategoryCoins})`}</h3>
      <ul className="discovery-unranked__list">
        {unranked.map((c) => (
          <li key={c.id} data-testid={`discovery-unranked-${c.id}`}>
            <span>{c.name}</span>
            <span>{`${c.coins_used} ${c.coins_used === 1 ? "coin" : "coins"}: ${c.coins.map((coin) => coin.symbol).join(", ")}`}</span>
          </li>
        ))}
      </ul>
      <p className="discovery-muted">No history chart for these: a category this small is not a narrative.</p>
    </section>
  );
  const unassignedLine = unassigned.length > 0 && (
    <details data-testid="discovery-unassigned" className="basket-empty-cats">
      <summary>{`${unassigned.length} unassigned ${unassigned.length === 1 ? "coin" : "coins"}`}</summary>
      <p className="basket-note">{unassigned.join(", ")}</p>
      <p className="discovery-muted">Not in any narrative yet: add them to attention_narratives.json.</p>
    </details>
  );
  const hiddenLine = hiddenNarratives.length > 0 && (
    <details data-testid="discovery-hidden" className="basket-empty-cats">
      <summary>{`${hiddenNarratives.length} hidden ${hiddenNarratives.length === 1 ? "narrative" : "narratives"} (fewer than ${minCategoryCoins} coins)`}</summary>
      <ul className="discovery-unranked__list">
        {hiddenNarratives.map((n) => (
          <li key={n.id} data-testid={`discovery-hidden-${n.id}`}>
            {`${n.name}: ${n.coins.length} ${n.coins.length === 1 ? "coin" : "coins"}${n.coins.length > 0 ? ` (${n.coins.join(", ")})` : ""}`}
          </li>
        ))}
      </ul>
    </details>
  );
  if (ranked.length === 0) {
    return (
      <>
        <p data-testid="discovery-none" className="basket-note">No category has enough coins to rank in this window.</p>
        {unrankedGroup}
        {emptyLine}
        {hiddenLine}
        {unassignedLine}
      </>
    );
  }

  return (
    <>
    <table data-testid="discovery-table" className="basket-table">
      <thead>
        <tr>
          <th scope="col">Category</th>
          <th scope="col" className="basket-table__num">Score (%)</th>
          <th scope="col" className="basket-table__num">Median (%)</th>
          <th scope="col" className="basket-table__num">Coins used</th>
        </tr>
      </thead>
      <tbody>
        {ranked.flatMap((c) => {
          const expanded = open.has(c.id);
          const rows = [
            <tr
              key={c.id}
              className={`basket-table__row${selection?.kind === "category" && selection.id === c.id ? " is-selected" : ""}`}
              data-testid={`discovery-row-${c.id}`}
              aria-current={selection?.kind === "category" && selection.id === c.id ? "true" : undefined}
            >
              <td>
                <button type="button" className="basket-table__name" aria-expanded={expanded} onClick={() => toggle(c)}>
                  <span className="basket-table__chev" aria-hidden="true" />
                  {c.name}
                </button>
              </td>
              <td className="basket-table__num">{formatSigned(c.score)}</td>
              <td className="basket-table__num">{formatSigned(c.median)}</td>
              <td className="basket-table__num">{c.coins_used}</td>
            </tr>,
          ];
          if (expanded) {
            rows.push(
              <tr key={`${c.id}-coins`} className="basket-table__coins" data-testid={`discovery-coins-${c.id}`}>
                <td colSpan={4}>
                  <div className="discovery-scroll">
                    <table className="discovery-coins">
                      <thead>
                        <tr>
                          <th scope="col">Coin</th>
                          <th scope="col" className="basket-table__num" title={COLUMN_HELP.score}>Score</th>
                          <th scope="col" title={COLUMN_HELP.signal}>Signal</th>
                          <th scope="col" title={COLUMN_HELP.sources}>Sources</th>
                          <th scope="col" className="basket-table__num" title={COLUMN_HELP.coverage}>Coverage</th>
                        </tr>
                      </thead>
                      <tbody>
                        {c.coins.map((coin) => (
                          <CoinRow
                            key={coin.symbol}
                            coin={coin}
                            id={c.id}
                            selected={selection?.kind === "coin" && selection.symbol === coin.symbol}
                            onSelect={onSelect}
                            risingThresholdPct={risingThresholdPct}
                            minCoveredWeight={minCoveredWeight}
                          />
                        ))}
                      </tbody>
                    </table>
                  </div>
                </td>
              </tr>,
            );
          }
          return rows;
        })}
      </tbody>
    </table>
    {unrankedGroup}
    {emptyLine}
    {hiddenLine}
    {unassignedLine}
    </>
  );
}
