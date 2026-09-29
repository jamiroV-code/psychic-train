import type { SpreadPoint } from "@/lib/types/pairs";

/**
 * Loads the Svelte/LayerChart island bundle, once.
 *
 * The island is built by Vite into public/islands/ (see vite.islands.config.mjs)
 * rather than by Next, so it is fetched at runtime by URL and webpack must not
 * try to resolve it. The promise and the stylesheet link are both cached, so a
 * page with seven panels pays for the bundle exactly once.
 */

const ISLAND_URL = "/islands/spread-chart.js";
const ISLAND_CSS = "/islands/spread-chart.css";

export interface RegimeStore {
  state: { from: number; to: number; hoverIndex: number | null };
  registerElement(id: string, el: HTMLElement): () => void;
  zoomAt(fraction: number, deltaY: number): void;
  setHover(index: number | null): void;
  visibleBounds(): { lo: number; hi: number };
}

export interface RegimePanelLine {
  color: string;
  values: (number | null)[];
  gapBefore?: boolean[];
}

export interface IslandApi {
  mountSpreadChart(
    target: HTMLElement,
    props: { points: SpreadPoint[]; height: number },
  ): () => void;
  createRegimeChartSync(options: {
    gridDates: string[];
    gridTimes: number[];
    initialRange: { from: number; to: number } | null;
    onHover?: (index: number | null) => void;
  }): RegimeStore;
  mountRegimePanel(
    target: HTMLElement,
    props: {
      store: RegimeStore;
      gridDates: string[];
      lines: RegimePanelLine[];
      unit: string;
      height: number;
    },
  ): () => void;
}

let cached: Promise<IslandApi> | null = null;

function ensureIslandStyles() {
  if (typeof document === "undefined") return;
  if (document.querySelector(`link[href="${ISLAND_CSS}"]`)) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = ISLAND_CSS;
  document.head.appendChild(link);
}

export function loadIslands(): Promise<IslandApi> {
  if (!cached) {
    ensureIslandStyles();
    // A runtime import of a file served from public/, so webpack must not try
    // to resolve or bundle it — the island is built by Vite, not by Next.
    cached = import(/* webpackIgnore: true */ ISLAND_URL) as Promise<IslandApi>;
  }
  return cached;
}
