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
  await p.getByLabel("Start from an example").selectOption({ label: "Delete every customer" });
  await p.getByRole("button", { name: "Rehearse it", exact: true }).click();
  await p.getByText(/containment: the damage happened only on the double/i).waitFor({ timeout: 60000 }); await p.waitForTimeout(1200);
  await p.screenshot({ path: `${out}/containment.png` });
  // The catch only an AI can make: a plan that passes every rule (needs a server with Vultr Serverless Inference).
  const health = await fetch(`${BASE}/api/health`).then((r) => r.json());
  if (health.inference_configured) {
    await p.getByRole("button", { name: "New" }).click();
    await p.getByRole("tab", { name: /Break it yourself/ }).click();
    await p.getByLabel("Start from an example").selectOption({ label: "Obvious refund plan (rules miss it)" });
    await p.getByRole("button", { name: "Rehearse it", exact: true }).click();
    await p.getByText(/The AI verifier is investigating/).waitFor({ timeout: 60000 }); await p.waitForTimeout(8000);
    await p.getByText(/The AI verifier is investigating/).scrollIntoViewIfNeeded(); await p.mouse.wheel(0, -120); await p.waitForTimeout(400);
    await p.screenshot({ path: `${out}/ai-investigating.png` });
    await p.getByText(/Approve anyway|First approval/).first().waitFor({ timeout: 240000 }); await p.waitForTimeout(1200);
    await p.getByText(/^Verdict$/i).first().scrollIntoViewIfNeeded(); await p.mouse.wheel(0, -160); await p.waitForTimeout(400);
    await p.screenshot({ path: `${out}/ai-catch.png`, fullPage: false });
  }
  // Browser double: a real Chromium in the sandbox; the filmstrip of what the agent did on screen.
  await p.getByRole("button", { name: "New" }).click();
  await p.getByRole("tab", { name: /Break it yourself/ }).click();
  await p.getByLabel("Start from an example").selectOption({ label: "Cancel the duplicate subscription (in a browser)" });
  await p.getByRole("button", { name: "Rehearse it", exact: true }).click();
  await p.getByText(/The agent in a browser/).waitFor({ timeout: 120000 });
  if (health.inference_configured) await p.getByText(/AI vision check:/).waitFor({ timeout: 240000 });
  await p.waitForTimeout(1500);
  await p.getByText(/The agent in a browser/).scrollIntoViewIfNeeded(); await p.mouse.wheel(0, -60); await p.waitForTimeout(500);
  await p.screenshot({ path: `${out}/browser.png` });
  // Cloud double: the fleet as server cards.
  await p.getByRole("button", { name: "New" }).click();
  await p.getByRole("tab", { name: /Break it yourself/ }).click();
  await p.getByLabel("Start from an example").selectOption({ label: "Clean up idle Vultr servers" });
  await p.getByRole("button", { name: "Rehearse it", exact: true }).click();
  await p.getByText(/Vultr fleet · the double/).waitFor({ timeout: 120000 }); await p.waitForTimeout(1500);
  await p.getByText(/Vultr fleet · the double/).scrollIntoViewIfNeeded(); await p.mouse.wheel(0, -60); await p.waitForTimeout(500);
  await p.screenshot({ path: `${out}/cloud.png` });
  await p.getByRole("button", { name: "New" }).click();
  await p.getByRole("tab", { name: /Break it yourself/ }).click();
  await p.getByLabel("Start from an example").selectOption({ label: "✓ A correct refund plan" });
  await p.getByRole("button", { name: "Rehearse it", exact: true }).click();
  await p.getByRole("button", { name: /Approve and apply/ }).click({ timeout: 240000 });  // the AI verifier investigates first
  await p.getByText("Applied for real").waitFor({ timeout: 60000 }); await p.waitForTimeout(1000);
  await p.screenshot({ path: `${out}/applied.png` });
  await p.goto(`${BASE}/history`, { waitUntil: "networkidle" }); await p.waitForTimeout(600);
  await p.screenshot({ path: `${out}/history.png` });
  await p.goto(`${BASE}/control`, { waitUntil: "networkidle" }); await p.waitForTimeout(2500);
  await p.screenshot({ path: `${out}/control.png` });
  await p.goto(`${BASE}/policy`, { waitUntil: "networkidle" }); await p.waitForTimeout(600);
  await p.screenshot({ path: `${out}/policy.png` });
  await b.close();
})().catch((e) => { console.error(e); process.exit(1); });
