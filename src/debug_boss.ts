import { scrapeGame } from './scraper';
import { loadFromUniversal } from './loader/format';

async function main() {
  const fmt = await scrapeGame('https://h5mota.com/games/51/');
  const game = loadFromUniversal(fmt);

  // Find all high-HP monsters in all floors
  const allMonsters: Array<{floor: number, row: number, col: number, id: string, name: string, hp: number}> = [];
  for (const [fid, floor] of game.floors) {
    for (let r = 0; r < floor.height; r++) {
      for (let c = 0; c < floor.width; c++) {
        const cell = floor.cells[r][c];
        if (cell.kind === 'monster') {
          const m = game.monsters.get(cell.monsterId);
          if (m && m.hp > 500) {
            allMonsters.push({ floor: fid, row: r, col: c, id: cell.monsterId, name: m.name, hp: m.hp });
          }
        }
      }
    }
  }
  allMonsters.sort((a, b) => b.hp - a.hp);
  console.log('High-HP monsters (HP>500):');
  for (const m of allMonsters.slice(0, 15)) {
    console.log(`  F${m.floor} [${m.row},${m.col}] ${m.name} (${m.id}) HP=${m.hp}`);
  }

  console.log('\nbossLocation:', game.bossLocation);
  const bl = game.bossLocation;
  const bFloor = game.floors.get(bl.floorId);
  if (bFloor) {
    const bc = bFloor.cells[bl.row][bl.col];
    console.log('boss cell:', bc);
    if (bc.kind === 'monster') {
      console.log('boss monster:', game.monsters.get(bc.monsterId));
    }
  }

  // Show last few floors
  console.log('\nLast floor (F51) monsters:');
  const f51 = game.floors.get(51);
  if (f51) {
    for (let r = 0; r < f51.height; r++) {
      for (let c = 0; c < f51.width; c++) {
        const cell = f51.cells[r][c];
        if (cell.kind === 'monster') {
          const m = game.monsters.get(cell.monsterId);
          console.log(`  [${r},${c}] ${m?.name} HP=${m?.hp}`);
        }
      }
    }
  }
}

main().catch(console.error);
