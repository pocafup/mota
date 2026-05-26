import { MonsterDef, ItemDef, Floor, ShopDef, CellContent, GameData } from './types';

// ============================================================
// 怪物数据（来自经典50层魔塔）
// ============================================================

export const MONSTERS: Map<string, MonsterDef> = new Map([
  ['monster01', { id: 'monster01', name: '绿色史莱姆', hp: 35,  attack: 18,  defense: 1,  gold: 1 }],
  ['monster02', { id: 'monster02', name: '红色史莱姆', hp: 45,  attack: 20,  defense: 2,  gold: 2 }],
  ['monster03', { id: 'monster03', name: '小蝙蝠',    hp: 35,  attack: 38,  defense: 3,  gold: 3 }],
  ['monster04', { id: 'monster04', name: '初级法师',  hp: 60,  attack: 32,  defense: 8,  gold: 5 }],
  ['monster05', { id: 'monster05', name: '骷髅人',    hp: 50,  attack: 42,  defense: 6,  gold: 6 }],
  ['monster06', { id: 'monster06', name: '骷髅士兵',  hp: 55,  attack: 52,  defense: 12, gold: 8 }],
  ['monster07', { id: 'monster07', name: '初级卫兵',  hp: 50,  attack: 48,  defense: 22, gold: 12 }],
  ['monster08', { id: 'monster08', name: '骷髅队长',  hp: 100, attack: 65,  defense: 15, gold: 30 }],
  ['monster09', { id: 'monster09', name: '大史莱姆',  hp: 130, attack: 60,  defense: 3,  gold: 8 }],
  ['monster10', { id: 'monster10', name: '大蝙蝠',    hp: 60,  attack: 100, defense: 8,  gold: 12 }],
  ['monster11', { id: 'monster11', name: '高级法师',  hp: 100, attack: 95,  defense: 30, gold: 18 }],
  ['monster12', { id: 'monster12', name: '兽人',      hp: 260, attack: 85,  defense: 5,  gold: 22 }],
  ['monster13', { id: 'monster13', name: '兽人武士',  hp: 320, attack: 120, defense: 15, gold: 30 }],
  ['monster14', { id: 'monster14', name: '石头人',    hp: 20,  attack: 100, defense: 68, gold: 28 }],
  ['monster15', { id: 'monster15', name: '大乌贼',    hp: 1200,attack: 180, defense: 20, gold: 100, isBoss: true }],
  ['monster21', { id: 'monster21', name: '中级卫兵',  hp: 100, attack: 180, defense: 110,gold: 50 }],
]);

// ============================================================
// 物品数据
// ============================================================

export const ITEMS: Map<string, ItemDef> = new Map([
  ['yellowKey',  { id: 'yellowKey',  name: '黄钥匙', effect: { type: 'yellowKey' } }],
  ['blueKey',    { id: 'blueKey',    name: '蓝钥匙', effect: { type: 'blueKey' } }],
  ['redKey',     { id: 'redKey',     name: '红钥匙', effect: { type: 'redKey' } }],
  // 血瓶：回复 base × area 点血
  ['hp',         { id: 'hp',         name: '红血瓶', effect: { type: 'hp',      base: 50 } }],
  ['hpLarge',    { id: 'hpLarge',    name: '蓝血瓶', effect: { type: 'hpLarge', base: 200 } }],
  // 宝石：+base × area 属性
  ['attackGem',  { id: 'attackGem',  name: '攻击宝石', effect: { type: 'attack',  base: 1 } }],
  ['defGem',     { id: 'defGem',     name: '防御宝石', effect: { type: 'defense', base: 1 } }],
  // 装备（固定加成）
  ['ironSword',  { id: 'ironSword',  name: '铁剑',   effect: { type: 'sword',  bonus: 10 } }],
  ['ironShield', { id: 'ironShield', name: '铁盾',   effect: { type: 'shield', bonus: 10 } }],
  ['steelSword', { id: 'steelSword', name: '钢剑',   effect: { type: 'sword',  bonus: 20 } }],
  ['steelShield',{ id: 'steelShield',name: '钢盾',   effect: { type: 'shield', bonus: 20 } }],
]);

// ============================================================
// 商店数据
// ============================================================

export const SHOPS: Map<string, ShopDef> = new Map([
  ['shop1', {
    id: 'shop1',
    items: [
      { label: '购买攻击力+3', effect: 'attack',  amount: 3,  cost: 30, repeatable: true },
      { label: '购买防御力+3', effect: 'defense', amount: 3,  cost: 30, repeatable: true },
      { label: '购买HP+100',   effect: 'hp',      amount: 100,cost: 10, repeatable: true },
    ]
  }],
]);

// ============================================================
// 地图辅助函数
// ============================================================

const E: CellContent = { kind: 'empty' };
const W: CellContent = { kind: 'wall' };
function M(id: string): CellContent { return { kind: 'monster', monsterId: id }; }
function I(id: string): CellContent { return { kind: 'item', itemId: id }; }
function YD(): CellContent { return { kind: 'door', color: 'yellow' }; }
function BD(): CellContent { return { kind: 'door', color: 'blue' }; }
function UP(f: number): CellContent { return { kind: 'stairsUp', toFloor: f }; }
function DN(f: number): CellContent { return { kind: 'stairsDown', toFloor: f }; }
function SH(id: string): CellContent { return { kind: 'shop', shopId: id }; }

// ============================================================
// 示例地图：3层演示场景
//
// 设计目标：说明以下决策点
//   F1：先打怪拿钥匙，再拿剑，还是直接上楼？
//   F2：左路（打更多怪，收集大血瓶）vs 右路（花蓝钥匙，收攻击宝石）
//   F3：Boss层（骷髅队长 HP=100 ATK=65 DEF=15）
//
// 初始属性：HP=1000, ATK=10, DEF=10
// 区域1：宝石+1属性，血瓶+50血；区域2：宝石+2属性，血瓶+100血
//
// 铁剑（+10 ATK）在F1，打败骷髅人可以得黄钥匙
// Boss需要 ATK>15，玩家最终应能达到 ATK≥22+
// ============================================================

export const SAMPLE_FLOORS: Map<number, Floor> = new Map([

  // ===== 第1层（区域1）=====
  //
  // 布局说明（11×11）：
  //   顶部：楼梯上行
  //   中上：铁剑（重要！让玩家能打Boss）
  //   中：骷髅人×1（掉黄钥匙，但需攻击力够）
  //   左下：两只绿史莱姆
  //   右：防御宝石
  //   底部中：入口
  //
  [1, {
    id: 1, area: 1, width: 11, height: 11,
    startPos: { row: 10, col: 5 },
    cells: [
      /* row0 */ [W, W,                W,              W,           W,          UP(2),      W,          W,               W,           W,          W],
      /* row1 */ [W, E,                E,               E,           E,          E,          E,          E,               E,           E,          W],
      /* row2 */ [W, I('ironSword'),   E,               E,           E,          I('hp'),    E,          E,               E,           E,          W],
      /* row3 */ [W, E,                W,               W,           YD(),       W,          W,           E,              E,           E,          W],
      /* row4 */ [W, E,                E,               E,           E,          E,          E,           E,              I('defGem'), E,          W],
      /* row5 */ [W, E,                W,               W,           E,          E,          W,           W,              E,           E,          W],
      /* row6 */ [W, E,                E,               E,           E,          I('hp'),    E,           E,              E,           E,          W],
      /* row7 */ [W, E,                E,               E,           E,          E,          E,           E,              E,           E,          W],
      /* row8 */ [W, M('monster01'),   E,               E,           E,          E,          E,           M('monster01'), E,           I('defGem'),W],
      /* row9 */ [W, E,                E,               E,           E,          I('yellowKey'), E,       E,              E,           E,          W],
      /* row10*/ [W, W,                W,               W,           W,          E,          W,           W,              W,           W,          W],
    ]
  }],

  // ===== 第2层（区域1）=====
  //
  // 布局说明：
  //   左路：3只骷髅人（较难，共耗约150HP），但有大血瓶+攻击宝石
  //   右路：需蓝钥匙（蓝钥匙在本层左侧），攻击宝石+铁盾
  //   中：商店（花金币买属性）
  //   蓝钥匙在左路怪物区域后——只有先打左路怪才能拿蓝钥匙开右路
  //
  // 注意：startPos 设为楼梯旁的空格（row9），让BFS能找到楼梯格本身
  [2, {
    id: 2, area: 1, width: 11, height: 11,
    startPos: { row: 9, col: 5 },
    cells: [
      /* row0 */ [W, W,                 W,               W,            W,         UP(3),        W,          W,               W,           W,          W],
      /* row1 */ [W, E,                 E,               E,            E,          E,            E,          E,               E,           E,          W],
      /* row2 */ [W, M('monster05'),    E,               E,            E,          E,            E,          E,               I('attackGem'),E,         W],
      /* row3 */ [W, E,                 W,               W,            E,          E,            E,          W,               BD(),        W,          W],
      /* row4 */ [W, I('hpLarge'),      W,               M('monster05'),E,         E,            E,          I('attackGem'),  E,           E,          W],
      /* row5 */ [W, E,                 W,               W,            W,          W,            W,          W,               E,           E,          W],
      /* row6 */ [W, E,                 E,               M('monster05'),E,         E,            E,          E,               I('ironShield'),E,        W],
      /* row7 */ [W, E,                 E,               E,            E,          E,            E,          E,               E,           E,          W],
      /* row8 */ [W, I('blueKey'),      E,               E,            SH('shop1'),E,            E,          E,               E,           E,          W],
      /* row9 */ [W, E,                 E,               E,            E,          E,            E,          E,               E,           E,          W],
      /* row10*/ [W, W,                 W,               W,            W,          DN(1),        W,          W,               W,           W,          W],
    ]
  }],

  // ===== 第3层（区域2）=====
  //
  // Boss层：骷髅队长（HP=100 ATK=65 DEF=15）
  //   需要 ATK>15 才能打Boss（铁剑即可满足）
  //   区域2宝石/血瓶效果翻倍
  //   有两只兽人可选打（高伤但掉金币）
  //
  [3, {
    id: 3, area: 2, width: 11, height: 11,
    startPos: { row: 9, col: 5 },
    cells: [
      /* row0 */ [W, W,                W,              W,           W,           W,          W,            W,              W,           W,          W],
      /* row1 */ [W, E,                E,              E,           M('monster08'),E,         E,            E,              E,           E,          W],
      /* row2 */ [W, E,                I('defGem'),    E,           E,           E,          E,            I('attackGem'), E,           E,          W],
      /* row3 */ [W, E,                W,              W,           E,           E,          W,            W,              E,           E,          W],
      /* row4 */ [W, I('hpLarge'),     W,              E,           W,           E,          W,            E,              W,           E,          W],
      /* row5 */ [W, E,                E,              E,           E,           E,          E,            E,              E,           E,          W],
      /* row6 */ [W, M('monster12'),   E,              E,           E,           E,          E,            E,              M('monster12'),E,         W],
      /* row7 */ [W, E,                E,              E,           E,           I('hp'),    E,            E,              E,           E,          W],
      /* row8 */ [W, E,                E,              E,           I('defGem'), E,          I('attackGem'),E,             E,           E,          W],
      /* row9 */ [W, E,                E,              E,           E,           E,          E,            E,              E,           E,          W],
      /* row10*/ [W, W,                W,              W,           W,           DN(2),      W,            W,              W,           W,          W],
    ]
  }],
]);

// ============================================================
// 导出完整游戏数据
// ============================================================

export const SAMPLE_GAME: GameData = {
  monsters: MONSTERS,
  items: ITEMS,
  floors: SAMPLE_FLOORS,
  shops: SHOPS,
  initialPlayer: {
    hp: 1000,
    maxHp: 999999,
    attack: 10,
    defense: 10,
    gold: 0,
    yellowKeys: 0,
    blueKeys: 0,
    redKeys: 0,
  },
  startFloor: 1,
  startPos: { row: 10, col: 5 },
  // Boss：骷髅队长（DEF=15，玩家拿到铁剑后ATK=20，可以击败）
  bossLocation: { floorId: 3, row: 1, col: 4 },
};
