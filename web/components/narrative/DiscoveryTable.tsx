"use client";

import { useState } from "react";
import { formatSigned, NO_DATA } from "@/lib/attention-lines";
import type { DiscoveryCategory, DiscoveryCoin } from "@/lib/types/discovery";

export interface DiscoveryTableProps {
  categories: readonly DiscoveryCategory[];
}

function formatPercent(value: number | null): string {
  if (value === null) return NO_DATA;
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}%`;
}

function coverageText(coin: DiscoveryCoin): string {
  const rising = coin.covered_weight > 0 ? Math.round((coin.rising_weight / coin.covered_weight) * 100) : 0;
  return `covers ${Math.round(coin.covered_weight)}% of weight, ${rising}% rising`;
}

/** Ranked by score, nulls last. Four columns; coins sit behind the name. */
export function DiscoveryTable({ categories }: DiscoveryTableProps) {
  const [open, setOpen] = useState<ReadonlySet<string>>(() => new Set());

  const empty = categories.filter((c) => c.coins_used === 0);
  const ranked = categories.filter((c) => c.coins_used > 0).sort((a, b) => (b.score ?? -Infinity) - (a.score ?? -Infinity));
  const toggle = (id: string) =>
    setOpen((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const emptyLine = empty.length > 0 && (
    <details data-testid="discovery-empty-categories" className="basket-empty-cats">
      <summary>{`${empty.length} ${empty.length === 1 ? "category" : "categories"} without data`}</summary>
      <p className="basket-note">{empty.map((c) => c.name).join(", ")}</p>
    </details>
  );
  if (ranked.length === 0) {
    return (
      <>
        <p data-testid="discovery-none" className="basket-note">No category has attention data in this window.</p>
        {emptyLine}
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
            <tr key={c.id} className="basket-table__row" data-testid={`discovery-row-${c.id}`}>
              <td>
                <button type="button" className="basket-table__name" aria-expanded={expanded} onClick={() => toggle(c.id)}>
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
                  <ul className="basket-coins">
                    {c.coins.map((coin) => (
                      <li key={coin.symbol} className="basket-coins__coin">
                        <p className="basket-coins__head">
                          <span className="basket-coins__symbol">{coin.symbol}</span>
                          <span>{formatPercent(coin.change)}</span>
                          <span className="basket-coins__muted">{coverageText(coin)}</span>
                          {coin.trigger && <span className="basket-coins__trigger">Trigger</span>}
                        </p>
                      </li>
                    ))}
                  </ul>
                </td>
              </tr>,
            );
          }
          return rows;
        })}
      </tbody>
    </table>
    {emptyLine}
    </>
  );
}
