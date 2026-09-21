import { test, expect } from "@playwright/test";

test("marketing assets, destination routes, keyboard navigation and reduced motion work", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(
    page.getByRole("link", { name: "Verify Email", exact: true }),
  ).toHaveAttribute("href", "/demo");
  await expect(
    page.getByRole("link", { name: "Try Demo", exact: true }),
  ).toHaveAttribute("href", "/demo");
  for (const image of await page.locator(".mw-scene img").all()) {
    await expect(image).toBeVisible();
    await expect
      .poll(() => image.evaluate((i: HTMLImageElement) => i.naturalWidth))
      .toBeGreaterThan(0);
  }
  await expect(page.locator(".mw-carriers")).toHaveCount(0);
  await expect(page.locator("main")).not.toContainText("Rules run first");
  await expect(page.locator("main")).not.toContainText("AI is optional");
  await expect(page.locator("main")).not.toContainText("in Seconds");
  await expect(page.locator("main")).not.toContainText(
    "forward from your inbox",
  );
  const verify = page.getByRole("link", { name: "Verify Email", exact: true });
  await verify.focus();
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Try Demo", exact: true }),
  ).toBeFocused();
  await page.emulateMedia({ reducedMotion: "reduce" });
  const scene = page.locator(".mw-scene");
  await scene.hover();
  expect(
    await page
      .locator(".mw-vessel")
      .evaluate((el) => getComputedStyle(el).transform),
  ).toBe("none");
  for (const path of [
    "/demo",
    "/dashboard",
    "/inbox",
    "/cases",
    "/pricing",
    "/sign-in",
  ]) {
    expect((await page.request.get(path)).status()).toBe(200);
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator("#workflow").scrollIntoViewIfNeeded();
  await expect(
    page.getByRole("heading", {
      name: "AI Verification Workflow",
      exact: true,
    }),
  ).toBeVisible();
  await page.screenshot({
    path: "../artifacts/ui/marketing-workflow-mobile.png",
  });
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.getByText("Menu", { exact: true }).click();
  await page
    .getByRole("navigation", { name: "Mobile navigation" })
    .getByRole("link", { name: "Features", exact: true })
    .click();
  await expect(page).toHaveURL(/#features$/);
  expect(errors).toEqual([]);
});
