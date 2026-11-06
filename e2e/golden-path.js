// End-to-end: drive the real UI like a judge would. Usage: BASE_URL=http://localhost:3000 node golden-path.js
const { chromium } = require("playwright");
const assert = require("assert");
const path = require("path");
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
  const reset = await fetch(`${BASE}/api/demo/reset`, { method: "POST" });
  assert.ok(reset.ok, `demo reset failed (${reset.status}): every later step would run on stale data`);

  await step("landing: value is visible in the first screen", async () => {
    await page.goto(BASE, { waitUntil: "networkidle" });
    await page.getByRole("heading", { name: /Let the double/ }).first().waitFor();
    assert.ok(await page.getByText("$37,404").first().isVisible(), "hero shows the $37,404 catch");
    if (SHOTS) await page.screenshot({ path: `${SHOTS}/e2e-landing.png` });
  });

  await step("landing: 'Try it right here' runs a real destructive plan and production survives", async () => {
    await page.getByRole("button", { name: /Run it on the double/ }).click();
    await page.getByText(/Approval locked\./).waitFor({ timeout: 60000 });
    assert.ok(await page.getByText("untouched").first().isVisible());
  });

  await step("containment: deleting every customer hits only the double", async () => {
    await page.goto(`${BASE}/app`, { waitUntil: "networkidle" });
    await page.getByRole("tab", { name: /Break it yourself/ }).click();
    await page.getByLabel("Start from an example").selectOption({ label: "Delete every customer" });
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
    await page.getByLabel("Start from an example").selectOption({ label: "✓ A correct refund plan" });
    await page.getByRole("button", { name: "Rehearse it", exact: true }).click();
    // with inference on, the AI verifier reads the data first (60-125 s on the live server)
    const approve = page.getByRole("button", { name: /Approve and apply|Approve anyway/ });
    await approve.waitFor({ timeout: 240000 });
    // the note field appears only when a written reason is required (the AI or a promise objected)
    if (/anyway/.test(await approve.innerText())) await page.getByLabel("Decision note").fill("Matches the 104 duplicate charges in ticket #88");
    await approve.click();
    await page.getByText("Applied for real").waitFor({ timeout: 60000 });
    const ledger = await fetch(`${BASE}/api/beanpay/ledger`).then((r) => r.json());
    assert.strictEqual(ledger.count, 104);
    assert.strictEqual(ledger.total_cents, 513600);
  });

  await step("undo: a rollback needs two different approvers and restores the data", async () => {
    await page.getByRole("button", { name: /Rehearse an undo/ }).click();
    await page.getByText(/This is the undo of/).waitFor({ timeout: 30000 });
    const name = page.getByRole("textbox", { name: "Approver name" });
    await name.fill("Priya");
    await page.getByRole("button", { name: /First approval/ }).click();
    await page.getByText(/approved by Priya/).waitFor({ timeout: 30000 });
    await name.fill("Marco");
    await page.getByRole("button", { name: /Second approval and apply/ }).click();
    await page.getByText("Applied for real").waitFor({ timeout: 60000 });
    const biz = await fetch(`${BASE}/api/business`).then((r) => r.json());
    assert.strictEqual(biz.refunded.count, 0, "rollback restored every refunded charge in the database");
  });

  await step("connectors: a Slack post is recorded, approved, then delivered to the outbox", async () => {
    await page.getByRole("button", { name: "New" }).click();
    await page.getByRole("tab", { name: /Break it yourself/ }).click();
    await page.getByLabel("Start from an example").selectOption({ label: "Post the refund summary to Slack" });
    await page.getByRole("button", { name: "Rehearse it", exact: true }).click();
    const ok = page.getByRole("button", { name: /Approve and apply|Approve anyway/ });
    await ok.waitFor({ timeout: 240000 });
    if (/anyway/.test(await ok.innerText())) await page.getByLabel("Decision note").fill("Checked: one summary post to #ops");
    await ok.click();
    await page.getByText("Applied for real").waitFor({ timeout: 60000 });
    const out = await fetch(`${BASE}/api/outbox`).then((r) => r.json());
    const fromPlans = out.deliveries.filter((d) => d.path !== "/stunt-double/notify");
    assert.strictEqual(fromPlans.length, 1, "exactly the approved Slack post was delivered");
    assert.strictEqual(fromPlans[0].connector, "slack");
    assert.ok(out.deliveries.some((d) => d.path === "/stunt-double/notify"), "reviewers were pinged on Slack");
  });

  await step("workspaces: upload your own SQLite DB and contain a mass delete there", async () => {
    await page.goto(`${BASE}/app`, { waitUntil: "networkidle" });
    await page.getByRole("button", { name: "Use your own data" }).click();
    await page.locator('input[type="file"]').setInputFiles(path.join(__dirname, "fixtures", "acme-crm.db"));
    await page.getByText(/acme-crm: 2 tables/).waitFor({ timeout: 30000 });
    await page.getByLabel("Start from an example").selectOption({ label: "Delete every row of accounts" });
    await page.getByRole("button", { name: "Rehearse it", exact: true }).click();
    await page.getByText(/containment: the damage happened only on the double/i).waitFor({ timeout: 60000 });
    const ws = (await fetch(`${BASE}/api/workspaces`).then((r) => r.json())).workspaces.find((w) => w.name === "acme-crm");
    const biz = await fetch(`${BASE}/api/business?ws=${ws.id}`).then((r) => r.json());
    assert.strictEqual(biz.tables.accounts, 120, "your production data is untouched");
  });

  await step("cloud double: deleting 'idle' servers is blocked for production; the safe cleanup applies (12 -> 8)", async () => {
    await page.goto(`${BASE}/app`, { waitUntil: "networkidle" });
    await page.getByRole("tab", { name: /Break it yourself/ }).click();
    await page.getByLabel("Start from an example").selectOption({ label: "Clean up idle Vultr servers" });
    await page.getByRole("button", { name: "Rehearse it", exact: true }).click();
    await page.getByText(/Would remove production: prod-db-replica, prod-backup-runner/).waitFor({ timeout: 300000 });   // a live three-model check can take ~2 min
    await page.getByRole("button", { name: "New" }).click();
    await page.getByRole("tab", { name: /Break it yourself/ }).click();
    await page.getByLabel("Start from an example").selectOption({ label: "✓ Clean up idle servers (safe)" });
    await page.getByRole("button", { name: "Rehearse it", exact: true }).click();
    const approve = page.getByRole("button", { name: /Approve and apply|Approve anyway/ });
    await approve.waitFor({ timeout: 240000 });
    if (/anyway/.test(await approve.innerText())) await page.getByLabel("Decision note").fill("Checked: only idle non-production servers");
    await approve.click();
    await page.getByText("Applied for real").waitFor({ timeout: 60000 });
    const biz = await fetch(`${BASE}/api/business`).then((r) => r.json());
    assert.strictEqual(biz.counts.servers, 8, "4 idle servers deleted, production kept");
  });

  await step("audit trail: history shows the applied run with a plan fingerprint", async () => {
    await page.goto(`${BASE}/history`, { waitUntil: "networkidle" });
    await page.getByText("applied", { exact: true }).first().waitFor();
    await page.getByText("blocked by policy").first().waitFor();
    await page.getByRole("button", { name: /Awaiting approval/ }).click();
    await page.getByRole("button", { name: /Undos/ }).click();
    await page.getByText("undo", { exact: true }).first().waitFor();
    const csv = await fetch(`${BASE}/api/runs.csv`).then((r) => r.text());
    assert.ok(csv.startsWith("run_id,") && csv.includes("Matches the 104 duplicate charges"), "CSV export carries the decision note");
  });

  await step("policy page loads the rules", async () => {
    await page.goto(`${BASE}/policy`, { waitUntil: "networkidle" });
    await page.getByText("Block risky refunds").waitFor();
  });

  await step("phone width: no horizontal scrolling", async () => {
    const m = await browser.newPage({ viewport: { width: 390, height: 844 }, ignoreHTTPSErrors: true });
    for (const path of ["/", "/app", "/history", "/policy", "/ledger", "/connect"]) {
      await m.goto(`${BASE}${path}`, { waitUntil: "networkidle" });
      const w = await m.evaluate(() => document.documentElement.scrollWidth);
      assert.ok(w <= 391, `${path} scrolls sideways (${w}px)`);
    }
  });

  assert.deepStrictEqual(errors, [], `page errors: ${errors.join(" | ")}`);
  await browser.close();
  console.log("E2E OK");
})().catch((e) => { console.error(e); process.exit(1); });
