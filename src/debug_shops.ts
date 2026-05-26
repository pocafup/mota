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
    const shopNpcIds = new Set(['blueShop', 'trader', 'specialTrader', 'pinkShop']);

    // Build tileId → {id, cls} map
    const tileMap: Record<number, { id: string; cls: string }> = {};
    const allTileIds = new Set<number>();
    for (const fid of c.floorIds) {
      const f = c.floors[fid];
      if (!f?.map) continue;
      for (const row of f.map as number[][])
        for (const t of row) if (t) allTileIds.add(t);
    }
    for (const t of allTileIds) {
      try {
        const info = c.getBlockInfo(t);
        if (info) tileMap[t] = { id: info.id, cls: info.cls };
      } catch { }
    }

    // Find shop NPC positions
    const shopPositions: any[] = [];
    for (let i = 0; i < c.floorIds.length; i++) {
      const fid = c.floorIds[i];
      const f = c.floors[fid];
      if (!f?.map) continue;
      const h = f.height || 13, w = f.width || 13;
      for (let r = 0; r < h; r++) {
        for (let cc = 0; cc < w; cc++) {
          const t = (f.map as number[][])[r]?.[cc];
          if (!t) continue;
          const info = tileMap[t];
          if (info && info.cls === 'npcs' && shopNpcIds.has(info.id)) {
            shopPositions.push({ floorId: fid, floorIdx: i + 1, row: r, col: cc, npcId: info.id });
          }
        }
      }
    }

    // Get events for shop positions
    const shopEvents: any[] = [];
    for (const sp of shopPositions) {
      const f = c.floors[sp.floorId];
      if (!f?.events) continue;
      // Key format in mota-js is "col,row"
      const eventKey = `${sp.col},${sp.row}`;
      const ev = f.events[eventKey];
      shopEvents.push({ ...sp, event: ev || null });
    }

    // Also look at NPC definitions in material
    const npcDefs = c.material?.npcs || {};
    const shopNpcDefs: any = {};
    for (const id of shopNpcIds) {
      if (npcDefs[id]) shopNpcDefs[id] = npcDefs[id];
    }

    // Look at c.data for any shop-related values
    const shopValues: any = {};
    const vals = c.data?.values || {};
    for (const [k, v] of Object.entries(vals)) {
      if (/shop|buy|price|cost/i.test(k)) shopValues[k] = v;
    }

    return JSON.parse(JSON.stringify({
      shopPositions,
      shopEvents,
      shopNpcDefs,
      shopValues,
    }));
  });

  console.log('\n=== Shop NPC positions ===');
  for (const sp of info.shopPositions) {
    console.log(`  F${sp.floorIdx} [${sp.row},${sp.col}] ${sp.npcId}`);
  }

  console.log('\n=== Shop events at those positions ===');
  for (const se of info.shopEvents) {
    if (se.event) {
      console.log(`\n  F${se.floorIdx} [${se.row},${se.col}] ${se.npcId}:`);
      console.log('  ', JSON.stringify(se.event, null, 2).slice(0, 1500));
    }
  }

  console.log('\n=== NPC definitions for shops ===');
  console.log(JSON.stringify(info.shopNpcDefs, null, 2).slice(0, 3000));

  console.log('\n=== Shop-related values ===');
  console.log(info.shopValues);

  await browser.close();
}

main().catch(console.error);
