import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { mockWorkspace } from "./fixtures";

const METRICS = {
  sample_size: 60,
  rules: { correct: 29, abstained: 31, wrong: 0, accuracy: 0.4833, accuracy_when_decided: 1 },
  ai: {
    asked: 60, correct: 57, wrong: 0, unusable: 3, accuracy: 0.95, unusable_rate: 0.05,
    latency_seconds: { mean: 36.8, p95: 91.6, max: 95.7 },
  },
  combined: { correct: 58, undecided: 2, accuracy: 0.9667 },
  per_category: {
    BL_COMPARISON: { total: 24, rules_correct: 14, ai_correct: 24 },
    SI_REQUEST: { total: 10, rules_correct: 3, ai_correct: 10 },
    INVOICE_QUERY: { total: 10, rules_correct: 3, ai_correct: 9 },
    GENERAL: { total: 8, rules_correct: 1, ai_correct: 6 },
    SPAM: { total: 8, rules_correct: 8, ai_correct: 8 },
  },
};
const RUN = {
  id: "run-1", source: "heldout_cached", status: "complete", sample_size: 60, calls_made: 0, metrics: METRICS,
  error: null, created_at: "2026-09-21T09:00:00Z", finished_at: "2026-09-21T09:00:01Z",
};
const usage = { scope: "day", used: 4, budget: 30, remaining: 26 };

async function open(page: Page, overview: object, { admin = false } = {}) {
  await mockWorkspace(page);
  if (admin)
    await page.route("http://127.0.0.1:54321/rest/v1/memberships**", (route) =>
      route.fulfill({ json: [{ workspace_id: "20000000-0000-4000-8000-000000000001", role: "admin", workspaces: { name: "Test Shipping Team" } }] }),
    );
  // The older benchmark report is not shipped everywhere; the AI score must not depend on it.
  await page.route("**/api/v1/quality/benchmark", (route) =>
    route.fulfill({ status: 404, json: { error: { code: "BENCHMARK_UNAVAILABLE", message: "No benchmark report is available in this environment." } } }),
  );
  const posts: unknown[] = [];
  await page.route("**/api/v1/quality/ai-classifier/evaluate", (route) => {
    posts.push(route.request().postDataJSON());
    return route.fulfill({ json: { ...RUN, status: "running", source: "heldout_live" } });
  });
  await page.route("**/api/v1/quality/ai-classifier", (route) => route.fulfill({ json: overview }));
  await page.goto("/analytics");
  return posts;
}

const panel = (page: Page) => page.getByRole("region", { name: "AI classifier score" });

test("the AI classifier score sits beside the rules score, with sample size and the caveats that matter", async ({ page }) => {
  await open(page, { available: true, message: null, provider_configured: true, latest: RUN, usage, plan: { sample_size: 60, answered: 60, to_call: 0, estimated_seconds: 0 } });
  const scores = panel(page);
  await expect(scores.getByText("Rules alone", { exact: true }).locator("..")).toContainText("48.3%");
  await expect(scores.getByText("Rules alone", { exact: true }).locator("..")).toContainText("29 of 60 right, 31 left undecided");
  await expect(scores.getByText("AI alone", { exact: true }).locator("..")).toContainText("95.0%");
  await expect(scores.getByText("AI alone", { exact: true }).locator("..")).toContainText("57 of 60 right, 3 unusable answers");
  await expect(scores.getByText("Rules, then AI", { exact: true }).locator("..")).toContainText("96.7%");
  await expect(scores).toContainText("60 emails");
  await expect(scores).toContainText("5.0%"); // unusable-output rate
  await expect(scores).toContainText("36.8 s / 91.6 s"); // mean and p95 latency
  await expect(scores).toContainText("no new calls");
  await expect(scores).toContainText("a guide, not a guarantee");
  await expect(scores.getByRole("row", { name: /General 8 1 6/ })).toBeVisible();
  await expect(scores.getByTestId("ai-usage")).toHaveText("AI calls used: 4 / 30 today");
  const violations = (await new AxeBuilder({ page }).analyze()).violations;
  expect(violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);
});

test("a live evaluation is never started without the exact call count being confirmed", async ({ page }) => {
  const posts = await open(page, { available: true, message: null, provider_configured: true, latest: null, usage, plan: { sample_size: 60, answered: 55, to_call: 5, estimated_seconds: 65 } }, { admin: true });
  const scores = panel(page);
  await expect(scores).toContainText("No score has been saved yet");
  await scores.getByRole("button", { name: "Run live evaluation" }).click();

  const confirm = scores.getByRole("group", { name: "Confirm live evaluation" });
  await expect(confirm).toContainText("5 times");
  await expect(confirm).toContainText("uses 5 of the 26 calls left today");
  const start = confirm.getByRole("button", { name: "Start 5 AI calls" });
  await expect(start).toBeDisabled();
  await confirm.getByRole("checkbox", { name: /uses 5 AI calls/ }).check();
  await start.click();
  await expect.poll(() => posts).toEqual([{ mode: "live", confirm_calls: 5 }]);
});

test("nothing can be started when the budget is too small, nothing is left to ask, or the user is not an administrator", async ({ page }) => {
  await open(page, { available: true, message: null, provider_configured: true, latest: RUN, usage: { scope: "day", used: 28, budget: 30, remaining: 2 }, plan: { sample_size: 60, answered: 55, to_call: 5, estimated_seconds: 65 } }, { admin: true });
  await panel(page).getByRole("button", { name: "Run live evaluation" }).click();
  const confirm = panel(page).getByRole("group", { name: "Confirm live evaluation" });
  await expect(confirm.getByRole("alert")).toContainText("not enough calls left");
  await confirm.getByRole("checkbox").check();
  await expect(confirm.getByRole("button", { name: /Start 5 AI calls/ })).toBeDisabled();
});

test("with every email already answered a live run is disabled, and a non-administrator cannot spend anything", async ({ page }) => {
  await open(page, { available: true, message: null, provider_configured: true, latest: RUN, usage, plan: { sample_size: 60, answered: 60, to_call: 0, estimated_seconds: 0 } }, { admin: true });
  await expect(panel(page).getByRole("button", { name: "Run live evaluation" })).toBeDisabled();
  await expect(panel(page).getByRole("button", { name: "Refresh score (no AI calls)" })).toBeEnabled();
});

test("a reviewer sees the score but the buttons that run anything are disabled", async ({ page }) => {
  await open(page, { available: true, message: null, provider_configured: true, latest: RUN, usage, plan: { sample_size: 60, answered: 55, to_call: 5, estimated_seconds: 65 } });
  await expect(panel(page).getByText("Rules alone", { exact: true })).toBeVisible();
  await expect(panel(page).getByRole("button", { name: "Refresh score (no AI calls)" })).toBeDisabled();
  await expect(panel(page).getByRole("button", { name: "Run live evaluation" })).toBeDisabled();
});

test("when the labelled set is not shipped the panel says so instead of showing invented numbers", async ({ page }) => {
  await open(page, { available: false, message: "The labelled evaluation set is not shipped in this environment.", provider_configured: false, latest: null, usage, plan: null });
  await expect(panel(page)).toContainText("not shipped in this environment");
  await expect(panel(page).getByText("AI alone", { exact: true })).toHaveCount(0);
});
