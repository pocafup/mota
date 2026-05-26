import { chromium } from 'playwright';

async function main() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.goto('https://h5mota.com/games/51/', { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => {
    const c = (window as any).core;
    return c?.floorIds?.length > 0 && c?.material?.enemys && c?.floors;
  }, { timeout: 30000 });

  // Wait for the game to fully initialize (status.hero should have live values)
  await page.waitForFunction(() => {
    const c = (window as any).core;
    return c?.status?.hero?.atk !== undefined;
  }, { timeout: 10000 });

  const info = await page.evaluate(() => {
    const c = (window as any).core;
    const sh = (c as any).status?.hero || {};
    const fh = c.firstData?.hero || {};
    const items = c.material?.items || {};

    // Check if hero has equipment bonuses applied
    return JSON.parse(JSON.stringify({
      // Live status hero stats
      liveAtk: sh.atk,
      liveDef: sh.def,
      liveHp: sh.hp,
      liveEquips: sh.items?.equips,
      liveFlags: sh.flags,

      // firstData hero stats (initial)
      firstAtk: fh.atk,
      firstDef: fh.def,
      firstEquips: fh.items?.equips,
      firstFlags: fh.flags,

      // Sword5 and shield5 raw values
      sword5raw: items.sword5?.equip?.value,
      shield5raw: items.shield5?.equip?.value,

      // The item I300
      I300def: items.I300,
    }));
  });

  console.log('=== Live hero stats at game start ===');
  console.log(`  ATK: ${info.liveAtk} (firstData: ${info.firstAtk})`);
  console.log(`  DEF: ${info.liveDef} (firstData: ${info.firstDef})`);
  console.log(`  HP: ${info.liveHp}`);
  console.log(`  Live equips: ${JSON.stringify(info.liveEquips)}`);
  console.log(`  Live flags (equip): nowWeapon=${info.liveFlags?.nowWeapon} nowShield=${info.liveFlags?.nowShield}`);

  console.log('\n=== Sword5 raw (equip.value) ===');
  console.log(JSON.stringify(info.sword5raw));
  console.log('=== Shield5 raw (equip.value) ===');
  console.log(JSON.stringify(info.shield5raw));

  console.log('\n=== Item I300 ===');
  console.log(JSON.stringify(info.I300def));

  await browser.close();
}

main().catch(console.error);
