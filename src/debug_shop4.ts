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
    const plugin = (c as any).plugin;

    const result: any = {};

    // List all shop IDs
    try {
      result.shopIds = plugin.listShopIds ? plugin.listShopIds() : null;
    } catch (e: any) {
      result.shopIdsError = e.message;
    }

    // Check events.eventdata for shop definitions
    const eventdata = (c as any).events?.eventdata || {};
    result.eventdataKeys = Object.keys(eventdata).slice(0, 30);

    // Look for shop-related eventdata
    const shopEventdataKeys = Object.keys(eventdata).filter(k =>
      /shop|商|trader|buy/i.test(k)
    );
    result.shopEventdataKeys = shopEventdataKeys;

    // Try getting shop data via openShop internally
    // In mota-js, shops are often stored as a list with items
    // Let's look at c.events.systemEvents
    const sysEvents = (c as any).events?.systemEvents || {};
    result.systemEventKeys = Object.keys(sysEvents).slice(0, 30);

    // Look at c.events.commonEvent
    const commonEvents = (c as any).events?.commonEvent || {};
    result.commonEventKeys = Object.keys(commonEvents).slice(0, 30);

    // Check c.extensions
    const ext = (c as any).extensions || {};
    result.extensionKeys = Object.keys(ext).slice(0, 20);

    // Check if plugin has shop data
    result.pluginOpenShop = plugin.openShop?.toString().slice(0, 500);
    result.pluginListShopIds = plugin.listShopIds?.toString().slice(0, 500);
    result.pluginConvertShop = plugin._convertShop?.toString().slice(0, 500);

    // Try calling listShopIds to see what shops exist
    let shopList: any = null;
    try {
      shopList = plugin.listShopIds();
    } catch { }
    result.shopList = shopList;

    // Get shop details for each shop
    const shopDetails: any = {};
    if (shopList && Array.isArray(shopList)) {
      for (const shopId of shopList) {
        try {
          // Try to get shop definition from the eventdata or other source
          const shopDef = eventdata[shopId];
          shopDetails[shopId] = shopDef;
        } catch { }
      }
    }
    result.shopDetails = shopDetails;

    return JSON.parse(JSON.stringify(result, (_k, v) => {
      if (typeof v === 'function') return `[Function]`;
      return v;
    }));
  });

  console.log('shopIds:', info.shopIds);
  console.log('shopList:', info.shopList);
  console.log('eventdataKeys (first 30):', info.eventdataKeys);
  console.log('shopEventdataKeys:', info.shopEventdataKeys);
  console.log('systemEventKeys:', info.systemEventKeys);
  console.log('commonEventKeys:', info.commonEventKeys);
  console.log('extensionKeys:', info.extensionKeys);
  console.log('\npluginListShopIds source:');
  console.log(info.pluginListShopIds);
  console.log('\npluginConvertShop source:');
  console.log(info.pluginConvertShop);
  console.log('\nshopDetails:', JSON.stringify(info.shopDetails, null, 2)?.slice(0, 3000));

  await browser.close();
}

main().catch(console.error);
