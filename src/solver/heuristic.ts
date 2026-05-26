import { GameState, GameData, ItemEffect, PlayerState } from '../types';
import { cellKey } from '../engine';

// ============================================================
// 预计算缓存（避免 upperBound 每次扫描全部格子）
// ============================================================

export interface GamePotential {
  totalHp:   number;   // 所有血瓶/大血瓶的 HP 总和
  totalAtk:  number;   // 所有攻击宝石/武器的 ATK 总和
  totalDef:  number;   // 所有防御宝石/盾牌的 DEF 总和
  totalGold: number;   // 所有怪物的金币总和
  cellHp:    Map<string, number>;  // 每个格子的 HP 贡献
  cellAtk:   Map<string, number>;  // 每个格子的 ATK 贡献
  cellDef:   Map<string, number>;  // 每个格子的 DEF 贡献
  cellGold:  Map<string, number>;  // 每个格子的金币贡献
  bestGoldAtkRate: number;  // 最佳商店的金币换ATK比率（ATK/gold）
  bossKey: string;
}

export function buildGamePotential(data: GameData): GamePotential {
  const cellHp   = new Map<string, number>();
  const cellAtk  = new Map<string, number>();
  const cellDef  = new Map<string, number>();
  const cellGold = new Map<string, number>();
  let totalHp = 0, totalAtk = 0, totalDef = 0, totalGold = 0;

  for (const [, floor] of data.floors) {
    for (let r = 0; r < floor.height; r++) {
      for (let c = 0; c < floor.width; c++) {
        const key = cellKey(floor.id, r, c);
        const cell = floor.cells[r][c];
        if (cell.kind === 'item') {
          const ef = data.items.get(cell.itemId)?.effect;
          if (!ef) continue;
          if (ef.type === 'hp' || ef.type === 'hpLarge') {
            const v = ef.base * floor.area;
            cellHp.set(key, v); totalHp += v;
          } else if (ef.type === 'attack') {
            const v = ef.base * floor.area;
            cellAtk.set(key, v); totalAtk += v;
          } else if (ef.type === 'defense') {
            const v = ef.base * floor.area;
            cellDef.set(key, v); totalDef += v;
          } else if (ef.type === 'sword') {
            cellAtk.set(key, ef.bonus); totalAtk += ef.bonus;
          } else if (ef.type === 'shield') {
            cellDef.set(key, ef.bonus); totalDef += ef.bonus;
          } else if (ef.type === 'compound') {
            if (ef.hp > 0)      { cellHp.set(key,  ef.hp);      totalHp  += ef.hp;  }
            if (ef.attack > 0)  { cellAtk.set(key, ef.attack);  totalAtk += ef.attack; }
            if (ef.defense > 0) { cellDef.set(key, ef.defense); totalDef += ef.defense; }
          }
        } else if (cell.kind === 'monster') {
          const m = data.monsters.get(cell.monsterId);
          if (m && m.gold > 0) {
            cellGold.set(key, m.gold); totalGold += m.gold;
          }
        }
      }
    }
  }

  // Compute best gold-to-ATK rate across all shops (ATK gained per 1 gold spent)
  let bestGoldAtkRate = 0;
  for (const [, shop] of data.shops) {
    for (const item of shop.items) {
      if (item.effect === 'attack' && item.cost > 0) {
        const rate = item.amount / item.cost;
        if (rate > bestGoldAtkRate) bestGoldAtkRate = rate;
      }
    }
  }

  const bl = data.bossLocation;
  return {
    totalHp, totalAtk, totalDef, totalGold,
    cellHp, cellAtk, cellDef, cellGold,
    bestGoldAtkRate,
    bossKey: cellKey(bl.floorId, bl.row, bl.col),
  };
}

/**
 * 乐观上界（快速版）：O(consumed.size) 而非 O(total cells)
 * 假设能无代价地收集所有剩余物品 + 用所有金币买攻击力。
 */
export function upperBound(state: GameState, data: GameData, pot?: GamePotential): number {
  let hp   = state.player.hp;
  let atk  = state.player.attack;
  let def  = state.player.defense;
  let gold = state.player.gold;

  if (pot) {
    // 快速路径：从总量减去已消耗格子的贡献
    let remHp = pot.totalHp, remAtk = pot.totalAtk, remDef = pot.totalDef, remGold = pot.totalGold;
    for (const key of state.consumed) {
      const h = pot.cellHp.get(key);   if (h)  remHp   -= h;
      const a = pot.cellAtk.get(key);  if (a)  remAtk  -= a;
      const d = pot.cellDef.get(key);  if (d)  remDef  -= d;
      const g = pot.cellGold.get(key); if (g)  remGold -= g;
    }
    hp += remHp; atk += remAtk; def += remDef;

    // Gold actually held can be spent at the best shop rate.
    // Using only currentGold (not remGold) means fighting monsters to earn gold
    // RAISES the UB (via reduced boss correction), incentivizing monster fights.
    if (pot.bestGoldAtkRate > 0) {
      atk += state.player.gold * pot.bestGoldAtkRate;
    }

    // Keys in hand represent future unlock potential not counted above
    hp += state.player.yellowKeys * 100
      + state.player.blueKeys * 200
      + state.player.redKeys * 500;

    if (!state.consumed.has(pot.bossKey)) {
      const bl = data.bossLocation;
      const bFloor = data.floors.get(bl.floorId);
      if (bFloor) {
        const bCell = bFloor.cells[bl.row][bl.col];
        if (bCell.kind === 'monster') {
          const boss = data.monsters.get(bCell.monsterId);
          if (boss) {
            const pDmg = Math.max(0, atk - boss.defense);
            if (pDmg > 0) {
              const rounds = Math.ceil(boss.hp / pDmg);
              hp -= Math.max(0, boss.attack - def) * (rounds - 1);
            }
          }
        }
      }
    }
    return hp;
  }

  // 慢速路径（无缓存时）：扫描全部格子
  for (const [, floor] of data.floors) {
    for (let r = 0; r < floor.height; r++) {
      for (let c = 0; c < floor.width; c++) {
        if (state.consumed.has(cellKey(floor.id, r, c))) continue;
        const cell = floor.cells[r][c];
        if (cell.kind === 'item') {
          const ef = data.items.get(cell.itemId)?.effect;
          if (!ef) continue;
          if (ef.type === 'hp')       hp  += ef.base * floor.area;
          if (ef.type === 'hpLarge')  hp  += ef.base * floor.area;
          if (ef.type === 'attack')   atk += ef.base * floor.area;
          if (ef.type === 'defense')  def += ef.base * floor.area;
          if (ef.type === 'sword')    atk += ef.bonus;
          if (ef.type === 'shield')   def += ef.bonus;
          if (ef.type === 'compound') { hp += ef.hp; atk += ef.attack; def += ef.defense; }
        }
        if (cell.kind === 'monster') {
          const m = data.monsters.get(cell.monsterId);
          if (m) gold += m.gold;
        }
      }
    }
  }

  // Keys in hand represent future unlock potential
  hp += state.player.yellowKeys * 500
    + state.player.blueKeys * 1000
    + state.player.redKeys * 2500;

  const bl = data.bossLocation;
  const bossConsumed = state.consumed.has(cellKey(bl.floorId, bl.row, bl.col));
  if (!bossConsumed) {
    const bFloor = data.floors.get(bl.floorId);
    if (bFloor) {
      const bCell = bFloor.cells[bl.row][bl.col];
      if (bCell.kind === 'monster') {
        const boss = data.monsters.get(bCell.monsterId);
        if (boss) {
          const pDmg = Math.max(0, atk - boss.defense);
          if (pDmg > 0) {
            const rounds = Math.ceil(boss.hp / pDmg);
            hp -= Math.max(0, boss.attack - def) * (rounds - 1);
          }
        }
      }
    }
  }
  return hp;
}

/**
 * 攻击力+delta 相当于多少HP（对应Boss战减少伤害量）
 */
export function attackHpEquiv(delta: number, player: PlayerState, data: GameData): number {
  const bl = data.bossLocation;
  const bFloor = data.floors.get(bl.floorId);
  if (!bFloor) return delta * 3;
  const bCell = bFloor.cells[bl.row][bl.col];
  if (bCell.kind !== 'monster') return delta * 3;
  const boss = data.monsters.get(bCell.monsterId);
  if (!boss) return delta * 3;
  const d0 = Math.max(1, player.attack - boss.defense);
  const d1 = Math.max(1, player.attack + delta - boss.defense);
  const bDmg = Math.max(0, boss.attack - player.defense);
  const r0 = Math.ceil(boss.hp / d0);
  const r1 = Math.ceil(boss.hp / d1);
  return bDmg * (r0 - r1);
}

/**
 * 防御力+delta 相当于多少HP
 */
export function defenseHpEquiv(delta: number, player: PlayerState, data: GameData): number {
  const bl = data.bossLocation;
  const bFloor = data.floors.get(bl.floorId);
  if (!bFloor) return delta * 3;
  const bCell = bFloor.cells[bl.row][bl.col];
  if (bCell.kind !== 'monster') return delta * 3;
  const boss = data.monsters.get(bCell.monsterId);
  if (!boss) return delta * 3;
  const pDmg = Math.max(1, player.attack - boss.defense);
  const rounds = Math.ceil(boss.hp / pDmg);
  const bDmg0 = Math.max(0, boss.attack - player.defense);
  const bDmg1 = Math.max(0, boss.attack - player.defense - delta);
  return (bDmg0 - bDmg1) * (rounds - 1);
}

/**
 * 物品的HP当量（用于排序优先级）
 */
export function itemHpValue(ef: ItemEffect, area: number, player: PlayerState, data: GameData): number {
  switch (ef.type) {
    case 'hp':       return ef.base * area;
    case 'hpLarge':  return ef.base * area;
    case 'attack':   return attackHpEquiv(ef.base * area, player, data);
    case 'defense':  return defenseHpEquiv(ef.base * area, player, data);
    case 'sword':    return attackHpEquiv(ef.bonus, player, data);
    case 'shield':   return defenseHpEquiv(ef.bonus, player, data);
    case 'compound': return ef.hp
      + attackHpEquiv(ef.attack, player, data)
      + defenseHpEquiv(ef.defense, player, data);
    case 'yellowKey':
    case 'blueKey':
    case 'redKey':   return 500;   // 钥匙价值高（解锁区域）
  }
}
