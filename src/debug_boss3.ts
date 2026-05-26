import { chromium } from 'playwright';
async function main() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.goto('https://h5mota.com/games/51/', { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => (window as any).core?.floorIds?.length > 0, { timeout: 30000 });
  const info = await page.evaluate(() => {
    const c = (window as any).core;
    const fids = c.floorIds;
    const lastFid = fids[fids.length - 1];
    const lastFloor = c.floors[lastFid];
    const enemys = c.material?.enemys || {};

    // Also check afterBattle events on all floors
    const afterBattles: any[] = [];
    for (let i = 0; i < fids.length; i++) {
      const f = c.floors[fids[i]];
      if (f?.afterBattle) afterBattles.push({ floor: i+1, fid: fids[i], afterBattle: f.afterBattle });
    }

    // Check isBoss in monsters
    const bossMonsters = Object.entries(enemys)
      .filter(([, e]: [string, any]) => e?.special && (
        (typeof e.special === 'number' && (e.special & 1)) ||
        (Array.isArray(e.special) && e.special.includes(1))
      ))
      .map(([id, e]: any) => ({ id, name: e.name, hp: e.hp, atk: e.atk, def: e.def, special: e.special }));

    // Check all monsters with special as array or number
    const specialMonsters = Object.entries(enemys)
      .filter(([, e]: [string, any]) => e?.special && (
        (typeof e.special === 'number' && e.special !== 0) ||
        (Array.isArray(e.special) && e.special.length > 0)
      ))
      .map(([id, e]: any) => ({ id, name: e.name, hp: e.hp, atk: e.atk, def: e.def, special: e.special }));

    // Last floor detail
    const tileMap: Record<number, any> = {};
    const tiles = new Set<number>();
    for (const row of (lastFloor?.map || []) as number[][]) for (const t of row) if (t) tiles.add(t);
    for (const t of tiles) { try { tileMap[t] = c.getBlockInfo(t); } catch {} }
    const lastCells: any[][] = [];
    for (const row of (lastFloor?.map || []) as number[][]) {
      lastCells.push(row.map((t: number) => t ? (tileMap[t]?.id || '?') : '_'));
    }

    return JSON.parse(JSON.stringify({
      lastFloorEvents: lastFloor?.events,
      lastCells: lastCells.slice(0, 13),
      bossMonsters,
      specialMonsters,
      afterBattles: afterBattles.slice(0, 5),
      floorCount: fids.length,
      lastFid,
    }));
  });

  console.log(`\n=== Last floor (${info.lastFid}) map ===`);
  for (const row of info.lastCells) console.log('  ' + row.map((c: string) => c.padEnd(12)).join(''));
  console.log('\n=== Boss monsters (isBoss=1) ===');
  for (const m of info.bossMonsters) console.log(`  ${m.name}(${m.id}): HP=${m.hp} ATK=${m.atk} DEF=${m.def} special=${JSON.stringify(m.special)}`);
  console.log('\n=== Special monsters ===');
  for (const m of info.specialMonsters) console.log(`  ${m.name}(${m.id}): HP=${m.hp} ATK=${m.atk} DEF=${m.def} special=${JSON.stringify(m.special)}`);
  console.log('\n=== Last floor events ===');
  console.log(JSON.stringify(info.lastFloorEvents, null, 2)?.slice(0, 3000));
  console.log('\n=== Floors with afterBattle ===');
  for (const ab of info.afterBattles) console.log(`  F${ab.floor}(${ab.fid}):`, JSON.stringify(ab.afterBattle)?.slice(0, 200));
  await browser.close();
}
main().catch(console.error);
