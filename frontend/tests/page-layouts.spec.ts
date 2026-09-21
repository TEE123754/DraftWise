import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { mockWorkspace, caseId } from "./fixtures";

test("public and signed-out pages fit desktop, tablet and mobile", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  for (const path of [
    "/",
    "/sign-in",
    "/dashboard",
    "/demo",
    "/pricing",
    "/workflow",
    "/privacy",
    "/terms",
    "/missing-page",
  ]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    for (const width of [1440, 768, 390]) {
      await page.setViewportSize({ width, height: 900 });
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
        `${path} at ${width}px`,
      ).toBe(true);
    }
    expect((await new AxeBuilder({ page }).analyze()).violations, path).toEqual(
      [],
    );
    if (["/sign-in", "/dashboard"].includes(path)) {
      await page.screenshot({
        path: `../artifacts/ui/${path.slice(1)}-access-mobile.png`,
        fullPage: true,
      });
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.screenshot({
        path: `../artifacts/ui/${path.slice(1)}-access-desktop.png`,
        fullPage: true,
      });
    }
  }
  expect(errors).toEqual([]);
});

test("workspace pages contain their layout on mobile and desktop", async ({
  page,
}) => {
  await mockWorkspace(page);
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.route("**/api/v1/dashboard", (r) =>
    r.fulfill({
      json: {
        emails_total: 520,
        emails_classified: 510,
        emails_unresolved: 10,
        cases_open: 14,
        cases_checked: 63,
        cases_failed: 0,
        review_queue_size: 6,
        awaiting_revision: 3,
        jobs_in_progress: 0,
        last_updated: new Date().toISOString(),
        document_checks: 126,
        mismatches: 46,
        spam_count: 32,
        safety_held: 8,
        safety_assessed: 520,
        processing_failures: 0,
        drift_alerts_active: null,
      },
    }),
  );
  await page.route("**/api/v1/dashboard/preferences", (r) =>
    r.fulfill({ json: { sections: ["metrics", "guidance", "quality"] } }),
  );
  await page.route("**/api/v1/quality/monitor", (r) =>
    r.fulfill({ json: { state: "baseline_required" } }),
  );
  await page.route("**/api/v1/quality/benchmark", (r) =>
    r.fulfill({
      status: 503,
      json: {
        error: { message: "Quality results unavailable in this UI fixture" },
      },
    }),
  );
  for (const route of ["alerts", "rules", "emails**"])
    await page.route(`**/api/v1/${route}`, (r) =>
      r.fulfill({
        json: {
          items: [],
          total: 0,
          next_cursor: null,
          by_state: {},
          by_category: {},
        },
      }),
    );
  await page.route("**/api/v1/emails/email-ui-test",r=>r.fulfill({json:{id:"email-ui-test",display_id:"email_007",subject:"Shipping document review with a long shipment reference",sender:"operations@example.test",body:"Shipment reference: "+"AB1234567890".repeat(18),attachments:[],extractions:[],state:"classified",classification:{category:"GENERAL",ambiguous:false,run_metadata:{method:"rules"}}}}));
  await page.route("**/api/v1/emails/email-ui-test/document-actions",r=>r.fulfill({json:{missing:[],kind:"review",title:"Review correspondence",draft_reply:"",can_request:false,comparison_required:false,references:{status:"no_reference",email_references:[],suggestions:[]}}}));
  for (const path of [
    "/dashboard",
    "/inbox",
    "/inbox/email-ui-test",
    "/cases",
    `/cases/${caseId}`,
    "/review",
    "/completed",
    "/alerts",
    "/rules",
    "/analytics",
    "/trash",
    "/settings/connections",
  ]) {
    await page.goto(path);
    await expect(page.locator(".workspace-main h1")).toBeVisible();
    for (const width of [1440, 768, 390]) {
      await page.setViewportSize({ width, height: 900 });
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
        `${path} at ${width}px`,
      ).toBe(true);
    }
    expect((await new AxeBuilder({ page }).analyze()).violations, path).toEqual(
      [],
    );
    if (path === "/dashboard") {
      await expect(page.getByText("520", { exact: true })).toBeVisible();
      await page.screenshot({
        path: "../artifacts/ui/dashboard-workspace-mobile.png",
        fullPage: true,
      });
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.screenshot({
        path: "../artifacts/ui/dashboard-workspace-desktop.png",
        fullPage: true,
      });
    }
  }
  expect(errors).toEqual([]);
});

test("sign-in keeps email submission, failure and success feedback", async ({
  page,
}) => {
  let fail = true;
  await page.route("**/auth/v1/otp**", (r) =>
    r.fulfill(
      fail
        ? {
            status: 400,
            json: {
              msg: "Please try again",
              error_description: "Please try again",
            },
          }
        : { json: {} },
    ),
  );
  await page.goto("/sign-in");
  await page.getByLabel("Work email").fill("operator@example.test");
  await page.getByRole("button", { name: "Email me a sign-in link" }).click();
  await expect(page.locator("form").getByRole("alert")).toBeVisible();
  fail = false;
  await page.getByRole("button", { name: "Email me a sign-in link" }).click();
  await expect(page.getByRole("status")).toContainText("Check your email");
  await expect(page.getByRole("status")).toContainText("operator@example.test");
});
