import { test, expect } from "@playwright/test";
import { caseId, detail, mockWorkspace } from "./fixtures";

test("returned draft shows fixed issues and regressions; preview does not mark the case complete", async ({
  page,
}) => {
  await mockWorkspace(page);
  await page.goto(`/cases/${caseId}`);
  await expect(
    page.getByRole("heading", { name: "BK-2026-041" }),
  ).toBeVisible();
  await expect(
    page.getByRole("region", { name: "Returned draft summary" }),
  ).toContainText("New regressions");
  await expect(
    page.getByRole("region", { name: "Returned draft summary" }),
  ).toContainText("gross weight kg");
  await page
    .getByRole("button", { name: "Preview supported corrections" })
    .click();
  await expect(
    page.getByRole("heading", {
      name: "Would match if these changes are applied",
    }),
  ).toBeVisible();
  await expect(
    page.getByText("Changes required", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "I’ve shared this request" }),
  ).toHaveCount(0);
  await page.screenshot({
    path: "test-results/case-workspace.png",
    fullPage: true,
  });
});

test("failed check offers a retry and refreshes its outcome", async ({
  page,
}) => {
  await mockWorkspace(page);
  let retried = false;
  await page.route(`**/api/v1/cases/${caseId}`, (route) =>
    route.fulfill({
      json: retried
        ? detail
        : {
            ...detail,
            case: {
              ...detail.case,
              readiness: "failed",
              next_action: {
                kind: "retry",
                title: "Retry the document check",
                fields: [],
              },
            },
            current_job: {
              id: "failed-job",
              state: "failed",
              error_code: "PROCESSING_FAILED",
              attempt: 3,
            },
          },
    }),
  );
  await page.route("**/api/v1/jobs/failed-job/retry", (route) => {
    expect(route.request().method()).toBe("POST");
    retried = true;
    return route.fulfill({
      status: 202,
      json: { job_id: "failed-job", state: "queued" },
    });
  });
  await page.route("**/api/v1/jobs/failed-job", (route) =>
    route.fulfill({
      json: { id: "failed-job", state: "succeeded", result: {} },
    }),
  );
  await page.goto(`/cases/${caseId}`);
  await expect(
    page.getByRole("heading", { name: "Retry the document check" }),
  ).toBeVisible();
  await page
    .getByRole("region", { name: "Next action" })
    .getByRole("button", { name: "Continue" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Preview the correction request" }),
  ).toBeVisible();
  expect(retried).toBe(true);
});
