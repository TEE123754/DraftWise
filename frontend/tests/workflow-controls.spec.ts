import { test,expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { mockWorkspace } from "./fixtures";

test("dashboard section preferences save and persist while the queue stays visible",async({page})=>{
  await mockWorkspace(page);
  let sections=["metrics","guidance","quality"];
  await page.route("**/api/v1/dashboard",r=>r.fulfill({json:{emails_total:10,emails_classified:8,emails_unresolved:2,cases_open:1,cases_checked:0,cases_failed:0,review_queue_size:1,awaiting_revision:0,jobs_in_progress:0,last_updated:new Date().toISOString(),document_checks:1,mismatches:1,spam_count:1,safety_held:0,safety_assessed:10,processing_failures:0,drift_alerts_active:null}}));
  await page.route("**/api/v1/dashboard/preferences",r=>{if(r.request().method()==="POST")sections=r.request().postDataJSON().sections;return r.fulfill({json:{sections}});});
  await page.route("**/api/v1/quality/monitor",r=>r.fulfill({json:{state:"baseline_required"}}));
  await page.goto("/dashboard");
  await page.getByRole("button",{name:"Customize dashboard"}).click();
  await page.getByRole("checkbox",{name:"Review checklist"}).uncheck();
  await page.getByRole("button",{name:"Move Model quality and drift up"}).click();
  await page.getByRole("button",{name:"Save view"}).click();
  await expect(page.getByRole("status")).toContainText("Dashboard view saved");
  await page.reload();
  await expect(page.getByRole("heading",{name:"Cases needing action"})).toBeVisible();
  await expect(page.getByRole("region",{name:"Review checklist"})).toHaveCount(0);
  expect(sections).toEqual(["quality","metrics"]);
  expect((await new AxeBuilder({page}).analyze()).violations).toEqual([]);
});
