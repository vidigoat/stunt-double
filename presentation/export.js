// Render the deck to PDF + per-slide PNGs, and the cover/OG images. Usage: node presentation/export.js
const { chromium } = require('playwright');
const path = require('path');
const here = __dirname, pub = path.join(here, '..', 'web', 'public');
(async () => {
  const b = await chromium.launch();
  const deck = await b.newPage({ viewport: { width: 1920, height: 1080 } });
  await deck.goto('file://' + path.join(here, 'deck.html'), { waitUntil: 'networkidle' });
  await deck.evaluate(() => document.fonts.ready);
  await deck.pdf({ path: path.join(here, 'stunt-double-deck.pdf'), width: '1920px', height: '1080px', printBackground: true });
  const n = await deck.locator('section.slide').count();
  for (let i = 0; i < n; i++) await deck.locator('section.slide').nth(i).screenshot({ path: path.join(here, 'slides', `slide-${String(i + 1).padStart(2, '0')}.png`) });
  for (const [file, w, h] of [['cover.png', 1920, 1080], ['og.png', 1200, 630]]) {
    const p = await b.newPage({ viewport: { width: w, height: h } });
    await p.goto('file://' + path.join(here, 'cover.html'), { waitUntil: 'networkidle' });
    await p.evaluate((u) => document.documentElement.style.setProperty('--u', u + 'px'), w / 100);
    await p.evaluate(() => document.fonts.ready);
    await p.screenshot({ path: file === 'og.png' ? path.join(pub, 'og.png') : path.join(here, file) });
  }
  await b.close();
  console.log(`exported ${n} slides, deck PDF, cover.png, web/public/og.png`);
})();
