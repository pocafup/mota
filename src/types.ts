// ============================================================
// 核心类型定义
// ============================================================

export interface MonsterDef {
  id: string;
  name: string;
  hp: number;
  attack: number;
  defense: number;
  gold: number;
  isBoss?: boolean;
  /** 特殊属性：magic=魔法攻击(忽略防御), firstStrike=先手攻击 */
  special?: string[];
}

export interface ItemDef {
  id: string;
  name: string;
  effect: ItemEffect;
}

export type ItemEffect =
  | { type: 'hp'; base: number }          // 恢复 base * area 点血量
  | { type: 'hpLarge'; base: number }     // 恢复 base * area 点血量（大血瓶）
  | { type: 'attack'; base: number }      // 攻击力 +base * area
  | { type: 'defense'; base: number }     // 防御力 +base * area
  | { type: 'yellowKey' }                  // 获得黄钥匙
  | { type: 'blueKey' }                    // 获得蓝钥匙
  | { type: 'redKey' }                     // 获得红钥匙
  | { type: 'sword'; bonus: number }      // 攻击力固定加成
  | { type: 'shield'; bonus: number }     // 防御力固定加成
  | { type: 'compound'; hp: number; attack: number; defense: number }; // 复合加成（固定值）

export type DoorColor = 'yellow' | 'blue' | 'red';

export type CellContent =
  | { kind: 'empty' }
  | { kind: 'wall' }
  | { kind: 'stairsUp'; toFloor: number }
  | { kind: 'stairsDown'; toFloor: number }
  | { kind: 'monster'; monsterId: string }
  | { kind: 'item'; itemId: string }
  | { kind: 'door'; color: DoorColor }
  | { kind: 'shop'; shopId: string }
  | { kind: 'npc'; npcId: string };      // NPC（目前不处理）

export interface Floor {
  id: number;
  /** 区域编号 1-5，决定宝石/血瓶的加成倍率 */
  area: number;
  width: number;
  height: number;
  /** cells[row][col] */
  cells: CellContent[][];
  /** 从下层楼梯进入时的起始位置 */
  startPos: { row: number; col: number };
}

export interface ShopDef {
  id: string;
  items: ShopItem[];
}

export interface ShopItem {
  label: string;
  effect: 'attack' | 'defense' | 'hp' | 'yellowKey' | 'blueKey' | 'redKey';
  amount: number;
  cost: number;
  /** 是否可多次购买 */
  repeatable: boolean;
}

// ============================================================
// 游戏状态
// ============================================================

export interface PlayerState {
  floorId: number;
  row: number;
  col: number;
  hp: number;
  maxHp: number;   // 当前轮次不限制最大血量（魔塔一般无上限）
  attack: number;
  defense: number;
  gold: number;
  yellowKeys: number;
  blueKeys: number;
  redKeys: number;
}

export interface GameState {
  player: PlayerState;
  /**
   * 已消耗的格子：拾取物品、击败怪物、开门后加入此集合
   * 格式："floorId,row,col"
   */
  consumed: Set<string>;
  /**
   * Zobrist XOR hash of all cellKeys in consumed — maintained incrementally
   * so stateKey() is O(1) instead of O(n log n).
   */
  consumedHash: number;
  /**
   * 已购买的商店物品（对于不可重复购买的）
   * 格式："shopId,itemIndex"
   */
  shopBought: Set<string>;
}

// ============================================================
// 搜索相关
// ============================================================

export interface Action {
  type: 'move' | 'fight' | 'pickup' | 'openDoor' | 'useStairs' | 'buyShop';
  targetFloor: number;
  targetRow: number;
  targetCol: number;
  description: string;
}

export interface SolverResult {
  success: boolean;
  finalHp: number;
  actions: Action[];
  summary: string;
}

export interface GameData {
  monsters: Map<string, MonsterDef>;
  items: Map<string, ItemDef>;
  floors: Map<number, Floor>;
  shops: Map<string, ShopDef>;
  /** 初始玩家属性 */
  initialPlayer: Omit<PlayerState, 'floorId' | 'row' | 'col'>;
  /** 起始楼层和位置 */
  startFloor: number;
  startPos: { row: number; col: number };
  /** Boss所在位置（胜利条件） */
  bossLocation: { floorId: number; row: number; col: number };
}
