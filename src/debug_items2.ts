import { chromium } from 'playwright';
async function main() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.goto('https://h5mota.com/games/51/', { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => (window as any).core?.floorIds?.length > 0, { timeout: 30000 });
  const data = await page.evaluate(() => {
    const c = (window as any).core;
    const items = c.material?.items || {};
    const result: any[] = [];
    for (const [id, item] of Object.entries(items) as [string, any][]) {
      if (!item) continue;
      result.push({
        id, name: item.name,
        cls: item.cls,
        itemEffect: item.itemEffect?.slice(0, 120),
        equipValue: item.equip?.value,
        hasRatio: item.itemEffect?.includes('.ratio'),
        hasAtk: item.itemEffect?.includes('.atk'),
        hasDef: item.itemEffect?.includes('.def'),
        hasHp: item.itemEffect?.includes('.hp'),
      });
    }
    return JSON.parse(JSON.stringify(result));
  });
  // Show items that deal with atk/def/hp
  console.log('\n=== All items with effects ===');
  for (const item of data) {
    if (item.hasAtk || item.hasDef || item.hasHp || item.equipValue) {
      console.log(`  ${item.name}(${item.id}): cls=${item.cls}`);
      if (item.itemEffect) console.log(`    effect: ${item.itemEffect}`);
      if (item.equipValue) console.log(`    equip: ${JSON.stringify(item.equipValue)}`);
    }
  }
  await browser.close();
}
main().catch(console.error);
