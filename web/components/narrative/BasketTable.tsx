"use client";

import { useState } from "react";
import { BasketCoins } from "@/components/narrative/BasketCoins";
import { formatBreadth, formatScore, formatSigned, NO_DATA } from "@/lib/attention-lines";
import type { BasketAttention } from "@/lib/types/attention";

export interface BasketTableProps {
  baskets: readonly BasketAttention[];
}

/** Ranked by score, nulls last. Five columns; coins sit behind the name. */
export function BasketTable({ baskets }: BasketTableProps) {
  const [open, setOpen] = useState<ReadonlySet<string>>(() => new Set());

  if (baskets.length === 0) {
    return <p data-testid="attention-table-empty" className="basket-note basket-table-empty">No baskets to rank.</p>;
  }

  const ranked = [...baskets].sort((a, b) => (b.score ?? -Infinity) - (a.score ?? -Infinity));
  const toggle = (id: string) =>
    setOpen((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  return (
    <table data-testid="attention-table" className="basket-table">
      <thead>
        <tr>
          <th scope="col">Basket</th>
          <th scope="col" className="basket-table__num">Score</th>
          <th scope="col" className="basket-table__num">Change</th>
          <th scope="col" className="basket-table__num">Breadth</th>
          <th scope="col" className="basket-table__num">Coverage</th>
        </tr>
      </thead>
      <tbody>
        {ranked.flatMap((b) => {
          const expanded = open.has(b.id);
          const rows = [
            <tr key={b.id} data-testid={`attention-row-${b.id}`}>
              <td>
                <button type="button" className="basket-table__name" aria-expanded={expanded} onClick={() => toggle(b.id)}>
                  {b.name}
                </button>
              </td>
              <td className="basket-table__num">{formatScore(b.score)}</td>
              <td className="basket-table__num">{formatSigned(b.change)}</td>
              <td className="basket-table__num">{formatBreadth(b.breadth)}</td>
              <td className="basket-table__num">{b.coverage}</td>
            </tr>,
          ];
          if (expanded) {
            rows.push(
              <tr key={`${b.id}-coins`} className="basket-table__coins" data-testid={`attention-coins-${b.id}`}>
                <td colSpan={5}>
                  <BasketCoins coins={b.coins} />
                </td>
              </tr>,
            );
          }
          return rows;
        })}
      </tbody>
    </table>
  );
}
