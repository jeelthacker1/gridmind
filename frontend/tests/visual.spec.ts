import { test, expect } from "@playwright/test";
test("desktop and mobile presentation", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Email", { exact: true }).fill("admin@gridmind.local");
  await page
    .getByLabel("Password", { exact: true })
    .fill(process.env.DEMO_PASSWORD || "test-only-password-123");
  await page.getByRole("button", { name: "Enter control center" }).click();
  await page.getByRole("button", { name: "Optimize dispatch" }).click();
  await expect(
    page.getByRole("heading", { name: "Control strategy comparison" }),
  ).toBeVisible({ timeout: 90000 });
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: "test-results/control-center.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page
    .getByRole("heading", { name: "Control center", exact: true })
    .scrollIntoViewIfNeeded();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: "test-results/mobile.png", fullPage: true });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});
