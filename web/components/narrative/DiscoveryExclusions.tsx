"use client";

import { useId, useState } from "react";
import type { DiscoveryExcludedCoin, DiscoveryExclusionReason } from "@/lib/types/discovery";

/** Short plain words for the coverage line, one per reason. */
export const REASON_LABEL: Record<DiscoveryExclusionReason, string> = {
  stablecoin: "stablecoins",
  "no-market": "tokenized funds / no market",
  "wrapped-staked": "wrapped or staked copies",
  "not-tradeable-config": "not tradeable (config)",
  unassigned: "unassigned",
  "hidden-narrative": "coins in hidden narratives",
  "no-source-data": "no source data",
};

/** One plain sentence per reason, for the expanded list. */
function reasonSentence(reason: string, minCategoryCoins: number): string {
  switch (reason) {
    case "stablecoin":
      return "Stablecoins: their price is pegged, so attention says nothing about them.";
    case "no-market":
      return "Tokenized funds and coins with no market on Binance, Coinbase, Kraken or Hyperliquid.";
    case "wrapped-staked":
      return "Wrapped, staked or bridged copies of another coin.";
    case "not-tradeable-config":
      return "Marked not tradeable in the config.";
    case "unassigned":
      return "Not in any narrative yet: add them to attention_narratives.json.";
    case "hidden-narrative":
      return `Only in narratives with fewer than ${minCategoryCoins} coins, which are hidden.`;
    case "no-source-data":
      return "In a narrative, but no attention source has data for them yet.";
    default:
      return `Excluded for the reason "${reason}".`;
  }
}

export function reasonLabel(reason: string): string {
  return REASON_LABEL[reason as DiscoveryExclusionReason] ?? reason;
}

export interface DiscoveryExclusionsProps {
  coins: readonly DiscoveryExcludedCoin[];
  counts: Readonly<Record<string, number>>;
  minCategoryCoins: number;
  /** Some shown coin has an unknown venue list: the footer says how tradeability is checked. */
  tradeabilityUnverified?: boolean;
}

/** A button that expands to the excluded coins, grouped by reason, biggest group first. */
export function DiscoveryExclusions({ coins, counts, minCategoryCoins, tradeabilityUnverified = false }: DiscoveryExclusionsProps) {
  const [open, setOpen] = useState(false);
  const listId = useId();

  const groups = new Map<string, DiscoveryExcludedCoin[]>();
  for (const coin of coins) groups.set(coin.reason, [...(groups.get(coin.reason) ?? []), coin]);
  for (const [reason, n] of Object.entries(counts)) if (n > 0 && !groups.has(reason)) groups.set(reason, []);
  if (groups.size === 0) return null;
  const size = (reason: string) => Math.max(counts[reason] ?? 0, groups.get(reason)?.length ?? 0);
  const ordered = [...groups.keys()].sort((a, b) => size(b) - size(a));

  return (
    <div data-testid="discovery-exclusions" className="discovery-exclusions">
      <button
        type="button"
        className="discovery-exclusions__toggle"
        data-testid="discovery-exclusions-toggle"
        aria-expanded={open}
        aria-controls={listId}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="basket-table__chev" aria-hidden="true" />
        {open ? "Hide excluded coins" : "Show excluded coins"}
      </button>
      {open && (
        <div id={listId} data-testid="discovery-exclusions-list" className="discovery-exclusions__list">
          {ordered.map((reason) => {
            const members = groups.get(reason) ?? [];
            return (
              <section key={reason} data-testid={`discovery-excluded-${reason}`} className="discovery-exclusions__group">
                <h3 className="discovery-unranked__title">{`${size(reason)} ${reasonLabel(reason)}`}</h3>
                <p className="discovery-exclusions__why">{reasonSentence(reason, minCategoryCoins)}</p>
                {members.length > 0 && (
                  <p className="discovery-muted">
                    {members.map((c) => (c.detail && c.detail !== c.reason ? `${c.symbol} (${c.detail})` : c.symbol)).join(", ")}
                  </p>
                )}
              </section>
            );
          })}
          {tradeabilityUnverified && (
            <p className="discovery-muted" data-testid="discovery-exclusions-tradeability">
              Tradeability is checked against exchange lists once they are built; until then no coin is excluded for it.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
