import { expect, test } from "@playwright/test";

test("operator can open the board on a phone-sized screen", async ({ page }) => {
  test.skip(!process.env.DASHBOARD_AUTH_TOKEN, "Needs a live dashboard");
  await page.addInitScript((token) => sessionStorage.setItem("usm-dashboard-token", token), process.env.DASHBOARD_AUTH_TOKEN);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Movement test board" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Start test" })).toBeVisible();
});
