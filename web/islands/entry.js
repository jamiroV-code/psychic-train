import { mount, unmount } from "svelte";
import SpreadChart from "./spread-chart.svelte";

/**
 * The island boundary.
 *
 * LayerChart peers on Svelte 5 and has no React build, so charts are the one
 * part of the app that genuinely has to leave React. This module is the seam:
 * React owns the DOM node, calls `mountSpreadChart` with plain data, and gets a
 * disposer back. Nothing Svelte crosses back into React.
 *
 * Built by `pnpm build:islands` (vite.islands.config.js) into
 * public/islands/spread-chart.js, so Next's own build stays untouched.
 */
export function mountSpreadChart(target, props) {
  const app = mount(SpreadChart, { target, props });
  return () => unmount(app);
}
