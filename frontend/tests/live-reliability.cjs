const { chromium } = require("@playwright/test");
const fs = require("node:fs");

(async () => {
  fs.mkdirSync("../artifacts/ui", {recursive:true});
  const browser = await chromium.launch({channel:"msedge",headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1000}});
    const errors = [];
    page.on("pageerror", e => errors.push(e.message));
    const response = await page.goto("http://localhost:3000/");
    if (response.status() !== 200) throw new Error("Homepage not 200");
    await page.getByRole("heading", {level:1}).waitFor();
    await page.locator("img").first().evaluate(img => img.decode());
    await page.screenshot({path:"../artifacts/ui/home-desktop.png",fullPage:true});
    await page.setViewportSize({width:390,height:844});
    await page.screenshot({path:"../artifacts/ui/home-mobile.png",fullPage:true});
    if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)) throw new Error("Mobile overflow");
    await page.setViewportSize({width:1440,height:1000});
    await page.goto("http://localhost:3000/demo");
    await page.getByRole("button", {name:"Start the demo"}).click();
    await page.getByRole("heading", {name:"Overview",exact:true}).waitFor({timeout:90000});
    await page.getByText("Emails imported", {exact:true}).waitFor({timeout:30000});
    await page.getByRole("link", {name:"Cases",exact:true}).click();
    await page.getByRole("heading", {name:"Attention queue"}).waitFor();
    await page.getByRole("button", {name:"Open Ask DraftWise assistant"}).click();
    await page.getByRole("button", {name:"What needs my attention?"}).click();
    await page.getByText(/Your workspace has 520 emails/).waitFor({timeout:30000});
    await page.keyboard.press("Escape");
    await page.getByRole("button", {name:"End demo",exact:true}).click();
    await page.getByRole("button", {name:"Start the demo"}).waitFor();
    if (errors.length) throw new Error(errors.join("; "));
    console.log("PASS: live homepage/mobile, demo summary, cases, assistant and session exit; no page errors.");
  } finally { await browser.close(); }
})().catch(error => { console.error(error.message); process.exitCode=1; });
