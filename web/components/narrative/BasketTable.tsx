"use client";

import { useState } from "react";
import { formatBreadth, formatScore, formatSigned, NO_DATA } from "@/lib/attention-lines";
import type { BasketAttention } from "@/lib/types/attention";

export interface BasketTableProps {
  baskets: readonly BasketAttention[];
}

/** Ranked by score, nulls last. Five columns; coins sit behind the name. */
export function BasketTable({ baskets }: BasketTableProps) {
  const [open, setOpen] = useState<ReadonlySet<string>>(() => new Set());

  if (baskets.length === 0) {
    return <p data-testid="attention-table-empty">No baskets to rank.</p>;
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
    <table data-testid="attention-table">
      <thead>
        <tr>
          <th scope="col">Basket</th>
          <th scope="col">Score</th>
          <th scope="col">Change</th>
          <th scope="col">Breadth</th>
          <th scope="col">Coverage</th>
        </tr>
      </thead>
      <tbody>
        {ranked.flatMap((b) => {
          const expanded = open.has(b.id);
          const rows = [
            <tr key={b.id} data-testid={`attention-row-${b.id}`}>
              <td>
                <button type="button" aria-expanded={expanded} onClick={() => toggle(b.id)}>
                  {b.name}
                </button>
              </td>
              <td>{formatScore(b.score)}</td>
              <td>{formatSigned(b.change)}</td>
              <td>{formatBreadth(b.breadth)}</td>
              <td>{b.coverage}</td>
            </tr>,
          ];
          if (expanded) {
            rows.push(
              <tr key={`${b.id}-coins`} data-testid={`attention-coins-${b.id}`}>
                <td colSpan={5}>
                  {b.coins.length === 0 && <p>{NO_DATA}</p>}
                  {b.coins.map((c) => (
                    <div key={c.symbol}>
                      <span>{c.symbol}</span> <span>{formatScore(c.score)}</span>{" "}
                      <span>{`${c.sources_used} of ${c.sources_total} sources`}</span>
                      <ul>
                        {c.sources.map((s) => (
                          <li key={s.source}>{`${s.source}: ${s.raw === null ? NO_DATA : s.raw}`}</li>
                        ))}
                      </ul>
                    </div>
                  ))}
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
