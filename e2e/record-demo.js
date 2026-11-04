// Records the README demo: containment, then a correct plan approved and applied. Usage: node record-demo.js <outdir>
const { chromium } = require("playwright");
const BASE = process.env.BASE_URL || "http://localhost:3000";
const out = process.argv[2];

const CURSOR = `(() => { const d = document.createElement('div'); d.id='__cursor';
  Object.assign(d.style,{position:'fixed',left:'0',top:'0',width:'18px',height:'18px',borderRadius:'50%',background:'rgba(10,10,10,.85)',
  border:'2px solid #FAFAF8',zIndex:2147483647,pointerEvents:'none',transform:'translate(-50%,-50%)',transition:'width .15s,height .15s',boxShadow:'0 2px 8px rgba(0,0,0,.25)'});
  const add=()=>document.body&&!document.getElementById('__cursor')&&document.body.appendChild(d);
  document.addEventListener('DOMContentLoaded',add); add();
  addEventListener('mousemove',e=>{d.style.left=e.clientX+'px';d.style.top=e.clientY+'px'},true);
  addEventListener('mousedown',()=>{d.style.width='12px';d.style.height='12px'},true);
  addEventListener('mouseup',()=>{d.style.width='18px';d.style.height='18px'},true); })()`;

(async () => {
  await fetch(`${BASE}/api/demo/reset`, { method: "POST" });
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, recordVideo: { dir: out, size: { width: 1280, height: 800 } } });
  await ctx.addInitScript(CURSOR);
  const page = await ctx.newPage();
  const pause = (ms) => page.waitForTimeout(ms);
  async function click(locator) {
    const box = await locator.boundingBox();
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 18 });
    await pause(250);
    await locator.click();
  }

  await page.goto(`${BASE}/`, { waitUntil: "networkidle" });
  await page.mouse.move(640, 300);
  await pause(2200);
  await page.mouse.wheel(0, 520); await pause(2400);
  await page.goto(`${BASE}/app`, { waitUntil: "networkidle" });
  await pause(900);
  await click(page.getByRole("tab", { name: /Break it yourself/ }));
  await click(page.getByRole("button", { name: "Delete every customer" }));
  await pause(500);
  await click(page.getByRole("button", { name: "Rehearse it" }));
  await page.getByText(/containment: the damage happened only on the double/i).waitFor({ timeout: 60000 });
  await pause(800);
  await page.mouse.move(980, 200, { steps: 20 });
  await pause(2600);
  await click(page.getByRole("button", { name: "New" }));
  await click(page.getByRole("tab", { name: /Break it yourself/ }));
  await click(page.getByRole("button", { name: /A correct refund plan/ }));
  await pause(400);
  await click(page.getByRole("button", { name: "Rehearse it" }));
  const approve = page.getByRole("button", { name: /Approve and apply/ });
  await approve.waitFor({ timeout: 60000 });
  await pause(2200);
  await click(approve);
  await page.getByText("Applied for real").waitFor({ timeout: 60000 });
  await page.getByText("Applied for real").scrollIntoViewIfNeeded();
  await pause(2400);
  await page.goto(`${BASE}/history`, { waitUntil: "networkidle" });
  await pause(2600);
  const video = page.video();
  await ctx.close();
  console.log(await video.path());
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
