"use client";

import { useEffect, useRef } from "react";
import type { SpreadPoint } from "@/lib/types/pairs";

/**
 * The LayerChart pilot (Direction D).
 *
 * LayerChart peers on Svelte 5 and ships no React build, so this chart is
 * rendered by a Svelte island rather than by React. React still owns the DOM
 * node, the props and the lifecycle; the island is mounted into that node and
 * disposed on unmount. Nothing Svelte leaks back across the boundary.
 *
 * The island is built separately by `pnpm build:islands` into
 * public/islands/, so Next's own build never has to learn about Svelte. It is
 * fetched on demand — only a pair detail view pays for it.
 *
 * `points` is passed through verbatim; the mapping to chart-ready data lives in
 * lib/pairs-spread-series.ts, where it is unit-tested independently of whatever
 * chart library sits underneath.
 */

const ISLAND_URL = "/islands/spread-chart.js";
const ISLAND_CSS = "/islands/spread-chart.css";

type MountFn = (
  target: HTMLElement,
  props: { points: SpreadPoint[]; height: number },
) => () => void;

function ensureIslandStyles() {
  if (document.querySelector(`link[href="${ISLAND_CSS}"]`)) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = ISLAND_CSS;
  document.head.appendChild(link);
}

export function SpreadChart({ points, height = 260 }: { points: SpreadPoint[]; height?: number }) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let disposed = false;
    let unmountIsland: (() => void) | undefined;

    ensureIslandStyles();

    // A runtime import of a file served from public/, so webpack must not try
    // to resolve or bundle it — the island is built by Vite, not by Next.
    import(/* webpackIgnore: true */ ISLAND_URL)
      .then((mod: { mountSpreadChart: MountFn }) => {
        // The effect can be torn down before the island finishes loading.
        if (disposed) return;
        unmountIsland = mod.mountSpreadChart(container, { points, height });
      })
      .catch(() => {
        // The chart is an aid, not the reading. If the island cannot load, the
        // surrounding panel still shows the plotted range and every statistic,
        // so this stays silent rather than replacing data with an error.
      });

    return () => {
      disposed = true;
      unmountIsland?.();
    };
  }, [points, height]);

  // Direction D: the chart is a LIGHT analytical panel inside the dark shell,
  // so the plot keeps the contrast budget that reading small numbers needs.
  // The testid stays on the chart host, not the panel.
  return (
    <div className="analytic-panel">
      <div data-testid="pairs-spread-chart" ref={containerRef} style={{ width: "100%" }} />
    </div>
  );
}
