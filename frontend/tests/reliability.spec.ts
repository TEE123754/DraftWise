import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { mockWorkspace, detail } from "./fixtures";

test("homepage settles, assets load and mobile layout fits", async ({
  page,
}) => {
  const response = await page.goto("/");
  expect(response?.status()).toBe(200);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Verify Shipping Emails with Clear Next Steps",
  );
  await expect(page.locator("img").first()).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  for (const width of [390, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  }
  expect((await page.request.get("/opengraph-image.png")).status()).toBe(200);
  expect((await page.request.get("/icon.png")).status()).toBe(200);
  await page.screenshot({
    path: "../artifacts/ui/landing-redesign-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: "../artifacts/ui/landing-redesign-mobile.png",
    fullPage: true,
  });
});

test("dashboard fails honestly and case-list navigation is valid", async ({
  page,
}) => {
  await mockWorkspace(page);
  await page.route("**/api/v1/dashboard", (route) =>
    route.fulfill({
      status: 500,
      json: { error: { message: "Summary unavailable" } },
    }),
  );
  await page.goto("/dashboard");
  await expect(page.locator('section[role="alert"]')).toContainText(
    "Summary unavailable",
  );
  await expect(page.getByText("520", { exact: true })).toHaveCount(0);
  await page.getByRole("link", { name: "Cases", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Attention queue" }),
  ).toBeVisible();
  await page.goto("/cases?readiness=awaiting_revision");
  await expect(
    page.getByRole("heading", { name: "Attention queue" }),
  ).toBeVisible();
});

test("assistant sends workspace credentials and displays a cited response", async ({
  page,
}) => {
  await mockWorkspace(page);
  await page.route("**/api/v1/chat", (route) => {
    expect(route.request().headers()["x-workspace-id"]).toBeTruthy();
    expect(route.request().headers()["authorization"]).toBeTruthy();
    return route.fulfill({
      json: {
        answer: "One case needs review.",
        citations: [{ caseId: detail.case.id }],
      },
    });
  });
  await page.goto("/cases");
  await page
    .getByRole("button", { name: "Open Ask DraftWise assistant" })
    .click();
  await page.getByRole("button", { name: "What needs my attention?" }).click();
  await expect(page.getByText("One case needs review.")).toBeVisible();
});

test("failed alert actions retain the alert", async ({ page }) => {
  await mockWorkspace(page);
  await page.route("**/api/v1/alerts**", (route) =>
    route.request().method() === "GET"
      ? route.fulfill({
          json: {
            items: [
              {
                id: "test-alert",
                alert_type: "drift",
                severity: "medium",
                title: "Test review alert",
                description: "Synthetic fixture",
                lifecycle: "open",
                sample_email_ids: [],
                created_at: new Date().toISOString(),
                affected_window_start: new Date().toISOString(),
                affected_window_end: new Date().toISOString(),
              },
            ],
          },
        })
      : route.fulfill({
          status: 500,
          json: { error: { message: "Save failed" } },
        }),
  );
  await page.goto("/alerts");
  await page
    .getByLabel("Reason and investigation findings")
    .fill("Reviewed sample evidence");
  await page
    .getByRole("button", { name: "Record investigation", exact: true })
    .click();
  await expect(page.locator('p[role="alert"]')).toContainText("Save failed");
  await expect(
    page.getByRole("button", { name: "Record investigation", exact: true }),
  ).toBeVisible();
});
