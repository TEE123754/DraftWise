import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { mockWorkspace } from "./fixtures";

const root = path.resolve(__dirname, "..");

function sources(dir: string): string[] {
  return fs.readdirSync(path.join(root, dir), { withFileTypes: true }).flatMap((entry) => {
    const relative = path.join(dir, entry.name);
    if (entry.isDirectory()) return sources(relative);
    return /\.tsx$/.test(entry.name) ? [relative] : [];
  });
}

test("every clickable control goes through the shared Button: no raw <button> outside components/ui", () => {
  const offenders = [...sources("app"), ...sources("components")]
    .filter((file) => !file.replaceAll("\\", "/").startsWith("components/ui/"))
    .filter((file) => /<button[\s>]/.test(fs.readFileSync(path.join(root, file), "utf8")));
  expect(offenders, "use <Button> from @/components/ui/button instead").toEqual([]);
});

test("Button offers primary, secondary, ghost, danger and link variants", () => {
  const source = fs.readFileSync(path.join(root, "components/ui/button.tsx"), "utf8");
  for (const variant of ["primary", "secondary", "ghost", "danger", "link"]) expect(source).toMatch(new RegExp(`\\b${variant}:`));
});

async function openDashboard(page: import("@playwright/test").Page) {
  await mockWorkspace(page);
  await page.route("**/api/v1/dashboard", (route) =>
    route.fulfill({ json: { emails_total: 10, emails_classified: 8, emails_unresolved: 2, cases_open: 0, cases_checked: 0, cases_failed: 0, review_queue_size: 0, awaiting_revision: 0, jobs_in_progress: 0, last_updated: new Date().toISOString(), document_checks: 0, mismatches: 0, spam_count: 0, safety_held: 0, safety_assessed: 10, processing_failures: 0, drift_alerts_active: null } }),
  );
  await page.route("**/api/v1/dashboard/preferences", (route) => route.fulfill({ json: { sections: ["metrics"] } }));
  await page.route("**/api/v1/quality/monitor", (route) => route.fulfill({ json: { state: "baseline_required" } }));
  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
}

test("a tooltip gives a name and a one-line function on hover, keyboard focus and touch, and Escape closes it", async ({ page }) => {
  await openDashboard(page);
  const button = page.getByRole("button", { name: "Customize dashboard" });

  await button.hover();
  const tip = page.getByRole("tooltip");
  await expect(tip).toBeVisible();
  await expect(tip.locator("strong")).toHaveText("Customize dashboard");
  await expect(tip).toContainText("Choose which panels appear and in what order");
  await expect(button).toHaveAccessibleDescription(/Choose which panels appear/);

  await page.keyboard.press("Escape");
  await expect(tip).toHaveCount(0);

  await page.mouse.move(0, 0);
  await expect(page.getByRole("tooltip")).toHaveCount(0);
  await page.getByRole("link", { name: "Open inbox" }).focus();
  await button.focus();
  await page.keyboard.press("Shift+Tab");
  await page.keyboard.press("Tab"); // keyboard focus, not a pointer click
  await expect(page.getByRole("tooltip")).toContainText("Customize dashboard");
  await button.blur();
  await expect(page.getByRole("tooltip")).toHaveCount(0);

  await page.getByRole("button", { name: "Refresh" }).dispatchEvent("pointerdown", { pointerType: "touch" });
  await expect(page.getByRole("tooltip")).toContainText("Reloads the counts and the work queue");
});

test("sidebar destinations are boxed buttons that say what they open", async ({ page }) => {
  await openDashboard(page);
  const nav = page.getByRole("navigation", { name: "Workspace" });
  for (const name of ["Overview", "Inbox", "Cases", "Review", "Rules", "Analytics", "Alerts", "Trash"]) {
    const link = nav.getByRole("link", { name });
    await expect(link).toBeVisible();
    // A box: it has a visible border or a filled background, like every other button.
    const looksBoxed = await link.evaluate((element) => {
      const style = getComputedStyle(element);
      return parseFloat(style.borderTopWidth) > 0 || style.backgroundColor !== "rgba(0, 0, 0, 0)";
    });
    expect(looksBoxed, name).toBe(true);
  }
  await nav.getByRole("link", { name: "Inbox" }).hover();
  const tip = page.getByRole("tooltip");
  await expect(tip.locator("strong")).toHaveText("Inbox");
  await expect(tip).toContainText("Every email and what it needs next");
  // Drawn beside the link and fully on screen: the sidebar scrolls, but it does not clip the hint.
  const box = (await tip.boundingBox())!;
  const link = (await nav.getByRole("link", { name: "Inbox" }).boundingBox())!;
  expect(box.x).toBeGreaterThanOrEqual(link.x + link.width);
  expect(box.width).toBeGreaterThan(100);
  const shown = await tip.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    return document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2) === element || element.contains(document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2));
  });
  expect(shown).toBe(true);
});
