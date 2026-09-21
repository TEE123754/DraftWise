import { test, expect } from "@playwright/test";
import { caseId, mockWorkspace } from "./fixtures";

test("the assistant tells the server which page it is asked from, offers page-specific questions and links emails it cites", async ({ page }) => {
  await mockWorkspace(page);
  let sent: unknown;
  await page.route("**/api/v1/chat", (route) => {
    sent = route.request().postDataJSON();
    return route.fulfill({
      json: {
        answer: "email_11 needs documents. Shipping instructions found; draft BL not found.",
        citations: [{ emailId: "11111111-1111-4111-8111-111111111111", label: "email_11" }, { caseId }],
        grounded_on: "workspace_data", method: "read_only_summary", fallback_reason: null,
        source: { label: "Inbox", href: "/inbox" },
      },
    });
  });
  await page.goto(`/cases/${caseId}`);
  await page.getByRole("button", { name: "Open Ask DraftWise assistant" }).click();
  const dialog = page.getByRole("dialog", { name: "Ask DraftWise assistant" });

  // On a case page the first suggestion is about this case; on other pages it would not be.
  await expect(dialog.getByRole("button", { name: "What is the status of this case?" })).toBeVisible();
  await expect(dialog.getByRole("button", { name: "What should I do with this email?" })).toHaveCount(0);
  await expect(dialog.getByRole("button", { name: "Which emails are missing documents?" })).toBeVisible();

  await dialog.getByRole("button", { name: "What is the status of this case?" }).click();
  await expect(dialog).toContainText("email_11 needs documents.");
  expect(sent).toEqual({ message: "What is the status of this case?", page: { path: `/cases/${caseId}`, case_id: caseId } });

  // Emails are cited by their own ID and open the email; cases still open the case.
  await expect(dialog.getByRole("link", { name: "email_11" })).toHaveAttribute("href", "/inbox/11111111-1111-4111-8111-111111111111");
  await expect(dialog.getByRole("link", { name: /^Case / })).toHaveAttribute("href", `/cases/${caseId}`);
});

test("away from an email or case the assistant sends only the path", async ({ page }) => {
  await mockWorkspace(page);
  await page.route("**/api/v1/dashboard**", (route) => route.fulfill({ json: { emails_total: 1, emails_classified: 1, cases_open: 0, cases_checked: 0, cases_failed: 0, review_queue_size: 0, awaiting_revision: 0, jobs_in_progress: 0, last_updated: new Date().toISOString() } }));
  let sent: unknown;
  await page.route("**/api/v1/chat", (route) => {
    sent = route.request().postDataJSON();
    return route.fulfill({ json: { answer: "Nothing needs a person right now.", citations: [], grounded_on: "workspace_data", method: "read_only_summary", fallback_reason: null, source: { label: "Inbox", href: "/inbox" } } });
  });
  await page.goto("/dashboard");
  await page.getByRole("button", { name: "Open Ask DraftWise assistant" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "What needs my attention?" }).click();
  await expect(page.getByRole("dialog")).toContainText("Nothing needs a person right now.");
  expect(sent).toEqual({ message: "What needs my attention?", page: { path: "/dashboard" } });
});
