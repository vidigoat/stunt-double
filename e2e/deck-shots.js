const { chromium } = require('playwright');
const out = process.argv[2];
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  await p.goto('http://localhost:3000/', { waitUntil: 'networkidle' }); await p.waitForTimeout(1200);
  const card = p.locator('section').first().locator('div.overflow-hidden.rounded-2xl').first();
  await card.screenshot({ path: `${out}/approval-card.png` });
  await p.goto('http://localhost:3000/app', { waitUntil: 'networkidle' }); await p.waitForTimeout(500);
  await p.getByRole('tab', { name: /Break it yourself/ }).click();
  await p.getByRole('button', { name: 'Delete every customer' }).click();
  await p.getByRole('button', { name: 'Rehearse it' }).click();
  await p.waitForSelector('text=containment', { timeout: 30000 }); await p.waitForTimeout(1000);
  await p.screenshot({ path: `${out}/console-containment.png` });
  await b.close();
})();
