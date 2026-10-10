import type { Layout, LayoutUpdate } from "@/lib/types/layout";

// T41 / S5b: client for GET/POST /api/layout/crypto (T40 / S5a).

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
const TIMEOUT_MS = 10_000;
const PATH = "/api/layout/crypto";

/** The stored revision moved on (HTTP 409): someone else saved first. */
export class LayoutConflictError extends Error {
  constructor(message = "layout changed elsewhere") {
    super(message);
    this.name = "LayoutConflictError";
  }
}

async function request(init?: RequestInit): Promise<Layout> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${PATH}`, { ...init, signal: AbortSignal.timeout(TIMEOUT_MS) });
  } catch (err) {
    if (err instanceof Error && err.name === "TimeoutError") {
      throw new Error(`API request timed out after ${TIMEOUT_MS}ms: ${PATH}`);
    }
    throw err;
  }
  if (res.status === 409) throw new LayoutConflictError();
  if (!res.ok) throw new Error(`API request failed: ${PATH} -> ${res.status}`);
  return (await res.json()) as Layout;
}

export function fetchLayout(): Promise<Layout> {
  return request();
}

export function saveLayout(update: LayoutUpdate): Promise<Layout> {
  return request({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(update) });
}
