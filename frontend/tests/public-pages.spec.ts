import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("the public workflow describes the six real steps and does not claim a Gmail import that does not work", async ({ page }) => {
  await page.goto("/workflow");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("How DraftWise works");
  const steps = page.getByRole("heading", { level: 2, name: /^Step / });
  await expect(steps).toHaveText([
    "Step 1: Intake",
    "Step 2: Classify",
    "Step 3: Documents",
    "Step 4: Extract",
    "Step 5: Compare",
    "Step 6: Decide and reply",
  ]);
  const text = await page.locator("main, body").first().innerText();
  expect(text).not.toMatch(/imported from a connected gmail/i);
  expect(text).toMatch(/Gmail inbox is not available yet/);
  expect(text).not.toMatch(/sanction|restricted goods/i); // the safety step is spam and phishing signals only
  expect(text).toMatch(/Local rules decide first/);
  expect(text).toMatch(/Nothing is sent for you/);
  await expect(page.getByRole("heading", { level: 2, name: "What the inbox colours mean" })).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});

test("pricing does not list the Gmail connection as available", async ({ page }) => {
  await page.goto("/pricing");
  await expect(page.getByText(/Gmail inbox connection/)).toContainText("not yet available");
});
