import { scrapeGame } from './scraper';
import { loadFromUniversal } from './loader/format';

async function main() {
  const fmt = await scrapeGame('https://h5mota.com/games/51/');
  const game = loadFromUniversal(fmt);

  // Count items by type on floors
  const itemCounts: Record<string, { count: number; totalAtk: number; totalHp: number; totalDef: number }> = {};
  let totalAtkFromAll = 0;

  for (const [, floor] of game.floors) {
    for (const row of floor.cells) {
      for (const cell of row) {
        if (cell.kind !== 'item') continue;
        const item = game.items.get(cell.itemId);
        if (!item) continue;
        const ef = item.effect;
        if (!itemCounts[cell.itemId]) itemCounts[cell.itemId] = { count: 0, totalAtk: 0, totalHp: 0, totalDef: 0 };
        itemCounts[cell.itemId].count++;
        if (ef.type === 'attack') {
          const v = ef.base * floor.area;
          itemCounts[cell.itemId].totalAtk += v;
          totalAtkFromAll += v;
        } else if (ef.type === 'sword') {
          itemCounts[cell.itemId].totalAtk += ef.bonus;
          totalAtkFromAll += ef.bonus;
        } else if (ef.type === 'compound') {
          itemCounts[cell.itemId].totalAtk += ef.attack;
          itemCounts[cell.itemId].totalHp += ef.hp;
          itemCounts[cell.itemId].totalDef += ef.defense;
          totalAtkFromAll += ef.attack;
        } else if (ef.type === 'hp' || ef.type === 'hpLarge') {
          itemCounts[cell.itemId].totalHp += ef.base * floor.area;
        } else if (ef.type === 'defense' || ef.type === 'shield') {
          itemCounts[cell.itemId].totalDef += ('base' in ef) ? ef.base * floor.area : (ef as any).bonus;
        }
      }
    }
  }

  console.log('\n=== Item instances on all floors ===');
  for (const [id, s] of Object.entries(itemCounts).sort((a, b) => b[1].totalAtk - a[1].totalAtk)) {
    const item = game.items.get(id)!;
    console.log(`  ${item.name}(${id}): ×${s.count} → ATK+${s.totalAtk} HP+${s.totalHp} DEF+${s.totalDef}`);
  }

  // Max shop ATK
  let maxShopAtk = 0;
  for (const [, shop] of game.shops) {
    for (const si of shop.items) {
      if (si.effect === 'attack') maxShopAtk += si.amount;
    }
  }

  console.log(`\n=== Total ATK potential ===`);
  console.log(`  Initial ATK:      ${game.initialPlayer.attack}`);
  console.log(`  From all items:   ${totalAtkFromAll}`);
  console.log(`  From all shops:   ${maxShopAtk}`);
  console.log(`  TOTAL:            ${game.initialPlayer.attack + totalAtkFromAll + maxShopAtk}`);
  console.log(`  Boss DEF:         1000`);
  console.log(`  Can beat boss?    ${game.initialPlayer.attack + totalAtkFromAll + maxShopAtk > 1000 ? 'YES' : 'NO'}`);
}
main().catch(console.error);
