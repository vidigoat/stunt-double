// Records the live-product part of the submission video with on-screen captions. Usage: node record-live.js <outdir>
const { chromium } = require("playwright");
const BASE = process.env.BASE_URL || "http://localhost:3000";
const out = process.argv[2];

const OVERLAY = `(() => {
  const css = document.createElement('style');
  css.textContent = '#__cap{position:fixed;left:50%;bottom:28px;transform:translateX(-50%);z-index:2147483646;max-width:1100px;padding:14px 26px;border-radius:999px;background:rgba(10,10,10,.92);color:#FAFAF8;font:500 22px/1.35 Geist,system-ui,sans-serif;letter-spacing:-.01em;box-shadow:0 12px 40px rgba(0,0,0,.25);transition:opacity .25s;text-align:center}#__cap b{color:#FF8A8E;font-weight:600}#__cur{position:fixed;width:20px;height:20px;border-radius:50%;background:rgba(10,10,10,.85);border:2px solid #FAFAF8;z-index:2147483647;pointer-events:none;transform:translate(-50%,-50%);box-shadow:0 2px 8px rgba(0,0,0,.25)}';
  const add = () => { if (!document.body || document.getElementById('__cap')) return; document.head.appendChild(css);
    const c = document.createElement('div'); c.id='__cap'; c.style.opacity='0'; document.body.appendChild(c);
    const k = document.createElement('div'); k.id='__cur'; document.body.appendChild(k);
    addEventListener('mousemove', e => { k.style.left = e.clientX + 'px'; k.style.top = e.clientY + 'px'; }, true); };
  document.addEventListener('DOMContentLoaded', add); add();
  window.__caption = (html) => { add(); const c = document.getElementById('__cap'); c.style.opacity = html ? '1' : '0'; if (html) c.innerHTML = html; };
})()`;

(async () => {
  await fetch(`${BASE}/api/demo/reset`, { method: "POST" });
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1600, height: 900 }, recordVideo: { dir: out, size: { width: 1600, height: 900 } }, ignoreHTTPSErrors: true });
  await ctx.addInitScript(OVERLAY);
  const page = await ctx.newPage();
  const pause = (ms) => page.waitForTimeout(ms);
  const say = (html) => page.evaluate((h) => window.__caption(h), html);
  async function click(loc) {
    const b = await loc.boundingBox();
    await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2, { steps: 20 });
    await pause(250);
    await loc.click();
  }

  await page.goto(BASE, { waitUntil: "networkidle" });
  await page.mouse.move(800, 420);
  await say("Stunt Double: every risky AI action gets a <b>rehearsal</b> first."); await pause(3800);
  await say("The approver sees <b>consequences</b>, not code: money out, people, emails, rows."); await page.mouse.wheel(0, 560); await pause(4200);

  await page.goto(`${BASE}/app`, { waitUntil: "networkidle" });
  await say("A real business: Bean There Coffee Co. <b>1,300 customers</b> in production."); await pause(3600);
  await click(page.getByRole("tab", { name: /Break it yourself/ }));
  await click(page.getByRole("button", { name: "Delete every customer", exact: true }));
  await say("Let's try something malicious: <b>DELETE FROM customers</b>."); await pause(2200);
  await click(page.getByRole("button", { name: "Rehearse it", exact: true }));
  await page.getByText(/containment: the damage happened only on the double/i).waitFor({ timeout: 60000 });
  await say("It ran in an isolated Vultr sandbox. The double lost <b>every customer</b>. Production lost <b>none</b>."); await page.mouse.move(1150, 200, { steps: 20 }); await pause(5200);
  await say("Policy locks the Approve button. <b>Blast radius: zero.</b>"); await page.mouse.move(1380, 470, { steps: 20 }); await pause(3800);
  await click(page.getByRole("tab", { name: "Sandbox" }));
  await say("No network, no secrets, read-only, capped, and <b>destroyed</b> after every run."); await pause(4200);

  await click(page.getByRole("button", { name: "New" }));
  await click(page.getByRole("tab", { name: /Break it yourself/ }));
  await click(page.getByRole("button", { name: "✓ A correct refund plan", exact: true }));
  await say("Now a correct plan: refund only the <b>104</b> customers who were really charged twice."); await pause(2600);
  await click(page.getByRole("button", { name: "Rehearse it", exact: true }));
  const approve = page.getByRole("button", { name: /Approve and apply/ });
  await approve.waitFor({ timeout: 60000 });
  await say("$5,136 to 104 people, in plain English. Approval is bound to a <b>fingerprint</b> of the plan."); await pause(4600);
  await click(approve);
  await page.getByText("Applied for real").waitFor({ timeout: 60000 });
  await page.getByText("Applied for real").scrollIntoViewIfNeeded();
  await say("Drift check passed. Only the <b>approved effects</b> are replayed: refunds and emails go out for real."); await pause(4800);

  await page.goto(`${BASE}/history`, { waitUntil: "networkidle" });
  await say("Every rehearsal is on the record. What was applied is <b>provably</b> what was approved."); await pause(4200);
  await say("");
  const video = page.video();
  await ctx.close();
  console.log(await video.path());
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
