import { test, expect, type Page } from "@playwright/test";
import { mockWorkspace } from "./fixtures";

const failed = {
  id: "c1",
  storage_key: "uploads/ws/a/stuck-invoice.pdf",
  file_name: "stuck-invoice.pdf",
  state: "failed",
  attempts: 8,
  last_error: "ConnectionError",
  next_attempt_at: new Date().toISOString(),
  created_at: new Date().toISOString(),
  finished_at: new Date().toISOString(),
};

async function mockTrash(page: Page, role: string) {
  const retried: string[] = [];
  let items = [failed];
  await mockWorkspace(page, role);
  await page.route("**/api/v1/emails?trash=true**", (route) => route.fulfill({ json: { items: [], total: 0, next_cursor: null } }));
  await page.route("**/api/v1/storage-cleanup**", async (route) => {
    const retry = new URL(route.request().url()).pathname.match(/storage-cleanup\/(.+)\/retry$/);
    if (retry) {
      retried.push(retry[1]);
      items = [];
      return route.fulfill({ json: { ...failed, state: "pending", attempts: 0 } });
    }
    return route.fulfill({
      json: {
        by_state: { pending: 0, deleted: 5, skipped: 1, failed: items.length },
        storage_configured: true,
        items,
      },
    });
  });
  return retried;
}

test("an administrator sees files storage would not delete and can queue one again", async ({ page }) => {
  const retried = await mockTrash(page, "admin");
  await page.goto("/trash");
  const panel = page.getByRole("region", { name: "File deletion after Trash" });
  await expect(panel.getByText("stuck-invoice.pdf")).toBeVisible();
  await expect(panel.getByText(/Gave up after 8 attempts \(ConnectionError\)/)).toBeVisible();
  await expect(panel.locator('[data-cleanup-count="Deleted"]')).toHaveText("5");

  await panel.getByRole("button", { name: "Retry deletion" }).click();
  await expect(panel.getByRole("status")).toContainText("stuck-invoice.pdf is queued again");
  await expect(panel.getByText("No file has failed to delete.")).toBeVisible();
  expect(retried).toEqual(["c1"]);
});

test("the deletion queue is not shown to anyone but an administrator", async ({ page }) => {
  await mockTrash(page, "reviewer");
  await page.goto("/trash");
  await expect(page.getByRole("heading", { name: "Trash" })).toBeVisible();
  await expect(page.getByRole("region", { name: "File deletion after Trash" })).toHaveCount(0);
});
