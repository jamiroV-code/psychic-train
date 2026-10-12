import type { Layout, LayoutUpdate } from "@/lib/types/layout";

// T41 / S5b: client for GET/POST /api/layout/crypto (T40 / S5a).
// T47 / S9C: `createLayoutClient(section)` serves any section; the old
// exports stay bound to crypto.

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
const TIMEOUT_MS = 10_000;

/** The stored revision moved on (HTTP 409): someone else saved first. */
export class LayoutConflictError extends Error {
  constructor(message = "layout changed elsewhere") {
    super(message);
    this.name = "LayoutConflictError";
  }
}

async function request(path: string, init?: RequestInit): Promise<Layout> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, { ...init, signal: AbortSignal.timeout(TIMEOUT_MS) });
  } catch (err) {
    if (err instanceof Error && err.name === "TimeoutError") {
      throw new Error(`API request timed out after ${TIMEOUT_MS}ms: ${path}`);
    }
    throw err;
  }
  if (res.status === 409) throw new LayoutConflictError();
  if (!res.ok) throw new Error(`API request failed: ${path} -> ${res.status}`);
  return (await res.json()) as Layout;
}

export interface LayoutClient {
  fetchLayout: () => Promise<Layout>;
  saveLayout: (update: LayoutUpdate) => Promise<Layout>;
}

export function createLayoutClient(section: string): LayoutClient {
  const path = `/api/layout/${section}`;
  return {
    fetchLayout: () => request(path),
    saveLayout: (update) =>
      request(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(update) }),
  };
}

const cryptoClient = createLayoutClient("crypto");

export function fetchLayout(): Promise<Layout> {
  return cryptoClient.fetchLayout();
}

export function saveLayout(update: LayoutUpdate): Promise<Layout> {
  return cryptoClient.saveLayout(update);
}
