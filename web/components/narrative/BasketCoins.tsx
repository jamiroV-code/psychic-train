import { formatCompact, formatScore, NO_DATA, sourceLabel } from "@/lib/attention-lines";
import type { CoinAttention } from "@/lib/types/attention";

export interface BasketCoinsProps {
  coins: readonly CoinAttention[];
}

/** One basket's coins: score, "n of N sources", raw value per source, state mark when not ok. */
export function BasketCoins({ coins }: BasketCoinsProps) {
  if (coins.length === 0) {
    return (
      <p data-testid="basket-coins-empty" className="basket-coins__none">
        {NO_DATA}
      </p>
    );
  }
  return (
    <ul className="basket-coins">
      {coins.map((c) => (
        <li key={c.symbol} className="basket-coins__coin">
          <p className="basket-coins__head">
            <span className="basket-coins__symbol">{c.symbol}</span>
            <span>{formatScore(c.score)}</span>
            <span className="basket-coins__muted">{`${c.sources_used} of ${c.sources_total} sources`}</span>
          </p>
          <ul className="basket-coins__sources">
            {c.sources.map((s) => (
              <li key={s.source} data-testid={`coin-source-${c.symbol}-${s.source}`}>
                <span>{sourceLabel(s.source)}</span>
                <span className={s.raw === null ? "basket-coins__muted" : undefined}>{formatCompact(s.raw)}</span>
                <span className="basket-coins__muted">{s.state === "ok" ? "" : s.state.replace(/-/g, " ")}</span>
              </li>
            ))}
          </ul>
        </li>
      ))}
    </ul>
  );
}
