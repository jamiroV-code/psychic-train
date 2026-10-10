import { mount, unmount } from "svelte";
import SpreadChart from "./spread-chart.svelte";
import RegimePanel from "./regime-panel.svelte";
import NarrativePanel from "./narrative-panel.svelte";
import OnchainPanel from "./onchain-panel.svelte";
import OnchainOverlay from "./onchain-overlay.svelte";
import SimpleLines from "./simple-lines.svelte";
import { createPanelSync } from "./panel-sync.svelte.js";
import { createLiveProps } from "./live-props.svelte.js";

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
 * Panels interleaved with React chrome are each their own mount, so the state
 * they share cannot live in any one of them. One store, created here once by
 * React and handed to every mount, is what keeps the coupled range/hover state
 * undivided. Used by the seven /regime panels and the /onchain chain panels.
 */
export { createPanelSync };

export function mountRegimePanel(target, props) {
  const app = mount(RegimePanel, { target, props });
  return () => unmount(app);
}

/**
 * One /narrative category panel. Independent by design (no shared range or
 * crosshair), so unlike the regime panels it takes no store.
 */
export function mountNarrativePanel(target, props) {
  const app = mount(NarrativePanel, { target, props });
  return () => unmount(app);
}

/** One /onchain chain panel. Shares the chain-panel store, like /regime. */
export function mountOnchainPanel(target, props) {
  const app = mount(OnchainPanel, { target, props });
  return () => unmount(app);
}

/**
 * The /onchain normalised comparison overlay. Takes its OWN store instance —
 * its range and readout are independent of the chain panels below it.
 */
export function mountOnchainOverlay(target, props) {
  const app = mount(OnchainOverlay, { target, props });
  return () => unmount(app);
}

/**
 * A plain multi-line time chart, shared by the screener's relative-performance
 * view and the drill-down MiniChart. No shared store: neither syncs with
 * anything.
 */
const SIMPLE_LINES_KEYS = ["series", "height", "format", "label", "timeframe", "highlight", "bands", "markers"];

/**
 * T43 / S11b: still a dispose function, now with an `update(props)` that
 * hands the mounted chart new data in place, so its zoom survives a refresh.
 */
export function mountSimpleLines(target, props) {
  const live = createLiveProps(props, SIMPLE_LINES_KEYS);
  const app = mount(SimpleLines, { target, props: live.props });
  return Object.assign(() => unmount(app), { update: (next) => live.set(next) });
}
