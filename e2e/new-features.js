// End-to-end for the Nov 5 features. Usage: BASE_URL=https://... node new-features.js
// Instant (reused, labelled) AI verdict with a live re-check; real-fleet import refuses a bad key without echoing it;
// SQL export of a rehearsal; the Consequence Engine's demo moment (contract, cut to 104, signed evidence that verifies).
// Needs the judge presets to have been checked live once (the verdict cache).
const { chromium } = require("playwright");
const assert = require("assert");
const BASE = process.env.BASE_URL || "http://localhost:3000";

async function step(name, fn) {
  const t = Date.now();
  await fn();
  console.log(`  ✓ ${name} (${Date.now() - t} ms)`);
}

(async () => {
  const browser = await chromium.launch();
  const errors = [];
  const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 }, ignoreHTTPSErrors: true })).newPage();
  page.on("pageerror", (e) => errors.push(e.message));
  const health = await fetch(`${BASE}/api/health`).then((r) => r.json());

  if (health.inference_configured) {
    await step("instant verdict: the refund catch comes back labelled, in seconds", async () => {
      await page.goto(`${BASE}/app`, { waitUntil: "networkidle" });
      await page.getByRole("tab", { name: /Break it yourself/ }).click();
      await page.getByRole("button", { name: "Obvious refund plan (rules miss it)", exact: true }).click();
      const t = Date.now();
      await page.getByRole("button", { name: "Rehearse it", exact: true }).click();
      await page.getByText(/Instant verdict: the same request/).waitFor({ timeout: 60000 });
      assert.ok(Date.now() - t < 30000, `took ${Date.now() - t} ms`);
      await page.getByText(/640/).first().waitFor();
      assert.ok(await page.getByRole("button", { name: /Re-check live/ }).isVisible());
    });
  }

  await step("SQL export: the correct refund plan downloads as 104 guarded UPDATEs", async () => {
    await page.goto(`${BASE}/app`, { waitUntil: "networkidle" });
    await page.getByRole("tab", { name: /Break it yourself/ }).click();
    await page.getByRole("button", { name: "✓ A correct refund plan", exact: true }).click();
    await page.getByRole("button", { name: "Rehearse it", exact: true }).click();
    const link = page.getByRole("link", { name: /Export as SQL/ });
    await link.waitFor({ timeout: 240000 });
    const sql = await fetch(`${BASE}${await link.getAttribute("href")}`).then((r) => r.text());
    assert.strictEqual(sql.split("\n").filter((l) => l.startsWith("UPDATE")).length, 104);
    assert.ok(sql.includes("BEGIN;") && sql.includes("COMMIT;"));
  });

  await step("your Vultr fleet: a bad key is refused and never echoed", async () => {
    await page.goto(`${BASE}/app`, { waitUntil: "networkidle" });
    await page.getByRole("button", { name: /Your Vultr fleet/ }).click();
    const fake = "ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ";
    await page.getByLabel("Vultr API key").fill(fake);
    await page.getByRole("button", { name: "Import", exact: true }).click();
    const msg = await page.getByText(/Vultr rejected that key/).first().textContent({ timeout: 30000 });
    assert.ok(!msg.includes(fake), "the error never echoes the key");
  });

  if (health.inference_configured) {
    await step("the engine: a wrong plan becomes the right one, and the record verifies", async () => {
      await page.goto(`${BASE}/app`, { waitUntil: "networkidle" });
      await page.getByRole("button", { name: /Watch a wrong plan become/ }).click();
      await page.waitForURL(/run=/, { timeout: 60000 });
      const rid = new URL(page.url()).searchParams.get("run");
      await page.getByText("Consequence engine · intent contract").first().waitFor({ timeout: 180000 });
      const keep = page.getByRole("button", { name: /Keep just the 104/ });
      await keep.waitFor({ timeout: 180000 });
      await keep.click();
      let run;
      for (let i = 0; i < 240; i++) {
        run = await fetch(`${BASE}/api/runs/${rid}`).then((r) => r.json());
        if (run.attempts.length > 1 && run.status === "review" && run.decision) break;
        await new Promise((r) => setTimeout(r, 1000));
      }
      const sub = run.attempts.at(-1).consequences;
      assert.strictEqual(sub.payments.count, 104, "exactly the 104 real double charges");
      assert.strictEqual(sub.payments.total_cents, 513600);
      assert.ok((sub.contract?.promises ?? []).every((p) => p.status === "kept" || p.status === "met"), "the subset keeps every promise");
      assert.strictEqual(run.decision.decision, "approve", run.decision.headline);
      const ev = await fetch(`${BASE}/api/runs/${rid}/evidence`).then((r) => r.json());
      const ok = await fetch(`${BASE}/api/evidence/verify`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(ev) }).then((r) => r.json());
      assert.ok(ok.ok, `evidence verifies: ${ok.reason}`);
      ev.chain.entries.find((e) => e.kind === "rehearsal").body.measured.payments.total_cents += 1;
      const bad = await fetch(`${BASE}/api/evidence/verify`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(ev) }).then((r) => r.json());
      assert.ok(!bad.ok, "one changed cent breaks it");
    });
  }

  assert.deepStrictEqual(errors, [], `page errors: ${errors.join(" | ")}`);
  await browser.close();
  console.log("NEW FEATURES OK");
})().catch((e) => { console.error(e); process.exit(1); });
