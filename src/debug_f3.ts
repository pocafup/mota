import { scrapeGame } from './scraper';
import { loadFromUniversal } from './loader/format';
import { getReachable } from './engine';
import { GameState } from './types';

async function main() {
  const uFormat = await scrapeGame('https://h5mota.com/games/51/');
  const game = loadFromUniversal(uFormat);

  // Print all cells for floors 2-6
  for (let fid = 2; fid <= 6; fid++) {
    const floor = game.floors.get(fid);
    if (!floor) { console.log(`F${fid}: missing`); continue; }
    console.log(`\n=== F${fid} startPos=(${floor.startPos.row},${floor.startPos.col}) size=${floor.height}x${floor.width} ===`);
    for (let r = 0; r < floor.height; r++) {
      for (let c = 0; c < floor.width; c++) {
        const cell = floor.cells[r][c];
        if (cell.kind !== 'empty' && cell.kind !== 'wall') {
          console.log(`  (${r},${c}): ${JSON.stringify(cell)}`);
        }
      }
    }

    // Also show what's reachable from startPos
    const state: GameState = {
      player: {
        ...game.initialPlayer,
        floorId: fid,
        row: floor.startPos.row,
        col: floor.startPos.col,
      },
      consumed: new Set(),
      consumedHash: 0,
      shopBought: new Set(),
    };
    const reachable = getReachable(state, game);
    console.log(`  Reachable from startPos: ${reachable.length} cells`);
    for (const pos of reachable) {
      const cell = floor.cells[pos.row][pos.col];
      console.log(`    (${pos.row},${pos.col}): ${JSON.stringify(cell)}`);
    }
  }
}

main().catch(console.error);
