import AxeBuilder from "@axe-core/playwright";
import { test, expect } from "@playwright/test";
import { caseId, mockWorkspace } from "./fixtures";

test("attention queue supports keyboard navigation and passes accessibility checks", async ({
  page,
}) => {
  await mockWorkspace(page);
  await page.goto("/cases");
  await expect(
    page.getByRole("heading", { name: "Attention queue" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "BK-2026-041" }),
  ).toBeVisible();
  await page.getByRole("link", {name:"Skip to content"}).focus();
  await expect(
    page.getByRole("link", { name: "Skip to content" }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/#main-content$/);
  const findings = await new AxeBuilder({ page }).analyze();
  expect(findings.violations).toEqual([]);
  await page.goto(`/cases/${caseId}`);
  await expect(
    page.getByRole("heading", { name: "BK-2026-041" }),
  ).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});
