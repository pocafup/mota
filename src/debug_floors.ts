import { chromium } from 'playwright';

async function main() {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage();
    await page.goto('https://h5mota.com/games/51/', { waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => {
      const c = (window as any).core;
      return c?.floorIds?.length > 0 && c?.material?.enemys && c?.floors;
    }, { timeout: 30000 });

    const result = await page.evaluate(() => {
      const c = (window as any).core;
      const floorIds: string[] = c.floorIds;

      // Build tileMap
      const allTileIds = new Set<number>();
      for (const fid of floorIds) {
        const f = c.floors[fid];
        if (!f?.map) continue;
        for (const row of f.map as number[][])
          for (const t of row) if (t) allTileIds.add(t);
      }
      const tileMap: Record<number, { id: string; cls: string }> = {};
      for (const t of allTileIds) {
        try {
          const info = c.getBlockInfo(t);
          if (info) tileMap[t] = { id: info.id, cls: info.cls };
        } catch { }
      }

      // Find all unique tile classes/ids for stair-like tiles
      const stairTiles: any[] = [];
      for (const [tid, info] of Object.entries(tileMap)) {
        if (/floor|stair|stairs|up|down|fly|portal|jump/i.test(info.id)) {
          stairTiles.push({ tileId: tid, ...info });
        }
      }

      // Check specific floors: 41 (MT40), 45 (MT44), 50 (MT49), 51 (MT50)
      const targetFloors = ['MT40', 'MT41', 'MT44', 'MT49', 'MT50'];
      const floorDetails: any = {};

      for (const fid of targetFloors) {
        const f = c.floors[fid];
        if (!f) { floorDetails[fid] = 'MISSING'; continue; }
        const floorNum = floorIds.indexOf(fid) + 1;
        const h: number = f.height || 13, w: number = f.width || 13;
        const nonEmpty: any[] = [];
        for (let r = 0; r < h; r++) {
          for (let cc = 0; cc < w; cc++) {
            const t = (f.map as number[][])[r]?.[cc];
            if (!t) continue;
            const info = tileMap[t];
            const evKey = `${cc},${r}`;
            const evs = (f.events || {})[evKey];
            nonEmpty.push({ r, cc, tileId: t, info, events: evs || [] });
          }
        }
        floorDetails[fid] = { floorNum, cells: nonEmpty };
      }

      // Also check changeFloor events on floors near the gaps
      const cfEvents: any = {};
      for (const fid of ['MT40', 'MT41', 'MT44', 'MT49', 'MT50']) {
        const f = c.floors[fid];
        if (!f?.events) continue;
        const cfList: any[] = [];
        for (const [key, evList] of Object.entries(f.events as any)) {
          if (!Array.isArray(evList)) continue;
          for (const ev of (evList as any[])) {
            if (ev?.type === 'changeFloor') {
              cfList.push({ key, ev });
            }
          }
        }
        if (cfList.length > 0) cfEvents[fid] = cfList;
      }

      return { stairTiles, floorDetails, cfEvents };
    });

    console.log('\n=== Stair-like tile IDs ===');
    for (const t of result.stairTiles) {
      console.log(`  tile ${t.tileId}: id=${t.id} cls=${t.cls}`);
    }

    console.log('\n=== Floor details ===');
    for (const [fid, detail] of Object.entries(result.floorDetails) as any[]) {
      if (detail === 'MISSING') { console.log(`\n${fid}: MISSING`); continue; }
      console.log(`\n${fid} (floorNum=${detail.floorNum}):`);
      for (const cell of detail.cells) {
        const ev = cell.events.length ? JSON.stringify(cell.events) : '';
        console.log(`  (${cell.r},${cell.cc}) tile=${cell.tileId} id=${cell.info?.id} cls=${cell.info?.cls}${ev ? ' events=' + ev.slice(0, 200) : ''}`);
      }
    }

    console.log('\n=== changeFloor events ===');
    console.log(JSON.stringify(result.cfEvents, null, 2));

  } finally {
    await browser.close();
  }
}

main().catch(console.error);
