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

    // Find the "商店" insert event definition
    const events = c.data?.events || {};
    const shopInsert = events['商店'];

    // Find trader NPC definitions from all possible locations
    const traderDef = {
      material_npcs: c.material?.npcs?.trader,
      data_npcs: (c.data as any)?.npcs?.trader,
      allEventKeys: Object.keys(events).slice(0, 50),
    };

    // Look for trader NPC events on specific floors
    const traderFloors: any[] = [];
    const shopNpcIds = ['blueShop', 'trader', 'specialTrader'];

    // Rebuild tile map
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
          if (info && info.id === 'trader') {
            const evKey = `${cc},${r}`;
            const ev = f.events?.[evKey];
            traderFloors.push({ floor: fid, floorIdx: i+1, row: r, col: cc, event: ev });
          }
        }
      }
    }

    // Check getBlockInfo for trader to see if it has built-in event
    let traderBlockInfo: any = null;
    for (const [tileId, info] of Object.entries(tileMap)) {
      if (info.id === 'trader') {
        const bi = c.getBlockInfo(parseInt(tileId));
        traderBlockInfo = bi;
        break;
      }
    }

    // Also look at c.data.blocks for NPC events
    const dataBlocks = (c.data as any)?.blocks?.trader;

    return JSON.parse(JSON.stringify({
      shopInsert,
      traderDef,
      traderFloors: traderFloors.slice(0, 5),
      traderBlockInfo,
      dataBlocks,
      eventKeys: Object.keys(events),
    }));
  });

  console.log('\n=== "商店" insert event definition ===');
  console.log(JSON.stringify(info.shopInsert, null, 2)?.slice(0, 3000));

  console.log('\n=== Trader NPC definition ===');
  console.log(JSON.stringify(info.traderDef, null, 2)?.slice(0, 2000));

  console.log('\n=== Trader floors and their events ===');
  for (const tf of info.traderFloors) {
    console.log(`\n  F${tf.floorIdx} [${tf.row},${tf.col}]:`);
    console.log('  event:', JSON.stringify(tf.event, null, 2)?.slice(0, 1000));
  }

  console.log('\n=== Trader block info (getBlockInfo) ===');
  console.log(JSON.stringify(info.traderBlockInfo, null, 2)?.slice(0, 1000));

  console.log('\n=== c.data.blocks.trader ===');
  console.log(JSON.stringify(info.dataBlocks, null, 2)?.slice(0, 1000));

  console.log('\n=== All event keys ===');
  console.log(info.eventKeys.join(', '));

  await browser.close();
}

main().catch(console.error);
