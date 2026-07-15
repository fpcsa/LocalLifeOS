import { defineConfig } from "vitest/config";

export default defineConfig({
  root: process.cwd(),
  resolve: {
    alias: {
      "@": process.cwd(),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    include: ["**/*.test.{ts,tsx}"],
  },
});
