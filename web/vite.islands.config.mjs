import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { resolve } from "node:path";

/**
 * Builds the Svelte/LayerChart islands as a standalone ES module.
 *
 * Deliberately separate from Next's build: Next runs on webpack and Svelte 5's
 * supported bundler is Vite, so rather than force a .svelte loader into the
 * Next pipeline, the island is compiled on its own and dropped into public/.
 * Next never has to know Svelte exists.
 *
 * Trade-off, and the main thing the pilot is meant to expose: this does NOT
 * rebuild on `pnpm dev`. Editing a .svelte file means re-running
 * `pnpm build:islands`. Acceptable for one chart; it is the first thing that
 * would hurt at five.
 */
export default defineConfig({
  plugins: [svelte({ emitCss: true })],
  build: {
    lib: {
      entry: resolve(import.meta.dirname, "islands/entry.js"),
      formats: ["es"],
    },
    outDir: resolve(import.meta.dirname, "public/islands"),
    emptyOutDir: true,
    cssCodeSplit: false,
    // The island is loaded by a modern browser via a native dynamic import.
    target: "es2022",
    rollupOptions: {
      output: {
        // React imports this by a stable URL, so the entry cannot be hashed.
        // Chunks stay hashed and split: LayerChart pulls its heavier marks in
        // through dynamic imports, and splitting keeps those off the initial
        // request instead of inlining them into the entry.
        entryFileNames: "spread-chart.js",
        chunkFileNames: "chunks/[name]-[hash].mjs",
        assetFileNames: "spread-chart.[ext]",
      },
    },
  },
});
