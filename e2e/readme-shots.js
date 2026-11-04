// Screenshots used in the README. Usage: node readme-shots.js <outdir>
const { chromium } = require("playwright");
const BASE = process.env.BASE_URL || "http://localhost:3000";
const out = process.argv[2];
(async () => {
  await fetch(`${BASE}/api/demo/reset`, { method: "POST" });
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1280, height: 800 }, deviceScaleFactor: 1.5 });
  await p.goto(BASE, { waitUntil: "networkidle" }); await p.waitForTimeout(1500);
  await p.screenshot({ path: `${out}/landing.png` });
  await p.goto(`${BASE}/app`, { waitUntil: "networkidle" });
  await p.getByRole("tab", { name: /Break it yourself/ }).click();
  await p.getByRole("button", { name: "Delete every customer", exact: true }).click();
  await p.getByRole("button", { name: "Rehearse it", exact: true }).click();
  await p.getByText(/containment: the damage happened only on the double/i).waitFor({ timeout: 60000 }); await p.waitForTimeout(1200);
  await p.screenshot({ path: `${out}/containment.png` });
  // The catch only an AI can make: a plan that passes every rule (needs a server with Vultr Serverless Inference).
  const health = await fetch(`${BASE}/api/health`).then((r) => r.json());
  if (health.inference_configured) {
    await p.getByRole("button", { name: "New" }).click();
    await p.getByRole("tab", { name: /Break it yourself/ }).click();
    await p.getByRole("button", { name: "Obvious refund plan (rules miss it)", exact: true }).click();
    await p.getByRole("button", { name: "Rehearse it", exact: true }).click();
    await p.getByText(/The AI verifier is investigating/).waitFor({ timeout: 60000 }); await p.waitForTimeout(8000);
    await p.getByText(/The AI verifier is investigating/).scrollIntoViewIfNeeded(); await p.mouse.wheel(0, -120); await p.waitForTimeout(400);
    await p.screenshot({ path: `${out}/ai-investigating.png` });
    await p.getByText(/Approve anyway|First approval/).first().waitFor({ timeout: 240000 }); await p.waitForTimeout(1200);
    await p.getByText(/^Verdict$/i).first().scrollIntoViewIfNeeded(); await p.mouse.wheel(0, -160); await p.waitForTimeout(400);
    await p.screenshot({ path: `${out}/ai-catch.png`, fullPage: false });
  }
  await p.getByRole("button", { name: "New" }).click();
  await p.getByRole("tab", { name: /Break it yourself/ }).click();
  await p.getByRole("button", { name: "✓ A correct refund plan", exact: true }).click();
  await p.getByRole("button", { name: "Rehearse it", exact: true }).click();
  await p.getByRole("button", { name: /Approve and apply/ }).click({ timeout: 240000 });  // the AI verifier investigates first
  await p.getByText("Applied for real").waitFor({ timeout: 60000 }); await p.waitForTimeout(1000);
  await p.screenshot({ path: `${out}/applied.png` });
  await p.goto(`${BASE}/history`, { waitUntil: "networkidle" }); await p.waitForTimeout(600);
  await p.screenshot({ path: `${out}/history.png` });
  await p.goto(`${BASE}/policy`, { waitUntil: "networkidle" }); await p.waitForTimeout(600);
  await p.screenshot({ path: `${out}/policy.png` });
  await b.close();
})().catch((e) => { console.error(e); process.exit(1); });
