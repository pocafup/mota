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
    const result: any = {
      npcIds: new Set<string>(),
      shopNpcs: [],
      allTiles: {} as Record<string, any>,
      floorItems: {} as Record<string, number>,
      shopFloors: [],
    };

    // Find all unique tile IDs and their classifications
    for (const fid of c.floorIds) {
      const f = c.floors[fid];
      if (!f?.map) continue;
      for (const row of f.map as number[][]) {
        for (const t of row) {
          if (!t || result.allTiles[t]) continue;
          try {
            const info = c.getBlockInfo(t);
            if (info) result.allTiles[t] = { id: info.id, cls: info.cls, name: info.name };
          } catch { }
        }
      }
    }

    // Find all NPCs
    const npcs = Object.values(result.allTiles).filter((t: any) => t.cls === 'npcs');
    result.npcInfo = npcs;

    // Check events on each floor for shop-related events
    for (const fid of c.floorIds) {
      const f = c.floors[fid];
      if (!f?.events) continue;
      const hasShop = Object.values(f.events).some((evList: any) => {
        if (!Array.isArray(evList)) return false;
        return evList.some((ev: any) =>
          ev?.type === 'openShop' || ev?.type === 'shop' ||
          (typeof ev === 'object' && JSON.stringify(ev).includes('shop'))
        );
      });
      if (hasShop) {
        result.shopFloors.push(fid);
      }
    }

    // Look at shop definitions
    result.materialShops = Object.keys(c.material?.shops || {});
    result.coreShops = Object.keys(c.shops || {});

    // Find all event types across all floors
    const eventTypes = new Set<string>();
    for (const fid of c.floorIds) {
      const f = c.floors[fid];
      if (!f?.events) continue;
      for (const evList of Object.values(f.events) as any[][]) {
        if (!Array.isArray(evList)) continue;
        for (const ev of evList) {
          if (ev?.type) eventTypes.add(ev.type);
        }
      }
    }
    result.eventTypes = Array.from(eventTypes);

    // Sample events on floors 25-27
    result.sampleEvents = {};
    for (const fid of ['MT24', 'MT25', 'MT26', 'MT27']) {
      const f = c.floors[fid];
      if (f?.events) {
        result.sampleEvents[fid] = f.events;
      }
    }

    return JSON.parse(JSON.stringify(result, (_k, v) => v instanceof Set ? [...v] : v));
  });

  console.log('\n=== NPC Tiles ===');
  console.log(JSON.stringify(info.npcInfo, null, 2));

  console.log('\n=== Event Types across all floors ===');
  console.log(info.eventTypes.join(', '));

  console.log('\n=== Shop floors (by event scan) ===');
  console.log(info.shopFloors);

  console.log('\n=== material.shops keys ===');
  console.log(info.materialShops);

  console.log('\n=== core.shops keys ===');
  console.log(info.coreShops);

  console.log('\n=== Sample events on floors 25-27 ===');
  console.log(JSON.stringify(info.sampleEvents, null, 2).slice(0, 3000));

  await browser.close();
}

main().catch(console.error);
