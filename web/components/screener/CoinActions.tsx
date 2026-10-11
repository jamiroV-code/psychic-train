"use client";

import { useEffect, useRef, useState, type KeyboardEvent, type MouseEvent } from "react";

export interface CoinActionsProps {
  symbol: string;
  groupId: string;
  groupName: string;
  groups: readonly { id: string; name: string }[];
  isFirst: boolean;
  isLast: boolean;
  // The layout could not load: every control is aria-disabled and inert.
  disabled?: boolean;
  onMove: (delta: -1 | 1) => void;
  onMoveToGroup: (groupId: string) => void;
  onRemove: () => void;
}

/**
 * T41 / S5b: one coin's layout controls, in the panel header. Native buttons
 * and a native select; every name says the coin and its group. A control
 * that cannot act stays focusable with aria-disabled="true" and does
 * nothing. Remove asks for an inline Confirm; Escape or Cancel goes back.
 */
export function CoinActions({
  symbol,
  groupId,
  groupName,
  groups,
  isFirst,
  isLast,
  disabled = false,
  onMove,
  onMoveToGroup,
  onRemove,
}: CoinActionsProps) {
  const [confirming, setConfirming] = useState(false);
  const removeRef = useRef<HTMLButtonElement>(null);
  const confirmRef = useRef<HTMLButtonElement>(null);
  // Set when the confirm row closes without removing: focus goes back to Remove.
  const backToRemove = useRef(false);

  useEffect(() => {
    if (confirming) confirmRef.current?.focus();
    else if (backToRemove.current) {
      backToRemove.current = false;
      removeRef.current?.focus();
    }
  }, [confirming]);

  const guard = (off: boolean, act: () => void) => (e: MouseEvent) => {
    e.preventDefault();
    if (!off) act();
  };

  const cancel = () => {
    backToRemove.current = true;
    setConfirming(false);
  };

  const onConfirmKey = (e: KeyboardEvent) => {
    if (e.key === "Escape") {
      e.preventDefault();
      cancel();
    }
  };

  return (
    <div className="coin-actions" data-testid={`coin-actions-${symbol}`}>
      <button
        type="button"
        className="board-button"
        data-testid={`move-earlier-${symbol}`}
        aria-label={`Move ${symbol} earlier in ${groupName}`}
        aria-disabled={disabled || isFirst ? "true" : undefined}
        onClick={guard(disabled || isFirst, () => onMove(-1))}
      >
        Earlier
      </button>
      <button
        type="button"
        className="board-button"
        data-testid={`move-later-${symbol}`}
        aria-label={`Move ${symbol} later in ${groupName}`}
        aria-disabled={disabled || isLast ? "true" : undefined}
        onClick={guard(disabled || isLast, () => onMove(1))}
      >
        Later
      </button>
      <label className="visually-hidden" htmlFor={`move-to-group-${symbol}`}>
        {`Move ${symbol} from ${groupName} to group`}
      </label>
      <select
        id={`move-to-group-${symbol}`}
        className="board-select"
        data-testid={`move-to-group-${symbol}`}
        value={groupId}
        aria-disabled={disabled ? "true" : undefined}
        onChange={(e) => {
          if (!disabled && e.target.value !== groupId) onMoveToGroup(e.target.value);
        }}
      >
        {groups.map((g) => (
          <option key={g.id} value={g.id}>
            {g.name}
          </option>
        ))}
      </select>
      {confirming ? (
        <span className="coin-actions__confirm">
          <button
            type="button"
            className="board-button"
            data-testid={`confirm-remove-${symbol}`}
            aria-label={`Confirm removing ${symbol} from ${groupName}`}
            ref={confirmRef}
            onKeyDown={onConfirmKey}
            onClick={() => {
              setConfirming(false);
              onRemove();
            }}
          >
            Confirm
          </button>
          <button
            type="button"
            className="board-button"
            data-testid={`cancel-remove-${symbol}`}
            aria-label={`Cancel removing ${symbol}`}
            onKeyDown={onConfirmKey}
            onClick={cancel}
          >
            Cancel
          </button>
        </span>
      ) : (
        <button
          type="button"
          className="board-button"
          ref={removeRef}
          data-testid={`remove-${symbol}`}
          aria-label={`Remove ${symbol} from ${groupName}`}
          aria-disabled={disabled ? "true" : undefined}
          onClick={guard(disabled, () => setConfirming(true))}
        >
          Remove
        </button>
      )}
    </div>
  );
}
