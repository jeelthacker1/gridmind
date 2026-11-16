import { test, expect } from "@playwright/test";
test("operator journey: dispatch, playback, forecast, scenario and reports", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByLabel("Email", { exact: true }).fill("admin@gridmind.local");
  await page
    .getByLabel("Password", { exact: true })
    .fill(process.env.DEMO_PASSWORD || "test-only-password-123");
  await page.getByRole("button", { name: "Enter control center" }).click();
  await expect(
    page.getByRole("heading", { name: "Control center", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Optimize dispatch" }).click();
  await expect(
    page.getByRole("heading", { name: "Control strategy comparison" }),
  ).toBeVisible({ timeout: 90000 });
  await page.getByRole("button", { name: "Start simulation" }).click();
  await expect(
    page.getByRole("button", { name: "Pause simulation" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Pause simulation" }).click();
  await page.getByRole("button", { name: "Reset simulation" }).click();
  await page
    .getByRole("button", { name: "Forecast studio", exact: true })
    .click();
  await page.getByRole("button", { name: "Generate forecast" }).click();
  await expect(
    page.getByRole("heading", { name: "Held-out test performance" }),
  ).toBeVisible({ timeout: 90000 });
  await page.getByRole("button", { name: "What-if lab", exact: true }).click();
  await page.getByRole("button", { name: "Run comparison" }).click();
  await expect(
    page.getByRole("heading", { name: "Computed scenario differences" }),
  ).toBeVisible({ timeout: 90000 });
  await page.getByRole("button", { name: "Grid outage", exact: true }).click();
  await page.getByRole("button", { name: "Run comparison" }).click();
  await expect(page.getByRole("status")).toContainText("completed", {
    timeout: 90000,
  });
  await page.getByRole("button", { name: "Reports", exact: true }).click();
  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: "CSV ↗" }).first().click();
  expect((await download).suggestedFilename()).toContain(".csv");
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByRole("heading", { name: "Run archive & exports" }),
  ).toBeVisible();
});
