/**
 * Count doors vs keys per floor to find key bottlenecks
 */
import { scrapeGame } from './scraper';
import { loadFromUniversal } from './loader/format';

async function main() {
  const uFormat = await scrapeGame('https://h5mota.com/games/51/');
  const game = loadFromUniversal(uFormat);

  let cumYDoors = 0, cumBDoors = 0, cumRDoors = 0;
  let cumYKeys = 0, cumBKeys = 0, cumRKeys = 0;

  console.log('Floor | YDoors  BDoors  RDoors | YKeys  BKeys  RKeys | CumYBal  CumBBal  CumRBal');

  for (const [fid, floor] of [...game.floors.entries()].sort((a, b) => a[0] - b[0])) {
    let yDoors = 0, bDoors = 0, rDoors = 0;
    let yKeys = 0, bKeys = 0, rKeys = 0;

    for (let r = 0; r < floor.height; r++) {
      for (let c = 0; c < floor.width; c++) {
        const cell = floor.cells[r][c];
        if (cell.kind === 'door') {
          if (cell.color === 'yellow') yDoors++;
          if (cell.color === 'blue')   bDoors++;
          if (cell.color === 'red')    rDoors++;
        }
        if (cell.kind === 'item') {
          const item = game.items.get(cell.itemId);
          if (!item) continue;
          if (item.effect.type === 'yellowKey') yKeys++;
          if (item.effect.type === 'blueKey')   bKeys++;
          if (item.effect.type === 'redKey')    rKeys++;
        }
      }
    }

    cumYDoors += yDoors; cumBDoors += bDoors; cumRDoors += rDoors;
    cumYKeys += yKeys; cumBKeys += bKeys; cumRKeys += rKeys;

    if (yDoors > 0 || bDoors > 0 || rDoors > 0 || yKeys > 0 || bKeys > 0 || rKeys > 0) {
      const yBal = cumYKeys - cumYDoors;
      const bBal = cumBKeys - cumBDoors;
      const rBal = cumRKeys - cumRDoors;
      const warning = (yBal < 0 || bBal < 0 || rBal < 0) ? ' ⚠️ KEY DEFICIT' : '';
      console.log(`F${fid.toString().padStart(2)}: Y:${yDoors}D/${yKeys}K  B:${bDoors}D/${bKeys}K  R:${rDoors}D/${rKeys}K | cumYBal=${yBal}  cumBBal=${bBal}  cumRBal=${rBal}${warning}`);
    }
  }

  // Also list trader shops that sell keys
  console.log('\n=== Key trader shops ===');
  for (const [sid, shop] of game.shops) {
    for (const item of shop.items) {
      if (item.effect === 'yellowKey' || item.effect === 'blueKey' || item.effect === 'redKey') {
        console.log(`${sid}: ${item.label} (${item.effect}+${item.amount}) cost=${item.cost}`);
      }
    }
  }
}

main().catch(console.error);
