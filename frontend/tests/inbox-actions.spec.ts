import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { caseId, detail, mockWorkspace } from "./fixtures";

test("missing SI is named, a local reply is available and a link requires confirmation", async ({
  page,
}) => {
  await mockWorkspace(page);
  await page.route("**/api/v1/emails/email-1/document-actions", (r) =>
    r.fulfill({
      json: {
        missing: ["shipping instructions"],
        kind: "request_si",
        title: "Ask for shipping instructions",
        can_request: true,
        draft_reply: "Please send the shipping instructions.",
        references: {
          status: "no_match",
          email_references: [],
          suggestions: [
            {
              attachment_id: "source-si",
              original_name: "SI.txt",
              external_id: "email_007",
              email_id: "source-email",
              quote: "Booking ref: BK12345",
              code: "BK12345",
            },
          ],
        },
      },
    }),
  );
  let linked = false;
  await page.route("**/api/v1/jobs/link-job", (r) =>
    r.fulfill({ json: { id: "link-job", state: "succeeded" } }),
  );
  await page.route("**/api/v1/emails/email-1/link-document", (r) => {
    expect(r.request().postDataJSON().reason).toBe(
      "Confirmed shipment evidence",
    );
    linked = true;
    return r.fulfill({ status: 202, json: { job_id: "link-job" } });
  });
  await page.goto(`/cases/${caseId}`);
  const panel = page.getByRole("region", { name: "Document follow-up" });
  await expect(panel).toContainText("Not found: shipping instructions");
  await panel.getByText("Draft a reply to the sender", { exact: true }).click();
  await expect(panel.getByLabel("Reply draft")).toHaveValue(
    "Please send the shipping instructions.",
  );
  await expect(
    panel.getByRole("button", { name: "Confirm and link document" }),
  ).toBeDisabled();
  expect(linked).toBe(false);
  await panel
    .getByLabel("Reason for linking")
    .fill("Confirmed shipment evidence");
  await panel
    .getByRole("button", { name: "Confirm and link document" })
    .click();
  await expect(panel.getByRole("status")).toContainText(
    "No AI call was requested",
  );
  expect(linked).toBe(true);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth > innerWidth,
    ),
  ).toBe(false);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});

test("Trash restores an email with a reason and refreshes the list", async ({
  page,
}) => {
  await mockWorkspace(page);
  let restored = false;
  await page.route("**/api/v1/emails?*", (r) =>
    r.fulfill({
      json: {
        total: restored ? 0 : 1,
        items: restored
          ? []
          : [
              {
                id: "spam-1",
                display_id: "email_007",
                subject: "Offer",
                deleted_reason: "Confirmed spam",
                deleted_at: new Date().toISOString(),
              },
            ],
      },
    }),
  );
  await page.route("**/api/v1/emails/spam-1/restore", (r) => {
    expect(r.request().postDataJSON().reason).toBe("Removed by mistake");
    restored = true;
    return r.fulfill({ json: { state: "restored" } });
  });
  await page.goto("/trash");
  await page.getByText("Restore email", { exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Restore", exact: true }),
  ).toBeDisabled();
  await page.getByLabel("Reason", { exact: true }).fill("Removed by mistake");
  await page.getByRole("button", { name: "Restore", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "email_007: Offer" }),
  ).toHaveCount(0);
  expect(restored).toBe(true);
});

test("safety alert links to evidence and requires a reason before spam removal", async ({
  page,
}) => {
  await mockWorkspace(page);
  let done = false;
  await page.route("**/api/v1/alerts", (r) =>
    r.fulfill({
      json: {
        items: [
          {
            id: "alert-1",
            alert_type: "spam",
            title: "Review spam",
            description: "Review suspicious content",
            lifecycle: done ? "resolved" : "open",
            sample_email_ids: ["email-007"],
          },
        ],
      },
    }),
  );
  await page.route("**/api/v1/alerts/alert-1/action", (r) => {
    expect(r.request().postDataJSON()).toMatchObject({
      action: "confirm_spam",
      reason: "Reviewed spam evidence",
    });
    done = true;
    return r.fulfill({ json: { state: "resolved" } });
  });
  await page.goto("/alerts");
  await expect(
    page.getByRole("link", { name: "Review source email 1" }),
  ).toHaveAttribute("href", "/inbox/email-007");
  await expect(
    page.getByRole("button", { name: "Confirm spam and move to Trash" }),
  ).toBeDisabled();
  await page
    .getByLabel("Reason and investigation findings")
    .fill("Reviewed spam evidence");
  await page
    .getByRole("button", { name: "Confirm spam and move to Trash" })
    .click();
  await expect(
    page.getByRole("button", { name: "Confirm spam and move to Trash" }),
  ).toHaveCount(0);
  expect(done).toBe(true);
});
