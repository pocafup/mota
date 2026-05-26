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

    // Search for shop-related data in all of core
    const result: any = {
      pluginKeys: [],
      coreEvents: {},
      shopScript: null,
      traderScript: null,
      // Try common mota-js shop locations
    };

    // Check c.plugin
    if ((c as any).plugin) {
      result.pluginKeys = Object.keys((c as any).plugin);
    }

    // Check c.events (the event processor, not data.events)
    if ((c as any).events) {
      const evObj = (c as any).events;
      // Look for shop-related functions
      result.coreEventKeys = Object.keys(evObj).slice(0, 30);
    }

    // Look for shop in all properties of core
    const coreKeys = Object.keys(c as any).filter(k => !/^_/.test(k));
    result.coreKeys = coreKeys.slice(0, 50);

    // Try to find trader event by looking in c.data more deeply
    const data = (c as any).data;
    if (data) {
      result.dataKeys = Object.keys(data).slice(0, 30);
      // Check for 'shops' property
      result.dataShops = data.shops;
      result.dataEventKeys = data.events ? Object.keys(data.events).slice(0, 30) : [];
    }

    // Specifically look for what happens on trader interaction
    // In some mota-js versions, the NPC event is in c.data.events[npcId] or c.data.blocks[npcId].event
    const blocks = data?.blocks || {};
    result.blocksTrader = blocks.trader;
    result.blocksBlueShop = blocks.blueShop;
    result.blockKeys = Object.keys(blocks).slice(0, 30);

    // Also check c.items (custom event system)
    result.coreItemsKeys = Object.keys((c as any).items || {}).slice(0, 20);

    // Check globalThis for shop vars
    const gKeys = Object.keys((window as any)).filter(k =>
      /shop|trader|商|buy|sell/i.test(k)
    ).slice(0, 20);
    result.globalShopKeys = gKeys;

    return JSON.parse(JSON.stringify(result, (_k, v) => {
      if (typeof v === 'function') return `[Function: ${v.name || 'anonymous'}]`;
      return v;
    }));
  });

  console.log('pluginKeys:', info.pluginKeys);
  console.log('coreKeys:', info.coreKeys?.slice(0, 30));
  console.log('coreEventKeys:', info.coreEventKeys);
  console.log('dataKeys:', info.dataKeys);
  console.log('dataEventKeys:', info.dataEventKeys);
  console.log('dataShops:', info.dataShops);
  console.log('blockKeys:', info.blockKeys);
  console.log('blocksTrader:', info.blocksTrader);
  console.log('blocksBlueShop:', info.blocksBlueShop);
  console.log('globalShopKeys:', info.globalShopKeys);

  await browser.close();
}

main().catch(console.error);
