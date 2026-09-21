import {test,expect} from "@playwright/test";
import {caseId,detail,mockWorkspace} from "./fixtures";

test("review requires evidence and a reason, then submits a versioned correction",async({page})=>{
  await mockWorkspace(page);
  await page.route("**/attachments/*/preview",route=>route.fulfill({json:{blocks:[{id:"block-1",text_content:"Gross weight: 22000 KG",locator:{line:1}}]}}));
  let saved=false;
  await page.route(`**/cases/${caseId}/extractions/si-1/review`,route=>{
    const body=route.request().postDataJSON();
    expect(body.expected_version).toBe(3);
    expect(body.value.evidence[0].quote).toBe("Gross weight: 22000 KG");
    expect(body.reason).toBe("Confirmed against the source");
    saved=true;return route.fulfill({status:202,json:{job_id:"review-job"}});
  });
  await page.route(`**/api/v1/cases/${caseId}`,route=>route.fulfill({json:saved?{...detail,case:{...detail.case,version:4,readiness:"checking"}}:detail}));
  await page.goto(`/cases/${caseId}`);
  await page.getByRole("button",{name:"gross weight kg",exact:true}).click();
  await page.getByText("Review extracted value",{exact:true}).first().click();
  const form=page.locator("form").filter({has:page.getByRole("button",{name:"Save review and recompare"})}).first();
  await expect(form.getByRole("button")).toBeDisabled();
  await form.getByLabel("Reason for this review").fill("Confirmed against the source");
  await form.getByLabel("Gross weight: 22000 KG").check();
  await form.getByRole("button").click();
  await expect(page.getByText("Review extracted value",{exact:true})).toHaveCount(0);
  expect(saved).toBe(true);
});
