import { chromium } from 'playwright';
async function main() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.goto('https://h5mota.com/games/51/', { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => (window as any).core?.floorIds?.length > 0, { timeout: 30000 });
  const data = await page.evaluate(() => {
    const c = (window as any).core;
    const areas = c.floorIds.map((fid: string, i: number) => {
      const f = c.floors[fid];
      return { floor: i+1, fid, ratio: f?.ratio };
    });
    const f1 = c.floors[c.floorIds[0]];
    const f1Keys = f1 ? Object.keys(f1).filter((k: string) => !['map','events'].includes(k)) : [];
    return JSON.parse(JSON.stringify({ areas: areas.slice(0,25), f1Keys }));
  });
  console.log('=== Floor areas (first 25) ===');
  for (const a of data.areas) console.log(`  F${a.floor}(${a.fid}): ratio=${a.ratio}`);
  console.log('\n=== Floor 1 keys ===', data.f1Keys.join(', '));
  await browser.close();
}
main().catch(console.error);
