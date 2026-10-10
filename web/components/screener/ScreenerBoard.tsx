"use client";

import { useCallback, useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { AddCoinForm } from "@/components/screener/AddCoinForm";
import { CoinGroup, type GroupOption } from "@/components/screener/CoinGroup";
import { DrillDownView } from "@/components/screener/DrillDownView";
import { useLiveData } from "@/components/screener/LiveProvider";
import { SpaghettiChart } from "@/components/screener/SpaghettiChart";
import type { ChartRange } from "@/lib/island-loader";
import { fetchLayout as fetchLayoutDefault, saveLayout as saveLayoutDefault } from "@/lib/api/layout";
import { fetchChartView, fetchScreenerBoard, fetchSpaghetti as fetchSpaghettiDefault } from "@/lib/api/screener";
import { addCoin as addCoinDefault, removeCoin as removeCoinDefault } from "@/lib/api/watchlist";
import {
  addGroup,
  arrange,
  deleteGroup,
  findCoin,
  moveCoin,
  moveCoinToGroup,
  moveGroup,
  renameGroup,
  toggleLine,
} from "@/lib/layout-state";
import { shareStructure, VOLATILE } from "@/lib/same-data";
import type { Layout, LayoutUpdate } from "@/lib/types/layout";
import { useBoardLayout } from "@/lib/use-board-layout";
import {
  TIMEFRAMES,
  type ChartView,
  type ScreenerBoardResponse,
  type SpaghettiResponse,
  type Timeframe,
} from "@/lib/types/screener";

export interface ScreenerBoardProps {
  // Injectable for tests (avoids requiring a real fetch/network layer);
  // defaults to the real API client in the app.
  fetchBoard?: (timeframe: Timeframe) => Promise<ScreenerBoardResponse>;
  fetchChart?: (symbol: string, timeframe: Timeframe) => Promise<ChartView>;
  // T37 / S6: the spaghetti chart below the grid follows the board timeframe.
  fetchSpaghetti?: (timeframe: Timeframe) => Promise<SpaghettiResponse>;
  // T41 / S5b: the saved layout and the watchlist edits.
  fetchLayout?: () => Promise<Layout>;
  saveLayout?: (update: LayoutUpdate) => Promise<Layout>;
  addCoin?: (symbol: string, groupId?: string) => Promise<unknown>;
  removeCoin?: (symbol: string) => Promise<unknown>;
  initialTimeframe?: Timeframe;
}

// T41 / S5b: while a just-added coin has no chart yet, the board is fetched
// again this long after the add (at most twice), then left to the live ticks.
const ADD_RETRY_MS = [4_000, 12_000];

function chartMissing(data: ScreenerBoardResponse, symbol: string): boolean {
  const coin = data.coins.find((c) => c.symbol === symbol);
  return !coin || !coin.chart.available;
}

function errorText(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

export function ScreenerBoard({
  fetchBoard = fetchScreenerBoard,
  fetchChart = fetchChartView,
  fetchSpaghetti = fetchSpaghettiDefault,
  fetchLayout = fetchLayoutDefault,
  saveLayout = saveLayoutDefault,
  addCoin = addCoinDefault,
  removeCoin = removeCoinDefault,
  initialTimeframe = "1d",
}: ScreenerBoardProps) {
  // Amendment 2 (AC-16): ONE global timeframe control lifted here, passed
  // down to every CoinPanel/MiniChart — not an independent per-panel toggle.
  const [timeframe, setTimeframe] = useState<Timeframe>(initialTimeframe);
  const [board, setBoard] = useState<ScreenerBoardResponse | null>(null);
  const [boardSettled, setBoardSettled] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [drillDownSymbol, setDrillDownSymbol] = useState<string | null>(null);
  // T44: one zoom for all the small charts. Zooming or panning any of them
  // sets it, every other one shows it (clamped into its own data). A new
  // timeframe starts at the full range; live data keeps it.
  const [sharedRange, setSharedRange] = useState<ChartRange | null>(null);
  const [rangeTimeframe, setRangeTimeframe] = useState(timeframe);
  if (rangeTimeframe !== timeframe) {
    setRangeTimeframe(timeframe);
    setSharedRange(null);
  }

  // T43 / S11b: every live check (`tick`) refetches the CURRENT timeframe.
  // A coin whose data is the same keeps the same object (structural sharing),
  // so its panel and chart are not touched; a failure keeps the panels and
  // shows the error, the next success clears it. The cancelled flag drops an
  // answer for a timeframe no longer selected.
  const { tick } = useLiveData();

  useEffect(() => {
    let cancelled = false;
    fetchBoard(timeframe)
      .then((data) => {
        if (cancelled) return;
        setBoard((prev) => shareStructure(prev, data, VOLATILE));
        setError(null);
        setBoardSettled(true);
      })
      .catch((err: Error) => {
        if (cancelled) return;
        setError(err.message);
        setBoardSettled(true);
      });
    return () => {
      cancelled = true;
    };
  }, [timeframe, fetchBoard, tick]);

  // T41 / S5b: the layout (groups, order, hidden lines). Order is derived
  // here from the board's coins and the layout, never stored, so a tick
  // that keeps the same coins keeps every object below.
  const { layout, status, notice, saveError, announcement, announce, commit, reload, retry } = useBoardLayout(
    fetchLayout,
    saveLayout,
  );
  const editable = status === "ready";
  const [reloadToken, setReloadToken] = useState(0);
  const [actionError, setActionError] = useState("");

  const symbolsKey = board ? board.coins.map((c) => c.symbol).join(",") : "";
  const layoutGroups = layout?.groups;
  const groups = useMemo(
    () => arrange(layoutGroups ?? [], symbolsKey ? symbolsKey.split(",") : []),
    [layoutGroups, symbolsKey],
  );
  const optionsKey = JSON.stringify(groups.map((g) => [g.id, g.name]));
  const groupOptions = useMemo<GroupOption[]>(
    () => (JSON.parse(optionsKey) as [string, string][]).map(([id, name]) => ({ id, name })),
    [optionsKey],
  );
  const panels = useMemo(() => new Map((board?.coins ?? []).map((c) => [c.symbol, c])), [board]);
  const hiddenLines = editable ? layout?.hidden_lines : undefined;

  // Callbacks below read the latest values from refs, so they stay stable
  // and the memo panels are not re-rendered by a new function.
  const latest = useRef({ groups, hidden: layout?.hidden_lines ?? [], timeframe, fetchBoard, addCoin, removeCoin });
  latest.current = { groups, hidden: layout?.hidden_lines ?? [], timeframe, fetchBoard, addCoin, removeCoin };
  const alive = useRef(true);
  const retryTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // The data-testid to focus after the next render (a moved control, a heading).
  const focusNext = useRef<string | null>(null);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      if (retryTimer.current !== null) clearTimeout(retryTimer.current);
      retryTimer.current = null;
    };
  }, []);

  useEffect(() => {
    const target = focusNext.current;
    if (!target) return;
    focusNext.current = null;
    document.querySelector<HTMLElement>(`[data-testid="${target}"]`)?.focus();
  });

  const refreshBoard = useCallback(async (): Promise<ScreenerBoardResponse | null> => {
    const { timeframe: tf, fetchBoard: fetcher } = latest.current;
    try {
      const data = await fetcher(tf);
      if (!alive.current || latest.current.timeframe !== tf) return null;
      setBoard((prev) => shareStructure(prev, data, VOLATILE));
      setError(null);
      return data;
    } catch (err) {
      if (alive.current && latest.current.timeframe === tf) setError(errorText(err));
      return null;
    }
  }, []);

  const retryUntilCharted = useCallback(
    (symbol: string) => {
      if (retryTimer.current !== null) clearTimeout(retryTimer.current);
      const step = (i: number) => {
        if (i >= ADD_RETRY_MS.length) return;
        const wait = ADD_RETRY_MS[i] - (i > 0 ? ADD_RETRY_MS[i - 1] : 0);
        retryTimer.current = setTimeout(async () => {
          retryTimer.current = null;
          const data = await refreshBoard();
          if (alive.current && (!data || chartMissing(data, symbol))) step(i + 1);
        }, wait);
      };
      step(0);
    },
    [refreshBoard],
  );

  const onMoveCoin = useCallback(
    (symbol: string, delta: -1 | 1) => {
      const { groups: current, hidden } = latest.current;
      const next = moveCoin(current, symbol, delta);
      if (next === current) return;
      commit(next, hidden);
      const at = findCoin(next, symbol);
      if (at) {
        const group = next[at.group];
        announce(
          `${symbol} moved ${delta < 0 ? "earlier" : "later"} in ${group.name}, now ${at.index + 1} of ${group.coins.length}.`,
        );
      }
      focusNext.current = `${delta < 0 ? "move-earlier" : "move-later"}-${symbol}`;
    },
    [commit, announce],
  );

  const onMoveCoinToGroup = useCallback(
    (symbol: string, groupId: string) => {
      const { groups: current, hidden } = latest.current;
      const next = moveCoinToGroup(current, symbol, groupId);
      if (next === current) return;
      commit(next, hidden);
      announce(`${symbol} moved to ${next.find((g) => g.id === groupId)?.name ?? groupId}.`);
      focusNext.current = `move-to-group-${symbol}`;
    },
    [commit, announce],
  );

  const onRemoveCoin = useCallback(
    async (symbol: string) => {
      const { groups: current, removeCoin: remove } = latest.current;
      const at = findCoin(current, symbol);
      const holder = at ? current[at.group] : null;
      setActionError("");
      try {
        await remove(symbol);
      } catch (err) {
        if (alive.current) setActionError(`Could not remove ${symbol}: ${errorText(err)}`);
        return;
      }
      if (!alive.current) return;
      setDrillDownSymbol((open) => (open === symbol ? null : open));
      announce(holder ? `Removed ${symbol} from ${holder.name}.` : `Removed ${symbol}.`);
      if (holder) focusNext.current = `group-heading-${holder.id}`;
      setReloadToken((t) => t + 1);
      reload();
      await refreshBoard();
    },
    [announce, reload, refreshBoard],
  );

  const onAdded = useCallback(
    async (symbol: string) => {
      setActionError("");
      announce(`Added ${symbol}.`);
      setReloadToken((t) => t + 1);
      reload();
      const data = await refreshBoard();
      if (alive.current && data && chartMissing(data, symbol)) retryUntilCharted(symbol);
    },
    [announce, reload, refreshBoard, retryUntilCharted],
  );

  const onRenameGroup = useCallback(
    (groupId: string, name: string): string | null => {
      const { groups: current, hidden } = latest.current;
      const result = renameGroup(current, groupId, name);
      if (!result.ok) return result.error;
      commit(result.groups, hidden);
      announce(`Group renamed to ${name.trim()}.`);
      return null;
    },
    [commit, announce],
  );

  const onMoveGroup = useCallback(
    (groupId: string, delta: -1 | 1) => {
      const { groups: current, hidden } = latest.current;
      const next = moveGroup(current, groupId, delta);
      if (next === current) return;
      commit(next, hidden);
      const index = next.findIndex((g) => g.id === groupId);
      announce(`Group ${next[index].name} moved ${delta < 0 ? "up" : "down"}, now ${index + 1} of ${next.length}.`);
      focusNext.current = `move-group-${delta < 0 ? "up" : "down"}-${groupId}`;
    },
    [commit, announce],
  );

  const onDeleteGroup = useCallback(
    (groupId: string) => {
      const { groups: current, hidden } = latest.current;
      const name = current.find((g) => g.id === groupId)?.name ?? groupId;
      const { groups: next, receiverId } = deleteGroup(current, groupId);
      if (receiverId === null) return;
      commit(next, hidden);
      const receiver = next.find((g) => g.id === receiverId)?.name ?? receiverId;
      announce(`Group ${name} deleted; its coins moved to ${receiver}.`);
      focusNext.current = `group-heading-${receiverId}`;
    },
    [commit, announce],
  );

  const onToggleLine = useCallback(
    (symbol: string) => {
      const { groups: current, hidden } = latest.current;
      commit(current, toggleLine(hidden, symbol));
    },
    [commit],
  );

  // New group: an inline input; Enter saves, Escape cancels.
  const newGroupId = useId();
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [newError, setNewError] = useState("");

  const closeCreate = (focus: string) => {
    setCreating(false);
    setNewName("");
    setNewError("");
    focusNext.current = focus;
  };

  const onNewGroupKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Escape") {
      e.preventDefault();
      closeCreate("new-group-button");
    } else if (e.key === "Enter") {
      e.preventDefault();
      const { groups: current, hidden } = latest.current;
      const result = addGroup(current, newName);
      if (!result.ok) {
        setNewError(result.error);
        return;
      }
      commit(result.groups, hidden);
      announce(`Group ${newName.trim()} created.`);
      closeCreate(`group-heading-${result.id}`);
    }
  };

  const settled = boardSettled && status !== "loading";

  const editBar = (
    <div className="board-edit">
      <AddCoinForm count={board?.coins.length ?? 0} groups={groupOptions} addCoin={addCoin} onAdded={onAdded} />
      <div className="board-edit__groups">
        {creating ? (
          <>
            <label htmlFor={newGroupId}>New group name</label>
            <input
              id={newGroupId}
              className="board-input"
              data-testid="new-group-input"
              value={newName}
              maxLength={60}
              autoFocus
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={onNewGroupKey}
            />
            <span className="coin-group__hint">Enter saves, Escape cancels</span>
            <p role="alert" className="board-alert" data-testid="new-group-error">
              {newError}
            </p>
          </>
        ) : (
          <button
            type="button"
            className="board-button"
            data-testid="new-group-button"
            aria-disabled={editable ? undefined : "true"}
            onClick={() => editable && setCreating(true)}
          >
            New group
          </button>
        )}
      </div>
      <p role="alert" className="board-alert" data-testid="board-action-error">
        {actionError}
      </p>
    </div>
  );

  return (
    <section data-testid="screener-board" aria-label="Screener board">
      <div className="screener-board__toolbar">
        <div role="group" aria-label="Board timeframe" data-testid="timeframe-toggle">
          {TIMEFRAMES.map((tf) => (
            <button
              key={tf}
              type="button"
              data-testid={`timeframe-button-${tf}`}
              aria-pressed={tf === timeframe}
              onClick={() => setTimeframe(tf)}
            >
              {tf}
            </button>
          ))}
        </div>
      </div>

      {/* T41 / S5b: status lines exist from the first render, so nothing shifts. */}
      <div className="board-status">
        <p className="board-notice" data-testid="layout-notice" role="status">
          {notice}
        </p>
        {status === "failed" && (
          <button type="button" className="board-button" data-testid="layout-retry" onClick={retry}>
            Retry loading the layout
          </button>
        )}
        <p className="board-alert" data-testid="layout-save-error" role="alert">
          {saveError}
        </p>
        <p className="visually-hidden" data-testid="board-announcer" aria-live="polite">
          {announcement}
        </p>
      </div>

      {error && <div data-testid="board-error">{error}</div>}

      {!settled ? (
        <div className="board-loading" data-testid="board-loading" aria-busy="true">
          Loading coins and layout
        </div>
      ) : (
        <>
          {board && board.coins.length === 0 && (
            <p className="board-empty" data-testid="board-empty">
              No coins on the watchlist yet. Add one below.
            </p>
          )}
          {board && editBar}
          {board && board.coins.length > 0 && (
            <div className="screener-board__grid" data-testid="screener-board-grid">
              {groups.map((group, position) => (
                <CoinGroup
                  key={group.id}
                  group={group}
                  position={position}
                  total={groups.length}
                  panels={panels}
                  groupOptions={groupOptions}
                  editable={editable}
                  timeframe={board.timeframe}
                  range={sharedRange}
                  onRangeChange={setSharedRange}
                  onOpenDrillDown={setDrillDownSymbol}
                  onMoveCoin={onMoveCoin}
                  onMoveCoinToGroup={onMoveCoinToGroup}
                  onRemoveCoin={onRemoveCoin}
                  onRenameGroup={onRenameGroup}
                  onMoveGroup={onMoveGroup}
                  onDeleteGroup={onDeleteGroup}
                />
              ))}
            </div>
          )}
          <SpaghettiChart
            timeframe={timeframe}
            fetchSpaghetti={fetchSpaghetti}
            hidden={hiddenLines}
            onToggle={editable ? onToggleLine : undefined}
            reloadToken={reloadToken}
          />
        </>
      )}

      {/* On-demand only (AC-7) — never rendered as part of the grid above. */}
      {drillDownSymbol && (
        <DrillDownView
          key={drillDownSymbol}
          symbol={drillDownSymbol}
          onClose={() => setDrillDownSymbol(null)}
          fetchChart={fetchChart}
        />
      )}
    </section>
  );
}
