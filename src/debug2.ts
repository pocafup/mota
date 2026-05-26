import { SAMPLE_GAME } from './data';
import { getReachable, applyAction, calcDamage, cellKey } from './engine';
import { GameState, PlayerState } from './types';

const data = SAMPLE_GAME;
const bossLoc = data.bossLocation;
const bossFloor = data.floors.get(bossLoc.floorId)!;
const bossCell  = bossFloor.cells[bossLoc.row][bossLoc.col];
const boss = bossCell.kind === 'monster' ? data.monsters.get(bossCell.monsterId)! : null;

console.log('Boss:', boss);
console.log('BossLoc:', bossLoc);

// 模拟"最优"手动路线：
// 1. 拿铁剑 (F1,2,1)
// 2. 走到F2→F3，收集所有物品
// 3. 打Boss

const initPlayer: PlayerState = {
  ...data.initialPlayer,
  floorId: 1, row: 10, col: 5,
};
let state: GameState = {
  player: initPlayer,
  consumed: new Set(),
  consumedHash: 0,
  shopBought: new Set(),
};

function step(desc: string, targetFloor: number, targetRow: number, targetCol: number) {
  const result = applyAction(state, { floorId: targetFloor, row: targetRow, col: targetCol }, data);
  if (!result) {
    console.log(`❌ ${desc}: applyAction returned null`);
    return false;
  }
  state = result.newState;
  const p = state.player;
  console.log(`✅ ${desc} → HP:${p.hp} ATK:${p.attack} DEF:${p.defense} Gold:${p.gold} 黄:${p.yellowKeys} 蓝:${p.blueKeys}`);
  return true;
}

console.log('\n=== 手动路线模拟 ===');

// F1步骤
step('F1 拾取铁剑',    1, 2, 1);
step('F1 拾取黄钥匙', 1, 9, 5);
step('F1 拾取红血瓶', 1, 2, 5);   // hp at (2,5)
step('F1 拾取红血瓶', 1, 6, 5);   // hp at (6,5)
step('F1 拾取防御宝石', 1, 8, 9); // defGem at (8,9)
step('F1 拾取防御宝石', 1, 4, 8); // defGem at (4,8)

// 检查F1楼梯是否可达
const reachable1 = getReachable(state, data);
console.log('\nF1可达格子:', reachable1.map(p => {
  const f = data.floors.get(p.floorId)!;
  const c = f.cells[p.row][p.col];
  return `(${p.floorId},${p.row},${p.col})=${c.kind}`;
}).join(', '));

// 使用黄门 - wait, do we need to open the yellow door?
// Let me check: the yellowDoor at (3,4) separates the map
// Actually looking at floor 1 layout, rows 0-2 should be accessible via right side

step('F1 使用楼梯上行', 1, 0, 5);  // stairsUp at (0,5)

// F2步骤
console.log('\n--- 进入F2 ---');
const reachable2 = getReachable(state, data);
console.log('F2可达格子:', reachable2.map(p => {
  const f = data.floors.get(p.floorId)!;
  const c = f.cells[p.row][p.col];
  return `(${p.floorId},${p.row},${p.col})=${c.kind}`;
}).join(', '));

step('F2 拾取蓝血瓶', 2, 4, 1);    // hpLarge at (4,1)
step('F2 拾取蓝钥匙', 2, 8, 1);    // blueKey at (8,1)
step('F2 拾取攻击宝石1', 2, 4, 7); // attackGem at (4,7) - wait let me check
step('F2 使用楼梯上行', 2, 0, 5);  // stairsUp at (0,5)

// F3步骤
console.log('\n--- 进入F3 ---');
const reachable3 = getReachable(state, data);
console.log('F3可达格子:', reachable3.map(p => {
  const f = data.floors.get(p.floorId)!;
  const c = f.cells[p.row][p.col];
  return `(${p.floorId},${p.row},${p.col})=${c.kind}`;
}).join(', '));

// Check boss
const p = state.player;
console.log(`\n玩家状态: HP:${p.hp} ATK:${p.attack} DEF:${p.defense}`);
if (boss) {
  const dmg = calcDamage(p, boss);
  console.log(`Boss战伤害: ${dmg} (如果 >HP 则必死)`);
  console.log(`${dmg < p.hp ? '✅ 能存活' : '❌ 会死亡'}`);
}

step('F3 打Boss', 3, 1, 4);
console.log('\n=== 最终状态 ===');
const fp = state.player;
console.log(`HP:${fp.hp} ATK:${fp.attack} DEF:${fp.defense}`);
console.log(state.consumed.has(cellKey(bossLoc.floorId, bossLoc.row, bossLoc.col)) ? '✅ Boss已击败' : '❌ Boss未击败');
