import { scrapeGame } from './scraper';
import { loadFromUniversal } from './loader/format';
import { GameState, GameData } from './types';
import { getReachable, applyAction, calcDamage } from './engine';
import { buildGamePotential, upperBound } from './solver/heuristic';
import { greedyShopBuyForRender as greedyShopBuy } from './engineExtra';

// Quick greedy solver that tries to go as high as possible
// Uses a smarter greedy: prioritize higher floors
async function main() {
  const uFormat = await scrapeGame('https://h5mota.com/games/51/');
  const game = loadFromUniversal(uFormat);
  const pot = buildGamePotential(game);

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

  console.log(`Boss: F${game.bossLocation.floorId}(${game.bossLocation.row},${game.bossLocation.col})`);
  console.log(`Initial upperBound = ${upperBound(initState, game, pot)}`);

  // Use priority: prefer higher floors, then items, then monsters
  function prioritize(state: GameState, pos: {floorId:number,row:number,col:number}): number {
    const floor = game.floors.get(pos.floorId)!;
    const cell = floor.cells[pos.row][pos.col];
    // Strongly prefer higher floors
    let score = pos.floorId * 10000;
    switch (cell.kind) {
      case 'item': score += 200; break;
      case 'stairsUp': score += 1000; break;
      case 'stairsDown': score -= 500; break;
      case 'door': score += 50; break;
      case 'monster': {
        const m = game.monsters.get(cell.monsterId);
        if (m) score += 100 - calcDamage(state.player, m);
        break;
      }
    }
    return score;
  }

  let state = initState;
  let step = 0;
  const maxSteps = 2000;
  let highestFloor = 0;

  while (step < maxSteps) {
    const reachable = getReachable(state, game);
    if (reachable.length === 0) {
      console.log(`\n[Step ${step}] DEAD END at F${state.player.floorId}(${state.player.row},${state.player.col})`);
      console.log(`HP=${state.player.hp} ATK=${state.player.attack} DEF=${state.player.defense}`);
      console.log(`Keys: Y=${state.player.yellowKeys} B=${state.player.blueKeys} R=${state.player.redKeys}`);
      break;
    }

    // Sort by priority
    reachable.sort((a, b) => prioritize(state, b) - prioritize(state, a));
    const best = reachable[0];

    const result = applyAction(state, best, game);
    if (!result || result.newState.player.hp <= 0) {
      // Skip this action, try next
      const result2 = reachable.length > 1 ? applyAction(state, reachable[1], game) : null;
      if (!result2 || result2.newState.player.hp <= 0) {
        console.log(`\n[Step ${step}] DIED or failed at F${best.floorId}(${best.row},${best.col})`);
        break;
      }
      state = result2.newState;
    } else {
      state = result.newState;
    }

    // Apply shop if landed on one
    const floor = game.floors.get(best.floorId)!;
    const cell = floor.cells[best.row][best.col];
    if (cell.kind === 'shop') {
      state = greedyShopBuy(state, cell.shopId, game);
    }

    if (state.player.floorId > highestFloor) {
      highestFloor = state.player.floorId;
      console.log(`[Step ${step}] Reached F${highestFloor}! HP=${state.player.hp} ATK=${state.player.attack} DEF=${state.player.defense} Keys:Y${state.player.yellowKeys}B${state.player.blueKeys}R${state.player.redKeys}`);
    }

    // Check boss
    const bossKey = `${game.bossLocation.floorId},${game.bossLocation.row},${game.bossLocation.col}`;
    if (state.consumed.has(bossKey)) {
      console.log(`\n*** BOSS DEFEATED at step ${step}! Final HP=${state.player.hp} ***`);
      break;
    }

    step++;
  }

  console.log(`\nFinal state: F${state.player.floorId}(${state.player.row},${state.player.col})`);
  console.log(`HP=${state.player.hp} ATK=${state.player.attack} DEF=${state.player.defense}`);
  console.log(`Keys: Y=${state.player.yellowKeys} B=${state.player.blueKeys} R=${state.player.redKeys}`);
  console.log(`Consumed: ${state.consumed.size} cells`);

  // Show how close to boss
  const bossFloor = game.floors.get(game.bossLocation.floorId)!;
  const bossCell = bossFloor.cells[game.bossLocation.row][game.bossLocation.col];
  if (bossCell.kind === 'monster') {
    const boss = game.monsters.get(bossCell.monsterId);
    if (boss) {
      const dmg = calcDamage(state.player, boss);
      console.log(`\nBoss fight damage if fought now: ${dmg} HP (boss ATK=${boss.attack} DEF=${boss.defense} HP=${boss.hp})`);
      console.log(`Player would ${state.player.hp > dmg ? 'SURVIVE' : 'DIE'}`);
    }
  }
}

main().catch(console.error);
