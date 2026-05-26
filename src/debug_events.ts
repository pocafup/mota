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

      // Recursively find all changeFloor actions in an event list
      function findChangeFlorInEvent(actions: any[]): any[] {
        const found: any[] = [];
        for (const ev of actions) {
          if (!ev || typeof ev !== 'object') continue;
          if (ev.type === 'changeFloor') found.push(ev);
          if (ev.true && Array.isArray(ev.true)) found.push(...findChangeFlorInEvent(ev.true));
          if (ev.false && Array.isArray(ev.false)) found.push(...findChangeFlorInEvent(ev.false));
          if (ev.action && Array.isArray(ev.action)) found.push(...findChangeFlorInEvent(ev.action));
          if (ev.caseList && Array.isArray(ev.caseList)) {
            for (const c of ev.caseList) {
              if (c?.action) found.push(...findChangeFlorInEvent(c.action));
            }
          }
        }
        return found;
      }

      // Scan all floors for changeFloor events and flag sets
      const results: any = { floors: {} };
      for (let i = 0; i < floorIds.length; i++) {
        const fid = floorIds[i];
        const f = c.floors[fid];
        if (!f?.events) continue;
        const floorNum = i + 1;

        const cfByCell: any = {};
        const setFlagByCell: any = {};

        for (const [key, evList] of Object.entries(f.events as Record<string, any[]>)) {
          if (!Array.isArray(evList)) continue;
          const cfs = findChangeFlorInEvent(evList);
          if (cfs.length > 0) cfByCell[key] = cfs;

          // Also find setValue events for flags
          const flagSets: string[] = [];
          function findFlagSets(actions: any[]) {
            for (const ev of actions) {
              if (!ev || typeof ev !== 'object') continue;
              if (ev.type === 'setValue' && ev.name?.startsWith('flag:')) flagSets.push(`${ev.name}=${ev.value}`);
              if (ev.true) findFlagSets(ev.true);
              if (ev.false) findFlagSets(ev.false);
              if (ev.action) findFlagSets(ev.action);
            }
          }
          findFlagSets(evList);
          if (flagSets.length > 0) setFlagByCell[key] = flagSets;
        }

        if (Object.keys(cfByCell).length > 0 || Object.keys(setFlagByCell).length > 0) {
          results.floors[`${fid}(F${floorNum})`] = {
            changeFloor: cfByCell,
            setFlags: setFlagByCell,
          };
        }
      }

      // Also check what flag:402 is set by
      const flag402Sources: string[] = [];
      for (let i = 0; i < floorIds.length; i++) {
        const fid = floorIds[i];
        const f = c.floors[fid];
        if (!f?.events) continue;
        const floorNum = i + 1;

        function scanForFlag402(actions: any[], context: string) {
          for (const ev of actions) {
            if (!ev || typeof ev !== 'object') continue;
            if (ev.type === 'setValue' && ev.name === 'flag:402') {
              flag402Sources.push(`F${floorNum}(${fid}) cell ${context}: set flag:402=${ev.value}`);
            }
            if (ev.true) scanForFlag402(ev.true, context);
            if (ev.false) scanForFlag402(ev.false, context);
            if (ev.action) scanForFlag402(ev.action, context);
          }
        }
        for (const [key, evList] of Object.entries(f.events as Record<string, any[]>)) {
          if (!Array.isArray(evList)) continue;
          scanForFlag402(evList, key);
        }
      }

      results.flag402Sources = flag402Sources;

      // Also look at initialValues for flag:402
      results.initialValues = c.data?.values || {};
      results.firstDataFlags = c.firstData?.hero?.flags || {};

      return results;
    });

    console.log('=== Floors with changeFloor events ===');
    for (const [fid, data] of Object.entries(result.floors) as any[]) {
      if (Object.keys(data.changeFloor).length > 0) {
        console.log(`\n${fid}:`);
        for (const [cell, cfs] of Object.entries(data.changeFloor) as any[]) {
          console.log(`  cell(col,row)=${cell}: ${JSON.stringify(cfs).slice(0, 300)}`);
        }
      }
    }

    console.log('\n=== flag:402 sources ===');
    if (result.flag402Sources.length === 0) {
      console.log('  (not found anywhere — flag:402 may start as true)');
    } else {
      for (const s of result.flag402Sources) console.log(' ', s);
    }

    console.log('\n=== Initial flags ===');
    console.log('  flag:402 in firstData.hero.flags:', result.firstDataFlags['402'] ?? '(not set)');
    console.log('  values.402:', result.initialValues['402'] ?? '(not set)');

    // Show which floors have flags being SET (to find F50→F51 mechanism)
    console.log('\n=== Floors with flag sets near F40-F51 ===');
    for (const [fid, data] of Object.entries(result.floors) as any[]) {
      if (Object.keys(data.setFlags).length > 0) {
        const floorNum = parseInt(fid.match(/F(\d+)/)?.[1] || '0');
        if (floorNum >= 38) {
          console.log(`\n${fid} setFlags:`);
          for (const [cell, flags] of Object.entries(data.setFlags) as any[]) {
            console.log(`  cell=${cell}: ${JSON.stringify(flags)}`);
          }
        }
      }
    }

  } finally {
    await browser.close();
  }
}

main().catch(console.error);
