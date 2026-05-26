import { scrapeGame } from './scraper';
import { loadFromUniversal } from './loader/format';

async function main() {
  const fmt = await scrapeGame('https://h5mota.com/games/51/');
  const game = loadFromUniversal(fmt);

  console.log('\n=== Items ===');
  for (const [id, item] of game.items) {
    console.log(`  ${id}: ${item.name}`, JSON.stringify(item.effect));
  }

  console.log('\n=== Monsters (sorted by HP) ===');
  const monsters = Array.from(game.monsters.values()).sort((a, b) => b.hp - a.hp);
  for (const m of monsters.slice(0, 20)) {
    console.log(`  ${m.name}: HP=${m.hp} ATK=${m.attack} DEF=${m.defense} Gold=${m.gold} Special=${JSON.stringify(m.special)}`);
  }

  console.log('\n=== Start ===');
  console.log('  startFloor:', game.startFloor);
  console.log('  startPos:', game.startPos);
  console.log('  initialPlayer:', game.initialPlayer);

  // Count items on each floor
  console.log('\n=== Floor summary ===');
  for (const [fid, floor] of game.floors) {
    let items = 0, monsters = 0, doors = 0, stairs = 0;
    for (const row of floor.cells) {
      for (const cell of row) {
        if (cell.kind === 'item') items++;
        else if (cell.kind === 'monster') monsters++;
        else if (cell.kind === 'door') doors++;
        else if (cell.kind === 'stairsUp' || cell.kind === 'stairsDown') stairs++;
      }
    }
    if (items + monsters + doors > 0) {
      console.log(`  F${fid}: items=${items} monsters=${monsters} doors=${doors} stairs=${stairs} area=${floor.area}`);
    }
  }
}

main().catch(console.error);
