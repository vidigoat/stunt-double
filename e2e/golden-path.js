// End-to-end: drive the real UI like a judge would. Usage: BASE_URL=http://localhost:3000 node golden-path.js
const { chromium } = require("playwright");
const assert = require("assert");
const BASE = process.env.BASE_URL || "http://localhost:3000";
const SHOTS = process.env.SHOTS_DIR;

async function step(name, fn) {
  const t = Date.now();
  await fn();
  console.log(`  ✓ ${name} (${Date.now() - t} ms)`);
}

(async () => {
  const browser = await chromium.launch();
  const errors = [];
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, ignoreHTTPSErrors: true });
  const page = await ctx.newPage();
  page.on("pageerror", (e) => errors.push(e.message));
  await fetch(`${BASE}/api/demo/reset`, { method: "POST" });

  await step("landing: value is visible in the first screen", async () => {
    await page.goto(BASE, { waitUntil: "networkidle" });
    await page.getByRole("heading", { name: /Let the double/ }).first().waitFor();
    assert.ok(await page.getByText("$37,404").first().isVisible(), "hero shows the $37,404 catch");
    if (SHOTS) await page.screenshot({ path: `${SHOTS}/e2e-landing.png` });
  });

  await step("containment: deleting every customer hits only the double", async () => {
    await page.goto(`${BASE}/app`, { waitUntil: "networkidle" });
    await page.getByRole("tab", { name: /Break it yourself/ }).click();
    await page.getByRole("button", { name: "Delete every customer", exact: true }).click();
    await page.getByRole("button", { name: "Rehearse it", exact: true }).click();
    await page.getByText(/containment: the damage happened only on the double/i).waitFor({ timeout: 60000 });
    assert.ok(await page.getByRole("button", { name: /Blocked by policy/ }).isDisabled(), "approval is locked");
    const prod = await fetch(`${BASE}/api/business`).then((r) => r.json());
    assert.strictEqual(prod.counts.customers, 1300, "production untouched");
    if (SHOTS) await page.screenshot({ path: `${SHOTS}/e2e-containment.png`, fullPage: true });
  });

  await step("approve + apply: a correct plan really refunds 104 customers", async () => {
    await page.getByRole("button", { name: "New" }).click();
    await page.getByRole("tab", { name: /Break it yourself/ }).click();
    await page.getByRole("button", { name: "✓ A correct refund plan", exact: true }).click();
    await page.getByRole("button", { name: "Rehearse it", exact: true }).click();
    const approve = page.getByRole("button", { name: /Approve and apply/ });
    await approve.waitFor({ timeout: 60000 });
    await approve.click();
    await page.getByText("Applied for real").waitFor({ timeout: 60000 });
    const ledger = await fetch(`${BASE}/api/beanpay/ledger`).then((r) => r.json());
    assert.strictEqual(ledger.count, 104);
    assert.strictEqual(ledger.total_cents, 513600);
  });

  await step("audit trail: history shows the applied run with a plan fingerprint", async () => {
    await page.goto(`${BASE}/history`, { waitUntil: "networkidle" });
    await page.getByText("applied", { exact: true }).first().waitFor();
    await page.getByText("blocked by policy").first().waitFor();
  });

  await step("policy page loads the rules", async () => {
    await page.goto(`${BASE}/policy`, { waitUntil: "networkidle" });
    await page.getByText("Block risky refunds").waitFor();
  });

  await step("phone width: no horizontal scrolling", async () => {
    const m = await browser.newPage({ viewport: { width: 390, height: 844 }, ignoreHTTPSErrors: true });
    for (const path of ["/", "/app", "/history", "/policy", "/ledger"]) {
      await m.goto(`${BASE}${path}`, { waitUntil: "networkidle" });
      const w = await m.evaluate(() => document.documentElement.scrollWidth);
      assert.ok(w <= 391, `${path} scrolls sideways (${w}px)`);
    }
  });

  assert.deepStrictEqual(errors, [], `page errors: ${errors.join(" | ")}`);
  await browser.close();
  console.log("E2E OK");
})().catch((e) => { console.error(e); process.exit(1); });
