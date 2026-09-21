// Optional smoke test: requires the real local API, worker and frontend.
const { chromium } = require("@playwright/test");

async function main() {
  const browser = await chromium.launch({ channel: "msedge", headless: true });
  try {
    const page = await browser.newPage();
    await page.goto("http://localhost:3000/demo");
    await page.getByRole("button", { name: "Start the demo" }).click();
    await page.getByText("Private sample workspace").waitFor({ timeout: 90000 });
    await page.getByRole("link", { name: "Inbox", exact: true }).click();
    await page.getByText("email_001", { exact: false }).first().waitFor();
    await page.getByRole("button", { name: "End demo", exact: true }).click();
    await page.getByRole("button", { name: "Start the demo" }).waitFor();
    console.log("PASS: real browser demo entry, supplied inbox and session exit.");
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
