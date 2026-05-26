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

      // Build tileMap (id → { id, cls })
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

      // Print grids for floors 3-7 (h5mota MT2-MT6)
      // Our F5 = MT4 = floorIds[4]
      const targetIndices = [2, 3, 4, 5, 6]; // MT2=F3, MT3=F4, MT4=F5, MT5=F6, MT6=F7
      const grids: any = {};

      for (const idx of targetIndices) {
        const fid = floorIds[idx];
        const f = c.floors[fid];
        if (!f?.map) continue;
        const h = f.height || 13, w = f.width || 13;
        const grid: string[][] = [];
        for (let r = 0; r < h; r++) {
          const row: string[] = [];
          for (let cc = 0; cc < w; cc++) {
            const t = (f.map as number[][])[r]?.[cc];
            if (!t) { row.push('.'); continue; }
            const info = tileMap[t];
            if (!info) { row.push('?'); continue; }
            if (info.cls === 'terrains') {
              // terrains = walls or floors
              if (info.id.includes('wall') || info.id.includes('Wall')) row.push('#');
              else row.push('_');
            } else if (info.cls === 'items') row.push('i');
            else if (info.cls === 'enemys') row.push('m');
            else if (info.cls === 'npcs') row.push('n');
            else if (info.cls === 'animates') row.push('@'); // stairs etc
            else row.push('?');
          }
          grid.push(row);
        }
        grids[`${fid}(F${idx + 1})`] = { grid, stairPos: [] as any[] };

        // Find actual stair tile ids
        for (let r = 0; r < h; r++) {
          for (let cc = 0; cc < w; cc++) {
            const t = (f.map as number[][])[r]?.[cc];
            if (!t) continue;
            const info = tileMap[t];
            if (!info) continue;
            if (/stair|stair|上楼|下楼/i.test(info.id) || info.cls === 'animates') {
              grids[`${fid}(F${idx + 1})`].stairPos.push({ r, cc, id: info.id, cls: info.cls, tileId: t });
            }
          }
        }
      }

      return { grids, tileMap };
    });

    for (const [name, data] of Object.entries(result.grids) as any[]) {
      console.log(`\n=== ${name} ===`);
      console.log('   0123456789012');
      for (let r = 0; r < data.grid.length; r++) {
        const rowStr = data.grid[r].join('');
        console.log(`${r.toString().padStart(2,' ')} ${rowStr}`);
      }
      if (data.stairPos.length > 0) {
        console.log(`  Stair tiles: ${JSON.stringify(data.stairPos)}`);
      }
    }

    // Show which tile IDs are terrains and their IDs
    console.log('\n=== Terrain tile IDs ===');
    for (const [tid, info] of Object.entries(result.tileMap) as any[]) {
      if (info.cls === 'terrains') {
        console.log(`  tile ${tid}: id=${info.id}`);
      }
    }

  } finally {
    await browser.close();
  }
}

main().catch(console.error);
