import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { mockWorkspace } from "./fixtures";

const STATES = ["needs_documents", "waiting_for_draft", "needs_review", "mismatch_found", "held", "spam", "processing", "checked", "classified"];
const ATTENTION = [
  { id: "id-14", display_id: "email_014", subject: "Verify your account now", state: "held", state_label: "Held for safety", action: { kind: "review_safety", title: "Inspect the safety signals, then release or delete the email" } },
  { id: "id-10", display_id: "email_010", subject: "Draft BL for SIN10", state: "mismatch_found", state_label: "Mismatch found", action: { kind: "preview_corrections", title: "Preview the correction request" } },
];

async function open(page: import("@playwright/test").Page, saved: string[]) {
  await mockWorkspace(page);
  const posted: string[][] = [];
  await page.route("**/api/v1/dashboard", (route) =>
    route.fulfill({ json: { emails_total: 40, emails_classified: 38, emails_unresolved: 2, cases_open: 1, cases_checked: 0, cases_failed: 0, review_queue_size: 1, awaiting_revision: 0, jobs_in_progress: 0, last_updated: new Date().toISOString(), document_checks: 3, mismatches: 1, spam_count: 1, safety_held: 1, safety_assessed: 40, processing_failures: 0, drift_alerts_active: null } }),
  );
  await page.route("**/api/v1/dashboard/preferences", (route) => {
    if (route.request().method() === "POST") {
      const sections = route.request().postDataJSON().sections;
      posted.push(sections);
      saved = sections;
    }
    return route.fulfill({ json: { sections: saved } });
  });
  await page.route("**/api/v1/quality/monitor", (route) => route.fulfill({ json: { state: "baseline_required" } }));
  await page.route("**/api/v1/emails/counts", (route) =>
    route.fulfill({ json: { total: 40, by_state: Object.fromEntries(STATES.map((s, i) => [s, s === "held" ? 8 : i + 1])), by_category: {} } }),
  );
  await page.route("**/api/v1/emails?**", (route) => route.fulfill({ json: { items: ATTENTION, total: 2, next_cursor: null } }));
  await page.goto("/dashboard");
  return posted;
}

test("the dashboard lists the emails that need a person and counts every state, each linking into the inbox", async ({ page }) => {
  await open(page, ["attention", "states", "metrics"]);
  const attention = page.getByRole("region", { name: "Needs my attention" });
  const rows = attention.getByRole("listitem");
  await expect(rows).toHaveCount(2);
  await expect(rows.first()).toContainText("email_014");
  await expect(rows.first()).toContainText("Held for safety");
  await expect(rows.first().getByRole("link")).toHaveAttribute("href", "/inbox/id-14");
  await expect(rows.nth(1)).toContainText("Next: Preview the correction request");

  const states = page.getByRole("region", { name: "Emails by state" });
  await expect(states.getByRole("link")).toHaveCount(9);
  const held = states.getByRole("link", { name: /Held for safety/ });
  await expect(held).toHaveAttribute("href", "/inbox?state=held");
  await expect(held).toContainText("8");
  await expect(states.getByRole("link", { name: /Mismatch found/ })).toHaveAttribute("href", "/inbox?state=mismatch_found");
  // Failed processing opens the emails whose job failed, not an approximating review state.
  await expect(page.locator('a[href="/inbox?failed=true"]')).toHaveCount(1);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});

test("panels can be reordered from the keyboard, hidden, saved and restored", async ({ page }) => {
  const posted = await open(page, ["attention", "states", "metrics", "guidance", "quality"]);
  const order = () => page.locator("section[aria-label]:not([aria-label='Dashboard customization']):not([aria-label='Workspace summary']) > h3").allTextContents();

  await page.getByRole("button", { name: "Customize dashboard" }).click();
  await expect(page.getByRole("button", { name: "Move Needs my attention up" })).toBeDisabled(); // already first
  await page.getByRole("button", { name: "Move Needs my attention down" }).focus();
  await page.keyboard.press("Enter");
  await page.getByRole("checkbox", { name: /Review checklist/ }).uncheck();
  await page.getByRole("button", { name: "Save view" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Dashboard view saved." })).toBeVisible();
  expect(posted.at(-1)).toEqual(["states", "attention", "metrics", "quality"]);
  const saved = ["Emails by state", "Needs my attention", "Workload and safety", "Model quality and drift"];
  await expect.poll(order).toEqual(saved);

  await page.reload(); // the saved view comes back from the server, not from the page
  await expect.poll(order).toEqual(saved);

  await page.getByRole("button", { name: "Customize dashboard" }).click();
  await page.getByRole("button", { name: "Reset to default" }).click();
  await page.getByRole("button", { name: "Save view" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Dashboard view saved." })).toBeVisible();
  expect(posted.at(-1)).toEqual(["attention", "states", "metrics", "guidance", "quality"]);
});
