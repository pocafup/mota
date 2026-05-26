import { scrapeGame } from './scraper';
import { loadFromUniversal } from './loader/format';
import { GameState } from './types';
import { getReachable, applyAction, cellKey } from './engine';
import { buildGamePotential, upperBound } from './solver/heuristic';
import { greedyShopBuyForRender as greedyShopBuy } from './engineExtra';

async function main() {
  const uFormat = await scrapeGame('https://h5mota.com/games/51/');
  const game = loadFromUniversal(uFormat);

  const bossLoc = game.bossLocation;
  console.log(`Boss: F${bossLoc.floorId}(${bossLoc.row},${bossLoc.col})`);

  // Print boss stats
  const bossFloor = game.floors.get(bossLoc.floorId)!;
  const bossCell = bossFloor.cells[bossLoc.row][bossLoc.col];
  if (bossCell.kind === 'monster') {
    const boss = game.monsters.get(bossCell.monsterId);
    console.log(`Boss stats: ${JSON.stringify(boss)}`);
  }

  // Print initial upper bound
  const initState: GameState = {
    player: {
      ...game.initialPlayer,
      floorId: game.startFloor,
      row: game.startPos.row,
      col: game.startPos.col,
    },
    consumed: new Set(),
    consumedHash: 0,
    shopBought: new Set(),
  };
  const pot = buildGamePotential(game);
  console.log(`Initial upperBound = ${upperBound(initState, game, pot)}`);
  console.log(`Player: ATK=${initState.player.attack}, DEF=${initState.player.defense}, HP=${initState.player.hp}`);

  // Simulate going straight to F51 via F25
  // Path: F2→F3→F4→...→F25→F51
  let state = initState;

  // Quick BFS to find path to F25's boss portal stair
  // For now just check if F51 is reachable and what happens there
  const f51 = game.floors.get(51);
  if (f51) {
    console.log(`\nF51 startPos: (${f51.startPos.row},${f51.startPos.col})`);
    console.log(`F51 cells (non-empty, non-wall):`);
    for (let r = 0; r < f51.height; r++) {
      for (let c = 0; c < f51.width; c++) {
        const cell = f51.cells[r][c];
        if (cell.kind !== 'empty' && cell.kind !== 'wall') {
          console.log(`  (${r},${c}): ${JSON.stringify(cell)}`);
        }
      }
    }

    // Check reachability from F51 startPos
    const f51State: GameState = {
      player: { ...initState.player, floorId: 51, row: f51.startPos.row, col: f51.startPos.col },
      consumed: new Set(),
      consumedHash: 0,
      shopBought: new Set(),
    };
    const reachable51 = getReachable(f51State, game);
    console.log(`Reachable from F51 startPos: ${reachable51.length} cells`);
    for (const pos of reachable51) {
      const cell = f51.cells[pos.row][pos.col];
      console.log(`  (${pos.row},${pos.col}): ${JSON.stringify(cell)}`);
    }
  }

  // Check all monsters that block progress (can't be beaten by initial player)
  console.log('\nMonsters that CANNOT be beaten by initial player (ATK=260, DEF=200):');
  for (const [fid, floor] of game.floors) {
    for (let r = 0; r < floor.height; r++) {
      for (let c = 0; c < floor.width; c++) {
        const cell = floor.cells[r][c];
        if (cell.kind === 'monster') {
          const m = game.monsters.get(cell.monsterId);
          if (!m) continue;
          const playerDmg = initState.player.attack - m.defense;
          if (playerDmg <= 0) {
            console.log(`  F${fid}(${r},${c}): ${m.name} DEF=${m.defense}`);
          }
        }
      }
    }
  }
}

main().catch(console.error);
