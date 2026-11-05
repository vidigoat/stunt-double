// Render the cover (16:9) and the social preview image. Usage: node presentation/export.js
const { chromium } = require('playwright');
const path = require('path');
const here = __dirname, pub = path.join(here, '..', 'web', 'public');
(async () => {
  const b = await chromium.launch();
  for (const [file, w, h] of [['cover.png', 1920, 1080], ['og.png', 1200, 630]]) {
    const p = await b.newPage({ viewport: { width: w, height: h } });
    await p.goto('file://' + path.join(here, 'cover.html'), { waitUntil: 'networkidle' });
    await p.evaluate((u) => document.documentElement.style.setProperty('--u', u + 'px'), w / 100);
    await p.evaluate(() => document.fonts.ready);
    await p.screenshot({ path: file === 'og.png' ? path.join(pub, 'og.png') : path.join(here, file) });
  }
  await b.close();
  console.log('exported cover.png and web/public/og.png');
})();
