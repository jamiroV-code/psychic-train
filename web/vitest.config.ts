import { configDefaults, defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

// `@vitejs/plugin-react` configures Vite/esbuild's automatic JSX runtime.
// Without it, esbuild falls back to the classic transform, which compiles
// `<Component />` to `React.createElement(...)` and requires `React` to be
// in scope in every file — but this codebase (React 19 / Next 15 style)
// never imports React explicitly, since Next's own SWC compiler already
// uses the automatic runtime. Vitest's default config doesn't get that for
// free; found (18-09-26, first real `pnpm test` run) via
// `ReferenceError: React is not defined` across every component test.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    // Playwright specs live in e2e/ and use @playwright/test's `test`, which
    // vitest cannot run (backlog vitest-config-e2e-exclude_19-09-26).
    exclude: [...configDefaults.exclude, "e2e/**"],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
});
