import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./browser",
  fullyParallel: false,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:4173",
    channel: "chrome",
    headless: true,
    viewport: { width: 1100, height: 500 },
  },
  webServer: {
    command: "npm exec vite -- --host 127.0.0.1 --port 4173 --strictPort",
    url: "http://127.0.0.1:4173/browser/fixture.html",
    reuseExistingServer: process.env["CI"] !== "true",
  },
});
