import * as fs from 'fs';
import * as path from 'path';
import { scrapeGame } from './scraper';
import { loadFromUniversal, UGameFormat } from './loader/format';
import { GameData, GameState } from './types';
import { getReachable, applyAction, cellKey } from './engine';
import { buildGamePotential, upperBound } from './solver/heuristic';

async function main() {
  const uFormat = await scrapeGame('https://h5mota.com/games/51/');
  const game = loadFromUniversal(uFormat);

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

  console.log(`startFloor=${game.startFloor}  startPos=(${game.startPos.row},${game.startPos.col})`);
  console.log(`initialPlayer:`, game.initialPlayer);
  console.log(`bossLocation: F${game.bossLocation.floorId}(${game.bossLocation.row},${game.bossLocation.col})`);

  const pot = buildGamePotential(game);
  console.log(`\nInitial upperBound = ${upperBound(initState, game, pot)}`);

  // Simulate a few steps manually
  let state = initState;
  let step = 0;
  while (step < 80) {
    const reachable = getReachable(state, game);
    if (reachable.length === 0) {
      console.log(`\n[Step ${step}] No reachable cells! Dead end at F${state.player.floorId}(${state.player.row},${state.player.col}) HP=${state.player.hp}`);
      break;
    }

    // Pick the first reachable cell (greedy depth-first)
    const pos = reachable[0];
    const result = applyAction(state, pos, game);
    if (!result || result.newState.player.hp <= 0) {
      console.log(`[Step ${step}] Action failed or died at F${pos.floorId}(${pos.row},${pos.col})`);
      break;
    }
    state = result.newState;
    const floor = game.floors.get(pos.floorId)!;
    const cell = floor.cells[pos.row][pos.col];
    step++;
    console.log(`[${step}] F${pos.floorId}(${pos.row},${pos.col}) ${JSON.stringify(cell)} → HP:${state.player.hp} ATK:${state.player.attack} DEF:${state.player.defense} Y:${state.player.yellowKeys} B:${state.player.blueKeys} R:${state.player.redKeys} reachable=${reachable.length}`);

    // Check if on boss floor
    if (pos.floorId === game.bossLocation.floorId) {
      console.log(`  ** On boss floor **`);
    }
  }

  // Show which floors are accessible (have stairway connections)
  console.log('\n--- Floor connectivity ---');
  for (const [fid, floor] of game.floors) {
    const stairs: string[] = [];
    for (let r = 0; r < floor.height; r++) {
      for (let c = 0; c < floor.width; c++) {
        const cell = floor.cells[r][c];
        if (cell.kind === 'stairsUp' || cell.kind === 'stairsDown') {
          stairs.push(`(${r},${c})→F${cell.toFloor}`);
        }
      }
    }
    console.log(`  F${fid}: stairs=[${stairs.join(', ')}]`);
  }
}

main().catch(console.error);
