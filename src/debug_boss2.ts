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
    const enemys = c.material?.enemys || {};
    // Get ALL monsters sorted by HP
    const allMonsters = Object.entries(enemys).map(([id, e]: [string, any]) => ({
      id, name: e.name, hp: e.hp, atk: e.atk, def: e.def, money: e.money, special: e.special,
    })).sort((a, b) => b.hp - a.hp);

    // Also get hero initial data
    const firstData = c.firstData?.hero || {};
    // And item equip values
    const items = c.material?.items || {};
    const equips = Object.entries(items)
      .filter(([, i]: any) => i?.equip?.value)
      .map(([id, i]: any) => ({ id, name: i.name, value: i.equip.value }));

    // Count red gems per floor
    const redGemCount: Record<number, number> = {};
    const floorIds = c.floorIds;
    for (let i = 0; i < floorIds.length; i++) {
      const fid = floorIds[i];
      const f = c.floors[fid];
      if (!f?.map) continue;
      const h = f.height || 13, w = f.width || 13;
      let count = 0;
      for (let r = 0; r < h; r++) {
        for (let cc = 0; cc < w; cc++) {
          const t = (f.map as number[][])[r]?.[cc];
          if (!t) continue;
          try {
            const info = c.getBlockInfo(t);
            if (info?.id === 'redGem') count++;
          } catch { }
        }
      }
      if (count > 0) redGemCount[i + 1] = count;
    }

    // Values
    const values = c.data?.values || {};

    return JSON.parse(JSON.stringify({
      topMonsters: allMonsters.slice(0, 10),
      heroStart: firstData,
      equips,
      redGemByFloor: redGemCount,
      values,
    }));
  });

  console.log('=== Top monsters ===');
  for (const m of info.topMonsters) {
    console.log(`  ${m.name}(${m.id}): HP=${m.hp} ATK=${m.atk} DEF=${m.def} special=${JSON.stringify(m.special)}`);
  }

  console.log('\n=== Hero start data (raw) ===');
  console.log(JSON.stringify(info.heroStart, null, 2));

  console.log('\n=== Equipment raw values ===');
  for (const e of info.equips) {
    console.log(`  ${e.name}(${e.id}): atk=${e.value.atk} def=${e.value.def}`);
  }

  console.log('\n=== Red gem count by floor ===');
  let totalGems = 0;
  for (const [floor, count] of Object.entries(info.redGemByFloor) as [string, number][]) {
    const area = Math.max(1, Math.floor((parseInt(floor) - 1) / 10));
    console.log(`  F${floor}: ${count} gems × area ${area} = ${count * area} ATK`);
    totalGems += count * area;
  }
  console.log(`  Total ATK from red gems: ${totalGems}`);

  console.log('\n=== Game values ===');
  console.log(JSON.stringify(info.values, null, 2));

  await browser.close();
}

main().catch(console.error);
