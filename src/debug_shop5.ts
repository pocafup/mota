import { chromium } from 'playwright';

async function main() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.goto('https://h5mota.com/games/51/', { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => {
    const c = (window as any).core;
    return c?.floorIds?.length > 0 && c?.material?.enemys && c?.floors;
  }, { timeout: 30000 });

  const info = await page.evaluate(() => {
    const c = (window as any).core;

    // Get core.status.shops
    const statusShops = (c as any).status?.shops || {};

    // Get common events (named events used by insert)
    const commonEvents = (c as any).events?.commonEvent || {};
    const shopCommonEvent = commonEvents['商店'];
    const traderCommonEvent = commonEvents['商人'];

    // Get system events for 'trader'
    const sysEvents = (c as any).events?.systemEvents || {};
    const traderSysEvent = sysEvents['trader'];

    return JSON.parse(JSON.stringify({
      statusShops,
      shopCommonEvent,
      traderCommonEvent,
      traderSysEvent,
    }, (_k, v) => {
      if (typeof v === 'function') return `[Function: ${v.name}]`;
      return v;
    }));
  });

  console.log('\n=== core.status.shops ===');
  console.log(JSON.stringify(info.statusShops, null, 2)?.slice(0, 5000));

  console.log('\n=== commonEvent["商店"] ===');
  console.log(JSON.stringify(info.shopCommonEvent, null, 2)?.slice(0, 3000));

  console.log('\n=== commonEvent["商人"] ===');
  console.log(JSON.stringify(info.traderCommonEvent, null, 2)?.slice(0, 3000));

  console.log('\n=== systemEvents["trader"] ===');
  console.log(JSON.stringify(info.traderSysEvent, null, 2)?.slice(0, 3000));

  await browser.close();
}

main().catch(console.error);
