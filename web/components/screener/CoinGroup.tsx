"use client";

import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { CoinActions } from "@/components/screener/CoinActions";
import { CoinPanel } from "@/components/screener/CoinPanel";
import type { ChartRange } from "@/lib/island-loader";
import type { LayoutGroup } from "@/lib/types/layout";
import type { CoinPanel as CoinPanelData, Timeframe } from "@/lib/types/screener";

export interface GroupOption {
  id: string;
  name: string;
}

export interface CoinGroupProps {
  group: LayoutGroup;
  /** Place of this group among all of them, and how many there are. */
  position: number;
  total: number;
  panels: ReadonlyMap<string, CoinPanelData>;
  groupOptions: readonly GroupOption[];
  editable: boolean;
  timeframe: Timeframe;
  // T44: the board's shared small-chart zoom, passed through untouched.
  range: ChartRange | null;
  onRangeChange: (range: ChartRange | null) => void;
  onOpenDrillDown: (symbol: string) => void;
  onMoveCoin: (symbol: string, delta: -1 | 1) => void;
  onMoveCoinToGroup: (symbol: string, groupId: string) => void;
  onRemoveCoin: (symbol: string) => void;
  /** Returns an error message, or null when the rename was applied. */
  onRenameGroup: (groupId: string, name: string) => string | null;
  onMoveGroup: (groupId: string, delta: -1 | 1) => void;
  onDeleteGroup: (groupId: string) => void;
}

interface CoinCellProps {
  panel: CoinPanelData;
  index: number;
  size: number;
  group: LayoutGroup;
  groupOptions: readonly GroupOption[];
  editable: boolean;
  timeframe: Timeframe;
  range: ChartRange | null;
  onRangeChange: (range: ChartRange | null) => void;
  onOpenDrillDown: (symbol: string) => void;
  onMoveCoin: (symbol: string, delta: -1 | 1) => void;
  onMoveCoinToGroup: (symbol: string, groupId: string) => void;
  onRemoveCoin: (symbol: string) => void;
}

// The actions element is memoised, so a live tick that keeps this coin's
// data object (S11b structural sharing) leaves the memo CoinPanel alone.
function CoinCell({
  panel,
  index,
  size,
  group,
  groupOptions,
  editable,
  timeframe,
  range,
  onRangeChange,
  onOpenDrillDown,
  onMoveCoin,
  onMoveCoinToGroup,
  onRemoveCoin,
}: CoinCellProps) {
  const symbol = panel.symbol;
  const actions = useMemo(
    () => (
      <CoinActions
        symbol={symbol}
        groupId={group.id}
        groupName={group.name}
        groups={groupOptions}
        isFirst={index === 0}
        isLast={index === size - 1}
        disabled={!editable}
        onMove={(delta) => onMoveCoin(symbol, delta)}
        onMoveToGroup={(id) => onMoveCoinToGroup(symbol, id)}
        onRemove={() => onRemoveCoin(symbol)}
      />
    ),
    [symbol, group.id, group.name, groupOptions, index, size, editable, onMoveCoin, onMoveCoinToGroup, onRemoveCoin],
  );
  return (
    <CoinPanel
      panel={panel}
      onOpenDrillDown={onOpenDrillDown}
      timeframe={timeframe}
      range={range}
      onRangeChange={onRangeChange}
      actions={actions}
    />
  );
}

/**
 * T41 / S5b: one layout group, a section labelled by its heading, with
 * its heading, coin count and group controls, and its coins in a grid. The
 * heading takes focus (tabIndex -1) after a remove or a group delete.
 */
export function CoinGroup({
  group,
  position,
  total,
  panels,
  groupOptions,
  editable,
  timeframe,
  range,
  onRangeChange,
  onOpenDrillDown,
  onMoveCoin,
  onMoveCoinToGroup,
  onRemoveCoin,
  onRenameGroup,
  onMoveGroup,
  onDeleteGroup,
}: CoinGroupProps) {
  const inputId = useId();
  const headingId = `group-heading-${group.id}`;
  const [renaming, setRenaming] = useState(false);
  const [draft, setDraft] = useState("");
  const [renameError, setRenameError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const renameRef = useRef<HTMLButtonElement>(null);
  const backToRename = useRef(false);

  useEffect(() => {
    if (renaming) inputRef.current?.focus();
    else if (backToRename.current) {
      backToRename.current = false;
      renameRef.current?.focus();
    }
  }, [renaming]);

  const close = () => {
    backToRename.current = true;
    setRenaming(false);
    setRenameError("");
  };

  const onRenameKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Escape") {
      e.preventDefault();
      close();
    } else if (e.key === "Enter") {
      e.preventDefault();
      const error = onRenameGroup(group.id, draft);
      if (error) setRenameError(error);
      else close();
    }
  };

  const off = (blocked: boolean) => (!editable || blocked ? "true" : undefined);
  const count = group.coins.length;

  return (
    <section aria-labelledby={headingId} className="coin-group" data-testid={`coin-group-${group.id}`}>
      <div className="coin-group__header">
        <h2 id={headingId} tabIndex={-1} className="coin-group__name" data-testid={headingId}>
          {group.name}
        </h2>
        <span className="coin-group__count" data-testid={`group-count-${group.id}`}>
          {count === 1 ? "1 coin" : `${count} coins`}
        </span>
        <div className="coin-group__controls">
          <button
            type="button"
            ref={renameRef}
            className="board-button"
            data-testid={`rename-group-${group.id}`}
            aria-label={`Rename group ${group.name}`}
            aria-disabled={off(false)}
            onClick={() => {
              if (!editable) return;
              setDraft(group.name);
              setRenameError("");
              setRenaming(true);
            }}
          >
            Rename
          </button>
          <button
            type="button"
            className="board-button"
            data-testid={`move-group-up-${group.id}`}
            aria-label={`Move group ${group.name} up`}
            aria-disabled={off(position === 0)}
            onClick={() => editable && position > 0 && onMoveGroup(group.id, -1)}
          >
            Up
          </button>
          <button
            type="button"
            className="board-button"
            data-testid={`move-group-down-${group.id}`}
            aria-label={`Move group ${group.name} down`}
            aria-disabled={off(position === total - 1)}
            onClick={() => editable && position < total - 1 && onMoveGroup(group.id, 1)}
          >
            Down
          </button>
          <button
            type="button"
            className="board-button"
            data-testid={`delete-group-${group.id}`}
            aria-label={`Delete group ${group.name}`}
            aria-disabled={off(total <= 1)}
            onClick={() => editable && total > 1 && onDeleteGroup(group.id)}
          >
            Delete
          </button>
        </div>
      </div>

      {renaming && (
        <div className="coin-group__rename">
          <label htmlFor={inputId} className="visually-hidden">
            {`New name for group ${group.name}`}
          </label>
          <input
            id={inputId}
            ref={inputRef}
            className="board-input"
            data-testid={`rename-input-${group.id}`}
            value={draft}
            maxLength={60}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onRenameKey}
          />
          <span className="coin-group__hint">Enter saves, Escape cancels</span>
          <p role="alert" className="board-alert" data-testid={`rename-error-${group.id}`}>
            {renameError}
          </p>
        </div>
      )}

      {count === 0 ? (
        <p className="coin-group__empty" data-testid={`group-empty-${group.id}`}>
          No coins in this group yet.
        </p>
      ) : (
        <div className="coin-group__grid">
          {group.coins.map((symbol, index) => {
            const panel = panels.get(symbol);
            if (!panel) return null;
            return (
              <CoinCell
                key={symbol}
                panel={panel}
                index={index}
                size={count}
                group={group}
                groupOptions={groupOptions}
                editable={editable}
                timeframe={timeframe}
                range={range}
                onRangeChange={onRangeChange}
                onOpenDrillDown={onOpenDrillDown}
                onMoveCoin={onMoveCoin}
                onMoveCoinToGroup={onMoveCoinToGroup}
                onRemoveCoin={onRemoveCoin}
              />
            );
          })}
        </div>
      )}
    </section>
  );
}
