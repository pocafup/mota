/**
 * Sweep greedy solver: on each floor, exhaust all items/doors/monsters before going up.
 * After each floor sweep, go to the highest accessible floor.
 * This simulates the classic magic tower "collect everything, then advance" strategy.
 */
import { scrapeGame } from './scraper';
import { loadFromUniversal } from './loader/format';
import { GameState, GameData } from './types';
import { getReachable, applyAction, calcDamage, cellKey } from './engine';
import { buildGamePotential, upperBound } from './solver/heuristic';
import { greedyShopBuyForRender as greedyShopBuy } from './engineExtra';

function actionPriority(state: GameState, pos: {floorId:number,row:number,col:number}, game: GameData): number {
  const floor = game.floors.get(pos.floorId)!;
  const cell = floor.cells[pos.row][pos.col];
  // Same floor actions first, high-value items/monsters > doors > stairs
  const floorBonus = pos.floorId === state.player.floorId ? 10000 : -Math.abs(pos.floorId - state.player.floorId) * 100;
  switch (cell.kind) {
    case 'item': return floorBonus + 500;
    case 'shop': return floorBonus + 300;
    case 'monster': {
      const m = game.monsters.get(cell.monsterId);
      if (!m) return floorBonus;
      const dmg = calcDamage(state.player, m);
      return floorBonus + 200 - dmg * 0.1;
    }
    case 'door': return floorBonus + 100;
    case 'stairsUp': return -5000 + pos.floorId * 10;  // Go up only when needed
    case 'stairsDown': return -10000;  // Almost never go down
    default: return floorBonus;
  }
}

async function main() {
  const uFormat = await scrapeGame('https://h5mota.com/games/51/');
  const game = loadFromUniversal(uFormat);
  const pot = buildGamePotential(game);
  const bossKey = cellKey(game.bossLocation.floorId, game.bossLocation.row, game.bossLocation.col);

  let state: GameState = {
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

  console.log(`Start: F${state.player.floorId}, HP=${state.player.hp}, ATK=${state.player.attack}, DEF=${state.player.defense}`);
  console.log(`Boss: F${game.bossLocation.floorId}(${game.bossLocation.row},${game.bossLocation.col})`);

  let step = 0;
  let lastFloor = state.player.floorId;
  const MAX_STEPS = 5000;
  let lastConsumedSize = 0;
  let stuckSteps = 0;

  while (step < MAX_STEPS) {
    // Check victory
    if (state.consumed.has(bossKey)) {
      console.log(`\n✅ BOSS DEFEATED at step ${step}! Final HP=${state.player.hp}`);
      break;
    }

    const reachable = getReachable(state, game);
    if (reachable.length === 0) {
      console.log(`\n❌ DEAD END at step ${step}: F${state.player.floorId}(${state.player.row},${state.player.col})`);
      console.log(`HP=${state.player.hp} ATK=${state.player.attack} DEF=${state.player.defense}`);
      console.log(`Keys: Y=${state.player.yellowKeys} B=${state.player.blueKeys} R=${state.player.redKeys}`);
      break;
    }

    // Sort by priority, pick best
    reachable.sort((a, b) => actionPriority(state, b, game) - actionPriority(state, a, game));

    let moved = false;
    for (const pos of reachable) {
      const result = applyAction(state, pos, game);
      if (!result || result.newState.player.hp <= 0) continue;
      state = result.newState;

      // Apply shop if needed
      const floor = game.floors.get(pos.floorId)!;
      const cell = floor.cells[pos.row][pos.col];
      if (cell.kind === 'shop') {
        state = greedyShopBuy(state, cell.shopId, game);
      }

      moved = true;

      if (state.player.floorId !== lastFloor) {
        lastFloor = state.player.floorId;
        console.log(`[Step ${step}] F${lastFloor}: HP=${state.player.hp} ATK=${state.player.attack} DEF=${state.player.defense} Keys:Y${state.player.yellowKeys}B${state.player.blueKeys}R${state.player.redKeys} consumed=${state.consumed.size}`);
      }
      break;
    }

    if (!moved) {
      console.log(`\n❌ No valid move at step ${step}: F${state.player.floorId}(${state.player.row},${state.player.col})`);
      break;
    }

    // Detect stuck loop (no new cells consumed for 20 steps)
    if (state.consumed.size === lastConsumedSize) {
      stuckSteps++;
      if (stuckSteps >= 20) {
        console.log(`\n⚠️ STUCK at step ${step}: F${state.player.floorId}(${state.player.row},${state.player.col}) — no progress for 20 steps`);
        break;
      }
    } else {
      lastConsumedSize = state.consumed.size;
      stuckSteps = 0;
    }

    step++;
  }

  // Show how close to boss
  const bossFloor = game.floors.get(game.bossLocation.floorId)!;
  const bossCell = bossFloor.cells[game.bossLocation.row][game.bossLocation.col];
  if (bossCell.kind === 'monster') {
    const boss = game.monsters.get(bossCell.monsterId);
    if (boss) {
      const dmg = calcDamage(state.player, boss);
      const canWin = state.player.hp > dmg;
      console.log(`\nBoss: ATK=${boss.attack} DEF=${boss.defense} HP=${boss.hp}`);
      console.log(`Fight damage: ${dmg} HP — player would ${canWin ? 'SURVIVE' : 'DIE'}`);
      if (dmg === Infinity) {
        console.log(`  (Can't damage boss — ATK=${state.player.attack} vs boss DEF=${boss.defense})`);
      }
    }
  }
}

main().catch(console.error);
