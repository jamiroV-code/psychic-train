/**
 * T43 / S11b: structural sharing for a refetched payload, so a chart whose
 * data did not change keeps the very same objects and is never touched.
 *
 * `shareStructure(prev, next)` returns `prev` itself when the two are equal
 * ignoring the volatile keys (the clock fields every answer restamps) at any
 * depth; otherwise `next`, with every equal subtree replaced by the previous
 * object, so unchanged siblings keep their identity.
 */

export const VOLATILE: readonly string[] = ["server_time", "fetched_at", "clock_skew_seconds"];

function isPlainObject(value: unknown): value is Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return false;
  const proto = Object.getPrototypeOf(value);
  return proto === Object.prototype || proto === null;
}

function share(prev: unknown, next: unknown, volatile: ReadonlySet<string>): unknown {
  if (Object.is(prev, next)) return prev;

  if (Array.isArray(prev) && Array.isArray(next)) {
    const out = next.map((item, i) => (i < prev.length ? share(prev[i], item, volatile) : item));
    const same = prev.length === next.length && out.every((item, i) => item === prev[i]);
    return same ? prev : out;
  }

  if (isPlainObject(prev) && isPlainObject(next)) {
    const stable = (obj: Record<string, unknown>) => Object.keys(obj).filter((k) => !volatile.has(k));
    let same = stable(prev).length === stable(next).length;
    const out: Record<string, unknown> = {};
    for (const key of Object.keys(next)) {
      if (volatile.has(key)) {
        out[key] = next[key];
        continue;
      }
      if (!Object.prototype.hasOwnProperty.call(prev, key)) {
        same = false;
        out[key] = next[key];
        continue;
      }
      const value = share(prev[key], next[key], volatile);
      if (value !== prev[key]) same = false;
      out[key] = value;
    }
    return same ? prev : out;
  }

  return next;
}

export function shareStructure<T>(prev: T | null | undefined, next: T, volatile: readonly string[] = VOLATILE): T {
  if (prev === null || prev === undefined) return next;
  return share(prev, next, new Set(volatile)) as T;
}
