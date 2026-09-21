import { test, expect } from "@playwright/test";
import { mockWorkspace } from "./fixtures";

const SUMMARY = { emails_total: 10, emails_classified: 8, emails_unresolved: 2, cases_open: 0, cases_checked: 0, cases_failed: 0, review_queue_size: 0, awaiting_revision: 0, jobs_in_progress: 0, last_updated: new Date().toISOString(), document_checks: 0, mismatches: 0, spam_count: 0, safety_held: 0, safety_assessed: 10, processing_failures: 0, drift_alerts_active: null };

async function openDashboard(page: import("@playwright/test").Page, progress: () => object | null) {
  await mockWorkspace(page);
  await page.route("**/api/v1/dashboard", (route) => route.fulfill({ json: SUMMARY }));
  await page.route("**/api/v1/dashboard/preferences", (route) => route.fulfill({ json: { sections: ["metrics"] } }));
  await page.route("**/api/v1/quality/monitor", (route) => route.fulfill({ json: { state: "baseline_required" } }));
  await page.route("**/api/v1/workspace/processing", (route) => {
    const body = progress();
    return body ? route.fulfill({ json: body }) : route.fulfill({ status: 500, json: { error: { message: "down" } } });
  });
  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
}

test("while documents are being read the overview shows how far it has got, then the banner goes away", async ({ page }) => {
  let state: object = { eligible: 126, read: 34, compared: 30, failed: 0, active: true };
  await openDashboard(page, () => state);
  const banner = page.getByRole("status").filter({ hasText: "Reading and comparing" });
  await expect(banner).toContainText("34 of 126 emails read · 30 compared");
  await expect(banner.getByRole("progressbar", { name: "Documents read" })).toHaveAttribute("value", "34");
  state = { eligible: 126, read: 126, compared: 126, failed: 0, active: false };
  await expect(banner).toBeHidden({ timeout: 15_000 }); // the next poll sees nothing left to do
});

test("nothing is shown when no reading is under way", async ({ page }) => {
  await openDashboard(page, () => ({ eligible: 126, read: 126, compared: 126, failed: 0, active: false }));
  await expect(page.getByText("Reading and comparing")).toHaveCount(0);
});

test("a failing progress request never breaks the page around it", async ({ page }) => {
  await openDashboard(page, () => null);
  await expect(page.getByText("Reading and comparing")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
});
