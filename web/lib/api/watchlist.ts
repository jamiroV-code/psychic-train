// T41 / S5b: client for POST /api/watchlist and DELETE /api/watchlist/{symbol}.

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
const TIMEOUT_MS = 10_000;

export interface WatchlistResponse {
  coins: string[];
}

/** HTTP 409: the watchlist is at its cap; the message is the server's own text. */
export class WatchlistFullError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "WatchlistFullError";
  }
}

/** HTTP 422: the symbol is malformed. */
export class InvalidSymbolError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "InvalidSymbolError";
  }
}

async function detail(res: Response): Promise<string | null> {
  try {
    const body = (await res.json()) as { detail?: unknown };
    return typeof body.detail === "string" ? body.detail : null;
  } catch {
    return null;
  }
}

async function send(path: string, init: RequestInit): Promise<WatchlistResponse> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, { ...init, signal: AbortSignal.timeout(TIMEOUT_MS) });
  } catch (err) {
    if (err instanceof Error && err.name === "TimeoutError") {
      throw new Error(`API request timed out after ${TIMEOUT_MS}ms: ${path}`);
    }
    throw err;
  }
  if (res.status === 409) throw new WatchlistFullError((await detail(res)) ?? `API request failed: ${path} -> 409`);
  if (res.status === 422) throw new InvalidSymbolError((await detail(res)) ?? "invalid symbol");
  if (!res.ok) throw new Error(`API request failed: ${path} -> ${res.status}`);
  return (await res.json()) as WatchlistResponse;
}

export function addCoin(symbol: string, groupId?: string): Promise<WatchlistResponse> {
  const body = groupId === undefined ? { symbol } : { symbol, group_id: groupId };
  return send("/api/watchlist", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function removeCoin(symbol: string): Promise<WatchlistResponse> {
  return send(`/api/watchlist/${encodeURIComponent(symbol)}`, { method: "DELETE" });
}
