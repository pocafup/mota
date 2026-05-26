import { GameData, GameState, Floor, Action, CellContent, PlayerState } from './types';
import { applyAction, cellKey, cloneState } from './engine';
import { greedyShopBuyForRender } from './engineExtra';

// ============================================================
// 终端颜色码（用于彩色输出）
// ============================================================
const C = {
  reset:   '\x1b[0m',
  bold:    '\x1b[1m',
  red:     '\x1b[31m',
  green:   '\x1b[32m',
  yellow:  '\x1b[33m',
  blue:    '\x1b[34m',
  magenta: '\x1b[35m',
  cyan:    '\x1b[36m',
  white:   '\x1b[37m',
  bgRed:   '\x1b[41m',
  bgGreen: '\x1b[42m',
  bgBlue:  '\x1b[44m',
  gray:    '\x1b[90m',
};

// ============================================================
// 单元格符号
// ============================================================

function cellSymbol(cell: CellContent, data: GameData): string {
  switch (cell.kind) {
    case 'empty':       return '  ';
    case 'wall':        return '██';
    case 'stairsUp':    return '↑↑';
    case 'stairsDown':  return '↓↓';
    case 'door':
      if (cell.color === 'yellow') return `${C.yellow}▤▤${C.reset}`;
      if (cell.color === 'blue')   return `${C.blue}▤▤${C.reset}`;
      return `${C.red}▤▤${C.reset}`;
    case 'item': {
      const ef = data.items.get(cell.itemId)?.effect;
      if (!ef) return `${C.green}??${C.reset}`;
      if (ef.type === 'yellowKey') return `${C.yellow}⚷ ${C.reset}`;
      if (ef.type === 'blueKey')   return `${C.blue}⚷ ${C.reset}`;
      if (ef.type === 'redKey')    return `${C.red}⚷ ${C.reset}`;
      if (ef.type === 'hp' || ef.type === 'hpLarge') return `${C.red}♥ ${C.reset}`;
      if (ef.type === 'attack' || ef.type === 'sword')   return `${C.cyan}⚔ ${C.reset}`;
      if (ef.type === 'defense' || ef.type === 'shield') return `${C.blue}🛡${C.reset}`;
      return `${C.green}* ${C.reset}`;
    }
    case 'monster': {
      const m = data.monsters.get(cell.monsterId);
      if (!m) return `${C.red}?!${C.reset}`;
      if (m.isBoss) return `${C.bgRed}${C.white}B!${C.reset}`;
      return `${C.red}☠ ${C.reset}`;
    }
    case 'shop':  return `${C.green}$$ ${C.reset}`;
    case 'npc':   return `${C.magenta}@ ${C.reset}`;
    default:      return '??';
  }
}

// ============================================================
// 渲染单个楼层地图
// ============================================================

function renderFloor(
  floor: Floor,
  data: GameData,
  consumed: Set<string>,
  visited: Array<{ row: number; col: number }>,   // 本层被经过的格子（按顺序）
  playerPos?: { row: number; col: number },
): string {
  const visitSet = new Map<string, number>();
  visited.forEach((p, i) => visitSet.set(`${p.row},${p.col}`, i + 1));

  const lines: string[] = [];
  // 顶部边框
  lines.push('  ' + '─'.repeat(floor.width * 3));

  for (let r = 0; r < floor.height; r++) {
    const rowStr = [`${String(r).padStart(2, '0')}│`];
    for (let c = 0; c < floor.width; c++) {
      const key = cellKey(floor.id, r, c);
      const cell = floor.cells[r][c];
      const isPlayer = playerPos?.row === r && playerPos?.col === c;
      const stepNum = visitSet.get(`${r},${c}`);
      const isConsumed = consumed.has(key);

      if (isPlayer) {
        rowStr.push(`${C.bgGreen}${C.white}●${C.reset} `);
      } else if (stepNum !== undefined) {
        // 标注步骤编号（1-9 显示数字，10+ 显示 +）
        const mark = stepNum <= 9 ? String(stepNum) : '+';
        rowStr.push(`${C.green}${mark}${C.reset} `);
      } else if (isConsumed) {
        // 已消耗格子（显示淡化）
        rowStr.push(`${C.gray}··${C.reset}`);
      } else {
        rowStr.push(cellSymbol(cell, data));
      }
      rowStr.push(' ');
    }
    lines.push(rowStr.join('') + '│');
  }

  lines.push('  ' + '─'.repeat(floor.width * 3));
  return lines.join('\n');
}

// ============================================================
// 逐步执行动作，跟踪路线
// ============================================================

interface StepRecord {
  floorId: number;
  row: number;
  col: number;
  action: Action;
  playerAfter: PlayerState;
}

export function traceRoute(
  actions: Action[],
  data: GameData,
): StepRecord[] {
  const init: PlayerState = {
    ...data.initialPlayer,
    floorId: data.startFloor,
    row: data.startPos.row,
    col: data.startPos.col,
  };
  let state: GameState = {
    player: init,
    consumed: new Set(),
    consumedHash: 0,
    shopBought: new Set(),
  };

  const records: StepRecord[] = [];

  for (const action of actions) {
    const pos = { floorId: action.targetFloor, row: action.targetRow, col: action.targetCol };
    const result = applyAction(state, pos, data);
    if (!result) break;

    let nextState = result.newState;
    // 商店购买（贪心）
    const floor = data.floors.get(pos.floorId);
    if (floor) {
      const cell = floor.cells[pos.row][pos.col];
      if (cell.kind === 'shop') {
        nextState = greedyShopBuyForRender(nextState, (cell as any).shopId, data);
      }
    }

    records.push({
      floorId: action.targetFloor,
      row: action.targetRow,
      col: action.targetCol,
      action,
      playerAfter: { ...nextState.player },
    });

    state = nextState;
  }

  return records;
}

// ============================================================
// 打印完整路线报告
// ============================================================

export function printRouteReport(
  actions: Action[],
  finalHp: number,
  data: GameData,
  opts: { showMaps?: boolean } = {}
): void {
  const { showMaps = true } = opts;
  const steps = traceRoute(actions, data);

  console.log(`\n${'═'.repeat(55)}`);
  console.log(`  魔塔AI最优路线报告`);
  console.log(`${'═'.repeat(55)}`);

  // ── 按楼层分组显示步骤 ──
  const byFloor = new Map<number, StepRecord[]>();
  for (const s of steps) {
    const arr = byFloor.get(s.floorId) ?? [];
    arr.push(s);
    byFloor.set(s.floorId, arr);
  }

  // ── 步骤列表 ──
  console.log(`\n📋 步骤列表（共${actions.length}步）：`);
  console.log('   格式：[步号] 楼层F#  行动  →  HP|ATK|DEF|钥匙\n');

  let consumed = new Set<string>();
  let player: PlayerState = {
    ...data.initialPlayer,
    floorId: data.startFloor,
    row: data.startPos.row,
    col: data.startPos.col,
  };
  let state: GameState = { player: { ...player }, consumed: new Set(), consumedHash: 0, shopBought: new Set() };

  for (let i = 0; i < steps.length; i++) {
    const s = steps[i];
    const a = s.action;
    const p = s.playerAfter;

    const typeIcon = {
      fight:     `${C.red}⚔ 战斗${C.reset}`,
      pickup:    `${C.green}★ 拾取${C.reset}`,
      openDoor:  `${C.yellow}⚷ 开门${C.reset}`,
      useStairs: `${C.cyan}↕ 楼梯${C.reset}`,
      buyShop:   `${C.magenta}$ 商店${C.reset}`,
      move:      '→ 移动',
    }[a.type] ?? a.type;

    const keyStr = [
      p.yellowKeys > 0 ? `${C.yellow}黄×${p.yellowKeys}${C.reset}` : '',
      p.blueKeys   > 0 ? `${C.blue}蓝×${p.blueKeys}${C.reset}`   : '',
      p.redKeys    > 0 ? `${C.red}红×${p.redKeys}${C.reset}`     : '',
    ].filter(Boolean).join(' ') || '无';

    const stepPad = String(i + 1).padStart(3);
    // For stairs, show destination floor from description; otherwise show source floor
    const displayFloor = a.type === 'useStairs'
      ? `F${p.floorId}`   // player is now on the destination floor
      : `F${a.targetFloor}`;
    const floorPad = displayFloor.padEnd(3);
    console.log(
      `  ${stepPad}. [${floorPad}] ${typeIcon}  ${a.description.padEnd(30)}`
      + `  HP:${String(p.hp).padStart(5)}  ATK:${p.attack}  DEF:${p.defense}  钥匙:${keyStr}`
    );
  }

  // ── 最终结果 ──
  console.log(`\n${'─'.repeat(55)}`);
  console.log(`${C.bold}${C.green}  ✅ 通关完成！最终剩余HP：${finalHp}${C.reset}`);
  console.log(`${'─'.repeat(55)}`);

  // ── 楼层地图 ──
  if (showMaps) {
    console.log('\n🗺  楼层路线图（绿色数字=经过步骤，·=已消耗，██=墙）：\n');

    // 按楼层打印
    const allFloors = Array.from(data.floors.keys()).sort((a, b) => a - b);

    // 重新模拟一遍，构建每层的访问轨迹
    let simState: GameState = {
      player: { ...data.initialPlayer, floorId: data.startFloor, row: data.startPos.row, col: data.startPos.col },
      consumed: new Set(),
      consumedHash: 0,
      shopBought: new Set(),
    };

    // floorVisits[floorId] = 按步骤顺序访问的 {row, col}（去重，保留首次）
    const floorVisits = new Map<number, Array<{ row: number; col: number }>>();
    const floorConsumed = new Map<number, Set<string>>();

    for (const a of actions) {
      const pos = { floorId: a.targetFloor, row: a.targetRow, col: a.targetCol };
      const result = applyAction(simState, pos, data);
      if (!result) break;

      const visits = floorVisits.get(a.targetFloor) ?? [];
      visits.push({ row: a.targetRow, col: a.targetCol });
      floorVisits.set(a.targetFloor, visits);

      // 记录该楼层在此步骤后已消耗的格子
      floorConsumed.set(a.targetFloor, new Set(result.newState.consumed));

      let nextState = result.newState;
      const floor = data.floors.get(a.targetFloor);
      if (floor) {
        const cell = floor.cells[a.targetRow][a.targetCol];
        if (cell.kind === 'shop') {
          nextState = greedyShopBuyForRender(nextState, (cell as any).shopId, data);
        }
      }
      simState = nextState;
    }

    for (const fid of allFloors) {
      const floor = data.floors.get(fid)!;
      const visits = floorVisits.get(fid) ?? [];
      const consumed = floorConsumed.get(fid) ?? new Set<string>();

      console.log(`\n  ─── 第 ${fid} 层（区域${floor.area}）${'─'.repeat(30)}`);
      console.log(renderFloor(floor, data, consumed, visits));

      // 图例：列出此层的关键行动
      const floorSteps = steps.filter(s => s.action.targetFloor === fid);
      if (floorSteps.length > 0) {
        console.log(`  关键行动：`);
        floorSteps.slice(0, 8).forEach((s, i) => {
          console.log(`    ${i + 1}. ${s.action.description}`);
        });
        if (floorSteps.length > 8) {
          console.log(`    ...（共${floorSteps.length}步）`);
        }
      }
    }
  }

  // ── 如何读路线图 ──
  console.log(`\n${'═'.repeat(55)}`);
  console.log('  📖 路线图读法说明');
  console.log(`${'═'.repeat(55)}`);
  console.log(`
  地图图例：
    ██  = 墙（不可通过）
    ↑↑  = 上行楼梯
    ↓↓  = 下行楼梯
    ▤▤  = 门（${C.yellow}黄${C.reset}/${C.blue}蓝${C.reset}/${C.red}红${C.reset}色区分）
    ⚷   = 钥匙（颜色对应）
    ♥   = 血瓶
    ⚔   = 攻击道具
    🛡  = 防御道具
    ☠   = 普通怪物
    ${C.bgRed}${C.white}B!${C.reset}  = Boss
    $   = 商店
    ··  = 已消耗格（打过怪/拿过物品/开过门）

  步骤标记：
    绿色数字（1-9）= 第N步经过此格
    绿色 +         = 第10步及之后经过此格

  步骤列表字段：
    HP  = 执行该步后剩余血量
    ATK = 攻击力   DEF = 防御力
    钥匙 = 当前持有各色钥匙数量

  搜索策略：最优先搜索（Best-First）
    → 优先展开"预期最终HP最高"的路线分支
    → 时间限制到期后返回当前最优解
    → 非全局最优，但通常接近最优
`);
}
