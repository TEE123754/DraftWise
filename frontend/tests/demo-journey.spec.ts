import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { detail } from "./fixtures";

test("anonymous visitor enters a demo without a user session", async ({
  page,
}) => {
  let opened = false;
  await page.route("http://127.0.0.1:8000/api/v1/**", async (route) => {
    if (route.request().url().endsWith("/demo/session")) {
      opened = true;
      return route.fulfill({
        status: 201,
        json: { workspace_id: "demo-workspace", role: "admin" },
      });
    }
    expect(route.request().headers()["x-demo-mode"]).toBe("true");
    expect(route.request().headers()["x-workspace-id"]).toBe("demo-workspace");
    expect(route.request().headers()["authorization"]).toBeUndefined();
    if (route.request().url().endsWith("/dashboard")) return route.fulfill({ json: {
      emails_total: 520, emails_classified: 99, cases_open: 1, cases_checked: 0, cases_failed: 0,
      review_queue_size: 1, awaiting_revision: 0, jobs_in_progress: 0, last_updated: new Date().toISOString(),
    } });
    return route.fulfill({ json: { items: [detail.case], next_cursor: null } });
  });
  await page.goto("/demo");
  await expect(
    page.getByRole("button", { name: "Start the demo" }),
  ).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.getByRole("button", { name: "Start the demo" }).click();
  await expect(
    page.getByText("BK-2026-041"),
  ).toBeVisible();
  await expect(page.getByText("Sample workspace", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Work email")).toHaveCount(0);
  expect(opened).toBe(true);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({ path: "../artifacts/ui/overview-redesign-desktop.png", fullPage: true });
  for (const width of [390, 768]) {
    await page.setViewportSize({ width, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: "../artifacts/ui/overview-redesign-mobile.png", fullPage: true });
});
