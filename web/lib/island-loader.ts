import type { SpreadPoint } from "@/lib/types/pairs";
import type { Timeframe } from "@/lib/types/screener";

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

export interface PanelSyncStore {
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

export interface NarrativePanelLine {
  key: string;
  color: string;
  values: (number | null)[];
  gapBefore?: boolean[];
  dashed?: boolean;
}

export interface OnchainMarker {
  date: string;
  kind: string;
}

export interface OnchainOverlayLine {
  key: string;
  color: string;
  values: (number | null)[];
  gapBefore?: boolean[];
}

export interface SimpleLineSeries {
  key: string;
  color: string;
  width?: number;
  points: { timestamp: string; value: number }[];
}

export interface IslandApi {
  mountSpreadChart(
    target: HTMLElement,
    props: { points: SpreadPoint[]; height: number },
  ): () => void;
  createPanelSync(options: {
    gridDates: string[];
    gridTimes: number[];
    initialRange: { from: number; to: number } | null;
    onHover?: (index: number | null) => void;
  }): PanelSyncStore;
  mountNarrativePanel(
    target: HTMLElement,
    props: {
      dates: string[];
      lines: NarrativePanelLine[];
      composite: { color: string; values: (number | null)[]; gapBefore?: boolean[] };
      mixedScale: { color: string; values: (number | null)[] } | null;
      height: number;
    },
  ): () => void;
  mountOnchainPanel(
    target: HTMLElement,
    props: {
      store: PanelSyncStore;
      gridDates: string[];
      value: (number | null)[];
      preLaunchValue: (number | null)[];
      ema28: (number | null)[];
      gapBefore: boolean[];
      markers: OnchainMarker[];
      color: string;
      rawColor: string;
      preLaunchColor: string;
      preLaunchFill: string;
      floorColor: string;
      rampColor: string;
      height: number;
      label: string;
    },
  ): () => void;
  mountOnchainOverlay(
    target: HTMLElement,
    props: {
      store: PanelSyncStore;
      gridDates: string[];
      lines: OnchainOverlayLine[];
      logScale: boolean;
      format: (v: number) => string;
      height: number;
      label: string;
    },
  ): () => void;
  mountSimpleLines(
    target: HTMLElement,
    props: {
      series: SimpleLineSeries[];
      height: number;
      format?: (v: number) => string;
      label: string;
      // T34 / S2: when set, the time axis is UTC with labels from
      // chart-time-format; when absent it is exactly the old local axis.
      timeframe?: Timeframe;
      // T37 / S6: emphasise the line nearest the pointer (the spaghetti chart).
      highlight?: boolean;
    },
  ): () => void;
  mountRegimePanel(
    target: HTMLElement,
    props: {
      store: PanelSyncStore;
      gridDates: string[];
      lines: RegimePanelLine[];
      unit: string;
      height: number;
      label: string;
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
