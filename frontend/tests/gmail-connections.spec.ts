import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { mockWorkspace } from "./fixtures";

const FUTURE =
  "Fetching mail from Gmail is planned for a future release and is not available yet. For now, add emails and their documents by upload, or open the demo, which comes with 520 sample emails.";
const CONNECTION = {
  id: "50000000-0000-4000-8000-000000000001",
  workspace_id: "20000000-0000-4000-8000-000000000001",
  email: "ops@example.test",
  state: "active",
  messages_imported: 0,
  last_sync_at: null,
  last_error: null,
  created_at: new Date().toISOString(),
};

test("a real user is told Gmail fetching is future development, with no way to start it", async ({ page }) => {
  await mockWorkspace(page);
  await page.route("**/api/v1/gmail/connections", (route) =>
    route.fulfill({ json: { items: [], available: false, configured: false, future: true, message: FUTURE } }),
  );
  await page.goto("/settings/connections");
  await expect(page.getByRole("heading", { name: "Gmail import: future development" })).toBeVisible();
  await expect(page.getByText(FUTURE)).toBeVisible();
  await expect(page.getByText("Coming in a future release")).toBeVisible();
  await expect(page.getByRole("button", { name: /Connect New Mailbox/ })).toHaveCount(0);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});

test("trying to sync an earlier connection shows the future-development message and it can still be disconnected", async ({ page }) => {
  await mockWorkspace(page);
  await page.route("**/api/v1/gmail/connections", (route) =>
    route.fulfill({ json: { items: [CONNECTION], available: false, configured: true, future: true, message: FUTURE } }),
  );
  await page.route("**/api/v1/gmail/connections/*/sync", (route) =>
    route.fulfill({
      status: 501,
      json: { error: { code: "GMAIL_FUTURE_DEVELOPMENT", message: FUTURE, retryable: false, details: {}, request_id: "r" } },
    }),
  );
  await page.goto("/settings/connections");
  await expect(page.getByText("ops@example.test")).toBeVisible();
  await expect(page.getByRole("button", { name: /Disconnect/ })).toBeVisible();
  await page.getByRole("button", { name: /Sync Now/ }).click();
  await expect(page.getByRole("alert").filter({ hasText: "future release" })).toBeVisible();
  await expect(page.getByText(/enqueued/)).toHaveCount(0); // it never claims mail is on its way
});

test("in the demo one click fetches the whole sample mailbox, without asking for an email ID", async ({ page }) => {
  await mockWorkspace(page);
  await page.addInitScript(() => sessionStorage.setItem("draftwise-demo-workspace", "demo-workspace"));
  let body: unknown = null;
  await page.route("**/api/v1/gmail/connections", (route) =>
    route.fulfill({ json: { items: [], available: false, configured: false, message: "Gmail import is not available in demo mode." } }),
  );
  await page.route("**/api/v1/demo/gmail/fetch", async (route) => {
    body = route.request().postDataJSON();
    return route.fulfill({
      json: {
        simulation: true, fetched: 520, imported: 0, reused: 520, queued_for_reading: 0,
        message: "Fetched 520 emails from the sample mailbox: 0 new, 520 already in your workspace (not duplicated).",
      },
    });
  });
  await page.goto("/settings/connections");
  await expect(page.getByLabel("Sample email ID")).toHaveCount(0);
  await page.getByRole("button", { name: "Simulate Gmail fetch" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Fetched 520 emails" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Open the inbox" })).toBeVisible();
  expect(body).toEqual({ prefer_ai: false }); // no email_id: the backend fetches all 520
});
