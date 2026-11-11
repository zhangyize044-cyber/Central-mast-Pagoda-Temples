import { chromium } from 'playwright-core';

const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const URL = process.env.URL || 'http://127.0.0.1:5191/';
const W = Number(process.env.W || 1440);
const H = Number(process.env.H || 900);
const VIEWS = ['full', 'low', 'top', 'inner', 'site'];

const browser = await chromium.launch({
  executablePath: EDGE,
  headless: true,
  args: ['--use-angle=d3d11', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist',
    '--enable-gpu-rasterization', '--hide-scrollbars', '--force-device-scale-factor=1'],
});
const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
const errs = [];
page.on('pageerror', (e) => errs.push(e.message));
await page.goto(URL, { waitUntil: 'networkidle', timeout: 60000 });
await page.waitForTimeout(6500);

for (const v of VIEWS) {
  await page.click(`button[data-view="${v}"]`);
  await page.waitForTimeout(3000);
  const out = `D:/Projects/lingxiao-tower/web/_view_${v}.png`;
  await page.screenshot({ path: out, type: 'png' });
  console.log('SHOT', v);
}
if (errs.length) console.log('ERRS', errs.slice(0, 5).join(' | '));
await browser.close();
