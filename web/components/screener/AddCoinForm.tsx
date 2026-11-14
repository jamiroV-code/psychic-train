"use client";

import { useEffect, useId, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { useVariant } from "@/components/screener/VariantProvider";
import { fetchSuggestions, type SuggestFn, type Suggestion } from "@/lib/api/symbols";
import { InvalidSymbolError, WatchlistFullError } from "@/lib/api/watchlist";
import { isFull, MAX_COINS } from "@/lib/layout-state";

export interface AddCoinFormProps {
  /** Coins on the watchlist now. */
  count: number;
  groups: readonly { id: string; name: string }[];
  addCoin: (symbol: string, groupId?: string) => Promise<unknown>;
  onAdded: (symbol: string) => void;
  /** Suggestion source; tests inject a double. */
  suggest?: SuggestFn;
}

/**
 * T41 / S5b: add a coin to the watchlist, into a chosen group (default the
 * last). At the 30-coin cap the button is aria-disabled, the cap message
 * stays on screen and a click sends nothing. Errors go to one alert line;
 * after a successful add focus stays in the cleared input.
 * T47 / S9C: labels, count and cap text name the variant (coin or ticker).
 */
export function AddCoinForm({ count, groups, addCoin, onAdded, suggest = fetchSuggestions }: AddCoinFormProps) {
  const variant = useVariant();
  const id = useId();
  const [symbol, setSymbol] = useState("");
  const [groupId, setGroupId] = useState(() => groups.at(-1)?.id ?? "");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const alive = useRef(true);
  const full = isFull(count);
  const [options, setOptions] = useState<Suggestion[]>([]);
  const [active, setActive] = useState(-1);
  const [open, setOpen] = useState(false);
  const [building, setBuilding] = useState(false);
  const request = useRef<AbortController | null>(null);
  const kind = variant.id === "equities" ? "ticker" : "coin";
  const listId = `${id}-suggestions`;

  /** Every keystroke asks again; an answer for an older keystroke is dropped, never shown. */
  const lookup = (text: string) => {
    request.current?.abort();
    const query = text.trim();
    if (!query) {
      setOptions([]);
      setOpen(false);
      setBuilding(false);
      return;
    }
    const controller = new AbortController();
    request.current = controller;
    suggest(kind, query, controller.signal)
      .then((result) => {
        if (controller.signal.aborted || !alive.current) return;
        setOptions(result.suggestions);
        setBuilding(!result.ready);
        setActive(-1);
        setOpen(true);
      })
      .catch(() => {
        if (controller.signal.aborted || !alive.current) return;
        setOptions([]); // suggestions are a convenience; typing a symbol and adding it still works
        setOpen(false);
      });
  };

  const pick = (choice: Suggestion) => {
    request.current?.abort();
    setSymbol(choice.symbol);
    setOptions([]);
    setOpen(false);
    setActive(-1);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Escape") {
      setOpen(false);
      return;
    }
    if (!open || options.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => (i + 1) % options.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => (i <= 0 ? options.length - 1 : i - 1));
    } else if (e.key === "Enter" && active >= 0) {
      e.preventDefault(); // choose the highlighted suggestion; a second Enter adds it
      pick(options[active]);
    }
  };

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      request.current?.abort();
    };
  }, []);

  // A deleted group falls back to the last one.
  const selected = groups.some((g) => g.id === groupId) ? groupId : (groups.at(-1)?.id ?? "");

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    request.current?.abort();
    setOpen(false);
    if (pending || full) return;
    const clean = symbol.trim().toUpperCase();
    if (!clean) {
      setError(`Enter a ${variant.noun} symbol.`);
      return;
    }
    setError("");
    setPending(true);
    try {
      await addCoin(clean, selected || undefined);
      if (!alive.current) return;
      setSymbol("");
      setOptions([]);
      setOpen(false);
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
    <form className="add-coin" aria-label={`Add a ${variant.noun}`} data-testid="add-coin-form" onSubmit={submit} noValidate>
      <label htmlFor={`${id}-symbol`}>{`${variant.noun[0].toUpperCase()}${variant.noun.slice(1)} symbol`}</label>
      <div className="add-coin__search">
        <input
          id={`${id}-symbol`}
          className="board-input"
          data-testid="add-coin-input"
          value={symbol}
          autoComplete="off"
          spellCheck={false}
          maxLength={20}
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={open && options.length > 0}
          aria-controls={listId}
          aria-activedescendant={active >= 0 ? `${listId}-${active}` : undefined}
          onChange={(e) => {
            setSymbol(e.target.value);
            lookup(e.target.value);
          }}
          onKeyDown={onKeyDown}
          onBlur={() => setOpen(false)}
        />
        {open && (
          <ul id={listId} role="listbox" className="add-coin__suggestions" data-testid="add-coin-suggestions">
            {options.map((o, i) => (
              <li
                key={o.symbol}
                id={`${listId}-${i}`}
                role="option"
                aria-selected={i === active}
                className={i === active ? "add-coin__option add-coin__option--active" : "add-coin__option"}
                data-testid="add-coin-suggestion"
                onMouseDown={(e) => {
                  e.preventDefault(); // keep focus in the input so blur does not close the list first
                  pick(o);
                }}
              >
                <span className="add-coin__option-symbol">{o.symbol}</span>
                <span className="add-coin__option-name">{o.name || "name unknown"}</span>
                {o.venues.length > 0 && <span className="add-coin__option-venues">{o.venues.join(", ")}</span>}
              </li>
            ))}
            {options.length === 0 && (
              <li className="add-coin__option add-coin__option--empty" data-testid="add-coin-no-match">
                {building ? "Still building the symbol list, try again in a minute." : "No match."}
              </li>
            )}
          </ul>
        )}
      </div>
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
        Add {variant.noun}
      </button>
      <span className="add-coin__count" data-testid="coin-count">
        {count} / {MAX_COINS} {variant.nounPlural}
      </span>
      {full && (
        <p id={`${id}-full`} className="add-coin__full" data-testid="add-coin-full">
          {variant.capMessage}
        </p>
      )}
      <p role="alert" className="board-alert" data-testid="add-coin-error">
        {error}
      </p>
    </form>
  );
}
