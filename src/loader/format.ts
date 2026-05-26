/**
 * 通用游戏数据格式（Universal Game Format）
 *
 * 使用方法：
 * 1. 在h5mota游戏页面按F12打开开发者工具 → Console
 * 2. 粘贴 extract-script.js 的内容并执行
 * 3. 将输出的JSON保存为文件
 * 4. 使用 loadFromJson() 加载
 */

import { GameData, Floor, MonsterDef, ItemDef, ShopDef, CellContent, ItemEffect } from '../types';

// ============================================================
// JSON格式定义（通用游戏描述）
// ============================================================

export interface UGameFormat {
  meta: {
    name: string;
    version?: string;
    source?: string;    // h5mota URL
  };
  initialPlayer: {
    hp: number;
    attack: number;
    defense: number;
    gold: number;
    yellowKeys?: number;
    blueKeys?: number;
    redKeys?: number;
  };
  startFloor: number;
  startPos: { row: number; col: number };
  bossLocation: { floorId: number; row: number; col: number };

  monsters: UMonster[];
  items: UItem[];
  shops?: UShop[];
  floors: UFloor[];
}

export interface UMonster {
  id: string;
  name: string;
  hp: number;
  attack: number;
  defense: number;
  gold: number;
  isBoss?: boolean;
  special?: string[];  // 'magic'=魔法攻击, 'firstStrike'=先手, 'poison'=毒
}

export interface UItem {
  id: string;
  name: string;
  /** 效果类型 */
  effect:
    | { type: 'hp';      base: number }    // 回复 base*area 点血
    | { type: 'hpLarge'; base: number }
    | { type: 'attack';  base: number }    // 攻击+base*area
    | { type: 'defense'; base: number }
    | { type: 'sword';    bonus: number }   // 攻击+bonus（固定）
    | { type: 'shield';   bonus: number }
    | { type: 'yellowKey' }
    | { type: 'blueKey' }
    | { type: 'redKey' }
    | { type: 'compound'; hp: number; attack: number; defense: number };
}

export interface UShop {
  id: string;
  items: Array<{
    label: string;
    effect: 'attack' | 'defense' | 'hp' | 'yellowKey' | 'blueKey' | 'redKey';
    amount: number;
    cost: number;
    repeatable?: boolean;
  }>;
}

export interface UFloor {
  id: number;
  area: number;
  width: number;
  height: number;
  /** 从下层楼梯进入的位置 */
  startPos: { row: number; col: number };
  /**
   * 地图格子，cells[row][col]
   * 格式：
   *   null / 'empty'               = 空地
   *   'wall'                       = 墙
   *   'stairsUp:N'                 = 上行楼梯到第N层
   *   'stairsDown:N'               = 下行楼梯到第N层
   *   'door:yellow'/'door:blue'/'door:red'  = 门
   *   'monster:monsterId'          = 怪物
   *   'item:itemId'                = 物品
   *   'shop:shopId'                = 商店
   */
  cells: (string | null)[][];
}

// ============================================================
// 解析器：UGameFormat → GameData
// ============================================================

export function loadFromUniversal(u: UGameFormat): GameData {
  const monsters = new Map<string, MonsterDef>(
    u.monsters.map(m => [m.id, m])
  );

  const items = new Map<string, ItemDef>(
    u.items.map(i => [i.id, { id: i.id, name: i.name, effect: i.effect as ItemEffect }])
  );

  const shops = new Map<string, ShopDef>(
    (u.shops ?? []).map(s => [s.id, {
      id: s.id,
      items: s.items.map(si => ({
        label: si.label,
        effect: si.effect,
        amount: si.amount,
        cost: si.cost,
        repeatable: si.repeatable ?? true,
      }))
    }])
  );

  const floors = new Map<number, Floor>(
    u.floors.map(f => [f.id, parseFloor(f)])
  );

  return {
    monsters,
    items,
    floors,
    shops,
    initialPlayer: {
      hp:          u.initialPlayer.hp,
      maxHp:       999999,
      attack:      u.initialPlayer.attack,
      defense:     u.initialPlayer.defense,
      gold:        u.initialPlayer.gold,
      yellowKeys:  u.initialPlayer.yellowKeys ?? 0,
      blueKeys:    u.initialPlayer.blueKeys ?? 0,
      redKeys:     u.initialPlayer.redKeys ?? 0,
    },
    startFloor:    u.startFloor,
    startPos:      u.startPos,
    bossLocation:  u.bossLocation,
  };
}

function parseFloor(f: UFloor): Floor {
  const cells: CellContent[][] = f.cells.map(row =>
    row.map(cell => parseCell(cell))
  );
  return {
    id:       f.id,
    area:     f.area,
    width:    f.width,
    height:   f.height,
    startPos: f.startPos,
    cells,
  };
}

function parseCell(cell: string | null): CellContent {
  if (!cell || cell === 'empty') return { kind: 'empty' };
  if (cell === 'wall') return { kind: 'wall' };

  const [type, arg] = cell.split(':');
  switch (type) {
    case 'wall':        return { kind: 'wall' };
    case 'stairsUp':    return { kind: 'stairsUp',   toFloor: parseInt(arg) };
    case 'stairsDown':  return { kind: 'stairsDown',  toFloor: parseInt(arg) };
    case 'door':
      if (arg === 'yellow' || arg === 'blue' || arg === 'red')
        return { kind: 'door', color: arg };
      return { kind: 'wall' };
    case 'monster':     return { kind: 'monster', monsterId: arg };
    case 'item':        return { kind: 'item',    itemId: arg };
    case 'shop':        return { kind: 'shop',    shopId: arg };
    case 'npc':         return { kind: 'npc',     npcId: arg };
    default:            return { kind: 'empty' };
  }
}
