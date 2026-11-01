"use client";

import { useId, useState } from "react";
import type { DiscoveryExcludedCoin, DiscoveryExclusionReason } from "@/lib/types/discovery";

/** Short plain words for the coverage line, one per reason. */
export const REASON_LABEL: Record<DiscoveryExclusionReason, string> = {
  stablecoin: "stablecoins",
  "no-market": "tokenized funds / no market",
  "wrapped-staked": "wrapped or staked copies",
  "commodity-backed": "gold or commodity backed tokens",
  "not-tradeable-config": "not tradeable (config)",
  "not-tradeable": "not tradeable (zero trading volume)",
  unassigned: "unassigned",
  "hidden-narrative": "coins in hidden narratives",
  "no-source-data": "no source data",
  watching: "new coins in probation",
  inactive: "coins that left the exit band",
  unclassified: "coins not classified yet",
};

/** One plain sentence per reason, for the expanded list. */
function reasonSentence(reason: string, minCategoryCoins: number): string {
  switch (reason) {
    case "stablecoin":
      return "Stablecoins: their price is pegged, so attention says nothing about them.";
    case "no-market":
      return "Tokenized funds: no exchange market to trade them on.";
    case "wrapped-staked":
      return "Wrapped, staked or bridged copies of another coin.";
    case "commodity-backed":
      return "Gold or commodity backed tokens: their price follows the commodity, so attention says nothing about the token.";
    case "not-tradeable-config":
      return "Marked not tradeable in the config.";
    case "not-tradeable":
      return "No trading market: zero 24h trading volume, or not listed on Binance or Hyperliquid.";
    case "unassigned":
      return "Not in any narrative yet: add them to attention_narratives.json.";
    case "hidden-narrative":
      return `Only in narratives with fewer than ${minCategoryCoins} coins, which are hidden.`;
    case "no-source-data":
      return "In a narrative, but no attention source has data for them yet.";
    case "watching":
      return "New in the top 100: they join after the probation days in a row there.";
    case "inactive":
      return "Outside the exit band for the set number of days: history and names are kept for a return.";
    case "unclassified":
      return "Not classified yet as a normal coin or a pegged or wrapped token: they wait for the owner.";
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
              Coins whose tradeability is unknown stay in: a missing or out-of-date exchange list never excludes a coin.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
