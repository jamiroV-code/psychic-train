import type { LayoutGroup } from "@/lib/types/layout";

/**
 * T41 / S5b: pure edits of the screener layout's groups. Every function
 * returns new arrays and never mutates its input; a no-op returns the input
 * itself, so a caller can tell nothing changed. Membership stays in the
 * watchlist: `arrange` fits a stored grouping to the coins the board has,
 * the same way the server reconciles it (api/data/layout.py).
 */

export const MAX_COINS = 30;
export const MAX_GROUPS = 12;
export const MAX_GROUP_NAME = 40;
export const DEFAULT_GROUP: Readonly<LayoutGroup> = { id: "main", name: "Main", coins: [] };
export const CAP_MESSAGE = "Screener is full: 30 coins maximum. Remove a coin to add another.";

export type GroupEdit = { ok: true; groups: LayoutGroup[]; id: string } | { ok: false; error: string };

/** Lower-case id, unique among the groups, valid for the server's id rule. */
export function nextGroupId(taken: ReadonlySet<string>): string {
  let n = 1;
  while (taken.has(`group-${n}`)) n += 1;
  return `group-${n}`;
}

export function arrange(groups: readonly LayoutGroup[], symbols: readonly string[]): LayoutGroup[] {
  const members = new Set(symbols);
  const placed = new Set<string>();
  const out = groups.map((group) => {
    const coins: string[] = [];
    for (const coin of group.coins) {
      if (members.has(coin) && !placed.has(coin)) {
        coins.push(coin);
        placed.add(coin);
      }
    }
    return { id: group.id, name: group.name, coins };
  });
  if (out.length === 0) out.push({ ...DEFAULT_GROUP, coins: [] });
  out[out.length - 1].coins.push(...symbols.filter((s) => !placed.has(s)));
  return out;
}

export function findCoin(groups: readonly LayoutGroup[], symbol: string): { group: number; index: number } | null {
  for (let group = 0; group < groups.length; group += 1) {
    const index = groups[group].coins.indexOf(symbol);
    if (index >= 0) return { group, index };
  }
  return null;
}

export function moveCoin(groups: readonly LayoutGroup[], symbol: string, delta: -1 | 1): LayoutGroup[] {
  const at = findCoin(groups, symbol);
  if (!at) return groups as LayoutGroup[];
  const coins = groups[at.group].coins;
  const to = at.index + delta;
  if (to < 0 || to >= coins.length) return groups as LayoutGroup[];
  const next = [...coins];
  [next[at.index], next[to]] = [next[to], next[at.index]];
  return groups.map((g, i) => (i === at.group ? { ...g, coins: next } : g));
}

export function moveCoinToGroup(groups: readonly LayoutGroup[], symbol: string, groupId: string): LayoutGroup[] {
  const at = findCoin(groups, symbol);
  const target = groups.findIndex((g) => g.id === groupId);
  if (!at || target < 0 || at.group === target) return groups as LayoutGroup[];
  return groups.map((g, i) => {
    if (i === at.group) return { ...g, coins: g.coins.filter((c) => c !== symbol) };
    if (i === target) return { ...g, coins: [...g.coins, symbol] };
    return g;
  });
}

/** An error message for a group name, or null when it may be used. */
export function validateGroupName(groups: readonly LayoutGroup[], name: string, exceptId?: string): string | null {
  const trimmed = name.trim();
  if (trimmed.length === 0) return "Enter a group name.";
  if (trimmed.length > MAX_GROUP_NAME) return `Group names are 1-${MAX_GROUP_NAME} characters.`;
  const folded = trimmed.toLowerCase();
  if (groups.some((g) => g.id !== exceptId && g.name.trim().toLowerCase() === folded)) {
    return "A group with that name already exists.";
  }
  return null;
}

export function addGroup(
  groups: readonly LayoutGroup[],
  name: string,
  makeId: (taken: ReadonlySet<string>) => string = nextGroupId,
): GroupEdit {
  if (groups.length >= MAX_GROUPS) return { ok: false, error: `At most ${MAX_GROUPS} groups.` };
  const error = validateGroupName(groups, name);
  if (error) return { ok: false, error };
  const id = makeId(new Set(groups.map((g) => g.id)));
  return { ok: true, id, groups: [...groups, { id, name: name.trim(), coins: [] }] };
}

export function renameGroup(groups: readonly LayoutGroup[], id: string, name: string): GroupEdit {
  const error = validateGroupName(groups, name, id);
  if (error) return { ok: false, error };
  return { ok: true, id, groups: groups.map((g) => (g.id === id ? { ...g, name: name.trim() } : g)) };
}

/** Its coins go to the previous group (the next one when it is first); the last group stays. */
export function deleteGroup(groups: readonly LayoutGroup[], id: string): { groups: LayoutGroup[]; receiverId: string | null } {
  const at = groups.findIndex((g) => g.id === id);
  if (at < 0 || groups.length <= 1) return { groups: groups as LayoutGroup[], receiverId: null };
  const receiver = at === 0 ? 1 : at - 1;
  const moved = groups[at].coins;
  const next = groups
    .map((g, i) => (i === receiver ? { ...g, coins: [...g.coins, ...moved] } : g))
    .filter((_, i) => i !== at);
  return { groups: next, receiverId: groups[receiver].id };
}

export function moveGroup(groups: readonly LayoutGroup[], id: string, delta: -1 | 1): LayoutGroup[] {
  const at = groups.findIndex((g) => g.id === id);
  const to = at + delta;
  if (at < 0 || to < 0 || to >= groups.length) return groups as LayoutGroup[];
  const next = [...groups];
  [next[at], next[to]] = [next[to], next[at]];
  return next;
}

export type SortKey = "name" | "change" | "rsi";

/**
 * AC-8: one-shot sort of one group's coins. "name" is A to Z; "change" and
 * "rsi" are high to low from `values`. A missing, null or non-finite value
 * is never read as 0: those coins go last. Ties (and the missing block) are
 * ordered by symbol, so the result does not depend on the current order.
 */
export function sortGroup(
  groups: readonly LayoutGroup[],
  groupId: string,
  key: SortKey,
  values: ReadonlyMap<string, number | null>,
): LayoutGroup[] {
  const at = groups.findIndex((g) => g.id === groupId);
  if (at < 0) return groups as LayoutGroup[];
  const bySymbol = (a: string, b: string) => (a < b ? -1 : a > b ? 1 : 0);
  const valueOf = (s: string): number | null => {
    const v = values.get(s);
    return typeof v === "number" && Number.isFinite(v) ? v : null;
  };
  const coins = [...groups[at].coins].sort((a, b) => {
    if (key === "name") return bySymbol(a, b);
    const va = valueOf(a);
    const vb = valueOf(b);
    if (va === null || vb === null) {
      if (va !== vb) return va === null ? 1 : -1;
      return bySymbol(a, b);
    }
    return vb - va || bySymbol(a, b);
  });
  if (coins.every((c, i) => c === groups[at].coins[i])) return groups as LayoutGroup[];
  return groups.map((g, i) => (i === at ? { ...g, coins } : g));
}

export function toggleLine(hidden: readonly string[], symbol: string): string[] {
  return hidden.includes(symbol) ? hidden.filter((s) => s !== symbol) : [...hidden, symbol];
}

export function isFull(count: number): boolean {
  return count >= MAX_COINS;
}
