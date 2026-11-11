import { chromium } from 'playwright-core';

const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const URL = process.env.URL || 'http://127.0.0.1:5180/';
const OUT = process.env.OUT || 'D:/Projects/lingxiao-tower/web/_shot.png';
const W = Number(process.env.W || 1440);
const H = Number(process.env.H || 900);

const browser = await chromium.launch({
  executablePath: EDGE,
  headless: true,
  args: [
    '--use-angle=d3d11',
    '--enable-unsafe-swiftshader',
    '--ignore-gpu-blocklist',
    '--enable-gpu-rasterization',
    '--hide-scrollbars',
    '--force-device-scale-factor=1',
  ],
});

const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });

const logs = [];
page.on('console', (m) => logs.push(`[${m.type()}] ${m.text()}`));
page.on('pageerror', (e) => logs.push(`[pageerror] ${e.message}`));

await page.goto(URL, { waitUntil: 'networkidle', timeout: 60000 });
await page.waitForTimeout(6000);

const info = await page.evaluate(() => {
  const c = document.getElementById('scene');
  const gl = c && (c.getContext('webgl2') || c.getContext('webgl'));
  return {
    canvas: c ? `${c.width}x${c.height}` : 'none',
    webgl: gl ? 'ok' : 'no-gl',
    loaderHidden: document.getElementById('loader')?.classList.contains('done') ?? null,
  };
});

await page.screenshot({ path: OUT, type: 'png' });
console.log('SHOT', OUT);
console.log('INFO', JSON.stringify(info));
if (logs.length) console.log('LOGS:\n' + logs.slice(0, 20).join('\n'));

await browser.close();
