"use client";

import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { InvalidSymbolError, WatchlistFullError } from "@/lib/api/watchlist";
import { CAP_MESSAGE, isFull, MAX_COINS } from "@/lib/layout-state";

export interface AddCoinFormProps {
  /** Coins on the watchlist now. */
  count: number;
  groups: readonly { id: string; name: string }[];
  addCoin: (symbol: string, groupId?: string) => Promise<unknown>;
  onAdded: (symbol: string) => void;
}

/**
 * T41 / S5b: add a coin to the watchlist, into a chosen group (default the
 * last). At the 30-coin cap the button is aria-disabled, the cap message
 * stays on screen and a click sends nothing. Errors go to one alert line;
 * after a successful add focus stays in the cleared input.
 */
export function AddCoinForm({ count, groups, addCoin, onAdded }: AddCoinFormProps) {
  const id = useId();
  const [symbol, setSymbol] = useState("");
  const [groupId, setGroupId] = useState(() => groups.at(-1)?.id ?? "");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const alive = useRef(true);
  const full = isFull(count);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  // A deleted group falls back to the last one.
  const selected = groups.some((g) => g.id === groupId) ? groupId : (groups.at(-1)?.id ?? "");

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (pending || full) return;
    const clean = symbol.trim().toUpperCase();
    if (!clean) {
      setError("Enter a coin symbol.");
      return;
    }
    setError("");
    setPending(true);
    try {
      await addCoin(clean, selected || undefined);
      if (!alive.current) return;
      setSymbol("");
      onAdded(clean);
    } catch (err) {
      if (!alive.current) return;
      if (err instanceof WatchlistFullError) setError(err.message);
      else if (err instanceof InvalidSymbolError) setError(`${clean} is not a valid symbol.`);
      else setError(`Could not add ${clean}: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      if (alive.current) setPending(false);
    }
  };

  const blocked = full || pending;

  return (
    <form className="add-coin" aria-label="Add a coin" data-testid="add-coin-form" onSubmit={submit} noValidate>
      <label htmlFor={`${id}-symbol`}>Coin symbol</label>
      <input
        id={`${id}-symbol`}
        className="board-input"
        data-testid="add-coin-input"
        value={symbol}
        autoComplete="off"
        spellCheck={false}
        maxLength={20}
        onChange={(e) => setSymbol(e.target.value)}
      />
      <label htmlFor={`${id}-group`}>Add to group</label>
      <select
        id={`${id}-group`}
        className="board-select"
        data-testid="add-coin-group"
        value={selected}
        onChange={(e) => setGroupId(e.target.value)}
      >
        {groups.map((g) => (
          <option key={g.id} value={g.id}>
            {g.name}
          </option>
        ))}
      </select>
      <button
        type="submit"
        className="board-button"
        data-testid="add-coin-button"
        aria-disabled={blocked ? "true" : undefined}
        aria-describedby={full ? `${id}-full` : undefined}
      >
        Add coin
      </button>
      <span className="add-coin__count" data-testid="coin-count">
        {count} / {MAX_COINS} coins
      </span>
      {full && (
        <p id={`${id}-full`} className="add-coin__full" data-testid="add-coin-full">
          {CAP_MESSAGE}
        </p>
      )}
      <p role="alert" className="board-alert" data-testid="add-coin-error">
        {error}
      </p>
    </form>
  );
}
