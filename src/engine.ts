import {
  PlayerState, GameState, Floor, CellContent, MonsterDef,
  ItemDef, ShopDef, ItemEffect, Action, GameData
} from './types';

// ============================================================
// 战斗计算
// ============================================================

/**
 * 计算玩家与怪物战斗受到的伤害（玩家先手）
 * 返回 Infinity 表示无法击败怪物（攻击力不足）
 *
 * 特殊属性：
 *   magic      = 魔法攻击，忽略玩家防御（monsterDmg = monster.attack）
 *   firstStrike = 怪物先手，玩家多吃一轮伤害
 */
export function calcDamage(player: PlayerState, monster: MonsterDef): number {
  const playerDmg = player.attack - monster.defense;
  if (playerDmg <= 0) return Infinity;  // 无法击破防御

  const special = monster.special ?? [];
  const isMagic       = special.includes('magic');
  const isFirstStrike = special.includes('firstStrike');

  const monsterDmg = isMagic
    ? monster.attack                                     // 魔法：无视防御
    : Math.max(0, monster.attack - player.defense);

  const rounds = Math.ceil(monster.hp / playerDmg);
  // 玩家先手时怪物攻击 (rounds-1) 次；怪物先手时攻击 rounds 次
  return monsterDmg * (isFirstStrike ? rounds : rounds - 1);
}

export function canBeat(player: PlayerState, monster: MonsterDef): boolean {
  return calcDamage(player, monster) < Infinity;
}

// ============================================================
// 物品效果计算
// ============================================================

export function calcItemEffect(effect: ItemEffect, area: number): Partial<PlayerState> {
  switch (effect.type) {
    case 'hp':      return { hp: effect.base * area };
    case 'hpLarge': return { hp: effect.base * area };
    case 'attack':  return { attack: effect.base * area };
    case 'defense': return { defense: effect.base * area };
    case 'sword':   return { attack: effect.bonus };
    case 'shield':  return { defense: effect.bonus };
    case 'yellowKey': return { yellowKeys: 1 };
    case 'blueKey':   return { blueKeys: 1 };
    case 'redKey':    return { redKeys: 1 };
    case 'compound':  return { hp: effect.hp, attack: effect.attack, defense: effect.defense };
  }
}

// ============================================================
// 状态工具
// ============================================================

export function cellKey(floorId: number, row: number, col: number): string {
  return `${floorId},${row},${col}`;
}

export function isConsumed(state: GameState, floorId: number, row: number, col: number): boolean {
  return state.consumed.has(cellKey(floorId, row, col));
}

// FNV-1a 32-bit hash for a cellKey string — used as Zobrist value
function cellZobrist(key: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < key.length; i++) {
    h ^= key.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return h >>> 0;
}

export function cloneState(state: GameState): GameState {
  return {
    player: { ...state.player },
    consumed: new Set(state.consumed),
    consumedHash: state.consumedHash,
    shopBought: new Set(state.shopBought),
  };
}

/** Add a cell to consumed and update the incremental Zobrist hash. */
function consumeCell(state: GameState, key: string): void {
  state.consumed.add(key);
  state.consumedHash ^= cellZobrist(key);
}

// ============================================================
// 楼梯到达位置（落点）
// 在目标楼层的 (stairRow, stairCol) 处寻找相邻空格作为到达位置；
// 找不到时回退到楼层的 startPos。
// ============================================================

function findArrivalPos(
  floor: Floor,
  stairRow: number,
  stairCol: number,
): { row: number; col: number } {
  const dirs = [
    { dr: -1, dc: 0 }, { dr: 1, dc: 0 },
    { dr: 0, dc: -1 }, { dr: 0, dc: 1 },
  ];
  for (const { dr, dc } of dirs) {
    const r = stairRow + dr, c = stairCol + dc;
    if (r < 0 || r >= floor.height || c < 0 || c >= floor.width) continue;
    const cell = floor.cells[r][c];
    if (cell.kind === 'empty' || cell.kind === 'stairsUp' || cell.kind === 'stairsDown') {
      return { row: r, col: c };
    }
  }
  return { row: floor.startPos.row, col: floor.startPos.col };
}

// ============================================================
// 可达格子的BFS（从当前位置出发）
// ============================================================

interface Pos { floorId: number; row: number; col: number; }

/**
 * 从当前玩家位置出发，BFS找出所有可达的格子（不穿越障碍）
 * 可达指：能站上去的空地，或者正好踏上去触发行动的格子（怪/门/物品/楼梯）
 */
export function getReachable(state: GameState, data: GameData): Pos[] {
  const { player, consumed } = state;
  const startFloor = player.floorId;
  const reachable: Pos[] = [];
  const visited = new Set<string>();

  const queue: Pos[] = [{ floorId: startFloor, row: player.row, col: player.col }];
  visited.add(cellKey(startFloor, player.row, player.col));

  while (queue.length > 0) {
    const pos = queue.shift()!;
    const floor = data.floors.get(pos.floorId);
    if (!floor) continue;

    const neighbors = [
      { row: pos.row - 1, col: pos.col },
      { row: pos.row + 1, col: pos.col },
      { row: pos.row, col: pos.col - 1 },
      { row: pos.row, col: pos.col + 1 },
    ];

    for (const nb of neighbors) {
      if (nb.row < 0 || nb.row >= floor.height || nb.col < 0 || nb.col >= floor.width) continue;
      const key = cellKey(pos.floorId, nb.row, nb.col);
      if (visited.has(key)) continue;
      visited.add(key);

      const cell = floor.cells[nb.row][nb.col];
      const alreadyConsumed = consumed.has(key);

      if (cell.kind === 'wall') continue;

      if (cell.kind === 'empty') {
        // 空地：可以通过，继续BFS
        queue.push({ floorId: pos.floorId, row: nb.row, col: nb.col });
        continue;
      }

      if (cell.kind === 'stairsUp' || cell.kind === 'stairsDown') {
        // 楼梯：可以踏上，加入可达列表，但不继续从此扩展（需要主动行动）
        reachable.push({ floorId: pos.floorId, row: nb.row, col: nb.col });
        // 楼梯可以走过去，也继续扩展（允许从同层楼梯旁绕过）
        queue.push({ floorId: pos.floorId, row: nb.row, col: nb.col });
        continue;
      }

      if (cell.kind === 'item') {
        if (!alreadyConsumed) {
          reachable.push({ floorId: pos.floorId, row: nb.row, col: nb.col });
        }
        // 即使已拾取，物品格变为通道，继续BFS
        queue.push({ floorId: pos.floorId, row: nb.row, col: nb.col });
        continue;
      }

      if (cell.kind === 'shop' || cell.kind === 'npc') {
        reachable.push({ floorId: pos.floorId, row: nb.row, col: nb.col });
        queue.push({ floorId: pos.floorId, row: nb.row, col: nb.col });
        continue;
      }

      if (cell.kind === 'monster') {
        if (!alreadyConsumed) {
          const monster = data.monsters.get(cell.monsterId);
          if (monster && canBeat(player, monster)) {
            // 可击败的怪：加入可达（需要战斗），战斗后格子可通行
            reachable.push({ floorId: pos.floorId, row: nb.row, col: nb.col });
            // 为了BFS继续扩展，假设怪已死（若玩家选择打）
            queue.push({ floorId: pos.floorId, row: nb.row, col: nb.col });
          }
          // 无法击败的怪：阻挡路线
        }
        // 已死亡的怪：格子可通行
        if (alreadyConsumed) {
          queue.push({ floorId: pos.floorId, row: nb.row, col: nb.col });
        }
        continue;
      }

      if (cell.kind === 'door') {
        const hasKey = (() => {
          switch (cell.color) {
            case 'yellow': return player.yellowKeys > 0;
            case 'blue':   return player.blueKeys > 0;
            case 'red':    return player.redKeys > 0;
          }
        })();
        if (!alreadyConsumed && hasKey) {
          reachable.push({ floorId: pos.floorId, row: nb.row, col: nb.col });
          // 假设开门后可通行
          queue.push({ floorId: pos.floorId, row: nb.row, col: nb.col });
        } else if (alreadyConsumed) {
          queue.push({ floorId: pos.floorId, row: nb.row, col: nb.col });
        }
        continue;
      }
    }
  }

  // 过滤掉已经在当前位置的格子，只返回需要执行动作的格子
  const currentKey = cellKey(startFloor, player.row, player.col);
  return reachable.filter(p => cellKey(p.floorId, p.row, p.col) !== currentKey);
}

// ============================================================
// 行动执行
// ============================================================

/**
 * 对指定格子执行行动，返回新状态（若无法执行则返回null）
 */
export function applyAction(
  state: GameState,
  target: Pos,
  data: GameData
): { newState: GameState; action: Action } | null {
  const { player } = state;
  const floor = data.floors.get(target.floorId);
  if (!floor) return null;

  const cell = floor.cells[target.row][target.col];
  const key = cellKey(target.floorId, target.row, target.col);
  const newState = cloneState(state);
  const newPlayer = newState.player;

  switch (cell.kind) {
    case 'monster': {
      if (newState.consumed.has(key)) return null;
      const monster = data.monsters.get(cell.monsterId);
      if (!monster) return null;
      const damage = calcDamage(player, monster);
      if (damage === Infinity) return null;
      newPlayer.hp -= damage;
      newPlayer.gold += monster.gold;
      newPlayer.floorId = target.floorId;
      newPlayer.row = target.row;
      newPlayer.col = target.col;
      consumeCell(newState, key);
      return {
        newState,
        action: {
          type: 'fight', targetFloor: target.floorId,
          targetRow: target.row, targetCol: target.col,
          description: `击败 ${monster.name}（伤害-${damage}，金币+${monster.gold}）`
        }
      };
    }

    case 'item': {
      if (newState.consumed.has(key)) return null;
      const itemDef = data.items.get(cell.itemId);
      if (!itemDef) return null;
      const delta = calcItemEffect(itemDef.effect, floor.area);
      if (delta.hp)         newPlayer.hp += delta.hp;
      if (delta.attack)     newPlayer.attack += delta.attack;
      if (delta.defense)    newPlayer.defense += delta.defense;
      if (delta.gold)       newPlayer.gold += delta.gold;
      if (delta.yellowKeys) newPlayer.yellowKeys += delta.yellowKeys;
      if (delta.blueKeys)   newPlayer.blueKeys += delta.blueKeys;
      if (delta.redKeys)    newPlayer.redKeys += delta.redKeys;
      newPlayer.floorId = target.floorId;
      newPlayer.row = target.row;
      newPlayer.col = target.col;
      consumeCell(newState, key);
      return {
        newState,
        action: {
          type: 'pickup', targetFloor: target.floorId,
          targetRow: target.row, targetCol: target.col,
          description: `拾取 ${itemDef.name}（${describeEffect(delta)}）`
        }
      };
    }

    case 'door': {
      if (newState.consumed.has(key)) return null;
      const color = cell.color;
      if (color === 'yellow' && newPlayer.yellowKeys <= 0) return null;
      if (color === 'blue'   && newPlayer.blueKeys <= 0)   return null;
      if (color === 'red'    && newPlayer.redKeys <= 0)    return null;
      if (color === 'yellow') newPlayer.yellowKeys--;
      if (color === 'blue')   newPlayer.blueKeys--;
      if (color === 'red')    newPlayer.redKeys--;
      newPlayer.floorId = target.floorId;
      newPlayer.row = target.row;
      newPlayer.col = target.col;
      consumeCell(newState, key);
      return {
        newState,
        action: {
          type: 'openDoor', targetFloor: target.floorId,
          targetRow: target.row, targetCol: target.col,
          description: `开 ${color === 'yellow' ? '黄' : color === 'blue' ? '蓝' : '红'}门`
        }
      };
    }

    case 'stairsUp':
    case 'stairsDown': {
      const destFloor = cell.toFloor;
      const destFloorData = data.floors.get(destFloor);
      if (!destFloorData) return null;
      // Arrive adjacent to the same (row,col) on the destination floor —
      // h5mota stairs always have a matching stair at the identical grid position.
      const arrival = findArrivalPos(destFloorData, target.row, target.col);
      newPlayer.floorId = destFloor;
      newPlayer.row = arrival.row;
      newPlayer.col = arrival.col;
      return {
        newState,
        action: {
          type: 'useStairs',
          targetFloor: target.floorId,
          targetRow: target.row,
          targetCol: target.col,
          description: `使用楼梯 → 第${destFloor}层`
        }
      };
    }

    case 'shop': {
      // 商店：作为一个整体"行动节点"，具体购买决策在solver中处理
      newPlayer.floorId = target.floorId;
      newPlayer.row = target.row;
      newPlayer.col = target.col;
      return {
        newState,
        action: {
          type: 'buyShop', targetFloor: target.floorId,
          targetRow: target.row, targetCol: target.col,
          description: `进入商店 ${cell.shopId}`
        }
      };
    }

    default:
      return null;
  }
}

// ============================================================
// 商店购买（独立函数）
// ============================================================

export function buyShopItem(
  state: GameState,
  shopId: string,
  itemIndex: number,
  data: GameData
): GameState | null {
  const shop = data.shops.get(shopId);
  if (!shop || itemIndex >= shop.items.length) return null;

  const shopItem = shop.items[itemIndex];
  const buyKey = `${shopId},${itemIndex}`;

  if (!shopItem.repeatable && state.shopBought.has(buyKey)) return null;
  if (state.player.gold < shopItem.cost) return null;

  const newState = cloneState(state);
  newState.player.gold -= shopItem.cost;
  if (!shopItem.repeatable) newState.shopBought.add(buyKey);

  switch (shopItem.effect) {
    case 'attack':   newState.player.attack += shopItem.amount; break;
    case 'defense':  newState.player.defense += shopItem.amount; break;
    case 'hp':       newState.player.hp += shopItem.amount; break;
    case 'yellowKey': newState.player.yellowKeys += shopItem.amount; break;
    case 'blueKey':   newState.player.blueKeys += shopItem.amount; break;
    case 'redKey':    newState.player.redKeys += shopItem.amount; break;
  }
  return newState;
}

// ============================================================
// 辅助
// ============================================================

function describeEffect(delta: Partial<PlayerState>): string {
  const parts: string[] = [];
  if (delta.hp)         parts.push(`HP+${delta.hp}`);
  if (delta.attack)     parts.push(`ATK+${delta.attack}`);
  if (delta.defense)    parts.push(`DEF+${delta.defense}`);
  if (delta.gold)       parts.push(`金币+${delta.gold}`);
  if (delta.yellowKeys) parts.push(`黄钥匙+${delta.yellowKeys}`);
  if (delta.blueKeys)   parts.push(`蓝钥匙+${delta.blueKeys}`);
  if (delta.redKeys)    parts.push(`红钥匙+${delta.redKeys}`);
  return parts.join('，');
}

/**
 * 计算打败指定怪物后玩家收益（用于评估是否值得战斗）
 * 返回：净HP影响（正=有益，负=有损）
 */
export function netFightValue(player: PlayerState, monster: MonsterDef): number {
  if (!canBeat(player, monster)) return -Infinity;
  return -calcDamage(player, monster);  // 战斗只有损失
}
