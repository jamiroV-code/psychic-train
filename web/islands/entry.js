import { mount, unmount } from "svelte";
import SpreadChart from "./spread-chart.svelte";
import RegimePanel from "./regime-panel.svelte";
import { createRegimeChartSync } from "./regime-sync.svelte.js";

/**
 * The island boundary.
 *
 * LayerChart peers on Svelte 5 and has no React build, so charts are the one
 * part of the app that genuinely has to leave React. This module is the seam:
 * React owns the DOM nodes, passes plain data in and gets callbacks and
 * disposers back. Nothing Svelte crosses back into React.
 *
 * Built by `pnpm build:islands` (vite.islands.config.mjs) into
 * public/islands/spread-chart.js, so Next's own build stays untouched.
 */
export function mountSpreadChart(target, props) {
  const app = mount(SpreadChart, { target, props });
  return () => unmount(app);
}

/**
 * The seven /regime panels are interleaved with React chrome, so each plot is
 * its own mount. They share one store, created here once by React, which is
 * what keeps the coupled range/hover state undivided across those mounts.
 */
export { createRegimeChartSync };

export function mountRegimePanel(target, props) {
  const app = mount(RegimePanel, { target, props });
  return () => unmount(app);
}
