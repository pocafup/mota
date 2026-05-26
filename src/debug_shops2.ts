import { scrapeGame } from './scraper';
import { loadFromUniversal } from './loader/format';

async function main() {
  const fmt = await scrapeGame('https://h5mota.com/games/51/');
  const game = loadFromUniversal(fmt);

  console.log('\n=== Shops ===');
  console.log(`Total shops: ${game.shops.size}`);
  for (const [id, shop] of game.shops) {
    console.log(`\n  ${id}: ${shop.items.length} items`);
    for (const item of shop.items.slice(0, 5)) {
      console.log(`    ${item.label}: ${item.effect}+${item.amount} for ${item.cost} gold`);
    }
    if (shop.items.length > 5) console.log(`    ... and ${shop.items.length - 5} more`);
  }

  // Estimate max ATK possible
  const maxAtkFromShops = Array.from(game.shops.values()).reduce((sum, shop) => {
    return sum + shop.items.filter(i => i.effect === 'attack').reduce((s, i) => s + i.amount, 0);
  }, 0);
  const maxAtkFromItems = Array.from(game.items.values()).reduce((sum, item) => {
    const ef = item.effect;
    if (ef.type === 'sword') return sum + ef.bonus;
    if (ef.type === 'attack') return sum + ef.base * 5; // max area
    return sum;
  }, 0);
  console.log('\n=== ATK potential ===');
  console.log(`Max ATK from shops: ${maxAtkFromShops}`);
  console.log(`Max ATK from items: ~${maxAtkFromItems}`);
  console.log(`Total max ATK: ~${100 + maxAtkFromShops + maxAtkFromItems} (need >1000 to beat boss)`);

  // Check shop cells on floors
  let shopCells = 0;
  for (const [, floor] of game.floors) {
    for (const row of floor.cells) {
      for (const cell of row) {
        if (cell.kind === 'shop') shopCells++;
      }
    }
  }
  console.log(`\nShop cells on floors: ${shopCells}`);
}

main().catch(console.error);
