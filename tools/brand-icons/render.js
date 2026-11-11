const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const jobs = JSON.parse(fs.readFileSync(process.argv[2]));
  const b = await chromium.launch(); const p = await b.newPage();
  for (const [svgp, w, h, png] of jobs) {
    await p.setViewportSize({ width: w, height: h });
    const svg = fs.readFileSync(svgp, 'utf8');
    await p.setContent(`<html><body style="margin:0;background:transparent"><img id="i" src="data:image/svg+xml;base64,${Buffer.from(svg).toString('base64')}" style="display:block;width:${w}px;height:${h}px"></body></html>`);
    await p.waitForFunction(() => document.getElementById('i').complete);
    await p.waitForTimeout(50);
    await p.screenshot({ path: png, omitBackground: true, clip: { x: 0, y: 0, width: w, height: h } });
  }
  await b.close(); console.log('rendered', jobs.length);
})();
