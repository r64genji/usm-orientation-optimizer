import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  use: {
    baseURL: "http://127.0.0.1:8866",
    viewport: { width: 390, height: 844 },
  },
  projects: [{ name: "phone", use: { ...devices["Pixel 7"] } }],
});
