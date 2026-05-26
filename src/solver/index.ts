import { GameState, GameData, PlayerState, Action, SolverResult } from '../types';
import {
  getReachable, applyAction,
  calcDamage, cellKey
} from '../engine';
import { upperBound, itemHpValue, buildGamePotential, GamePotential } from './heuristic';
import { greedyShopBuyForRender as greedyShopBuy } from '../engineExtra';

// ============================================================
// 状态键（用于去重剪枝）
// 使用排序后的 consumed 集合计算 djb2 哈希，避免 XOR 哈希的碰撞问题
// ============================================================

function stateKey(state: GameState): string {
  const p = state.player;
  // O(1): use the incrementally-maintained Zobrist XOR hash from consumedHash
  return `${p.floorId},${p.row},${p.col}|${p.yellowKeys},${p.blueKeys},${p.redKeys}|${p.attack},${p.defense}|${state.consumedHash >>> 0}`;
}

// ============================================================
// 节点优先级评分
// ============================================================

interface SearchNode {
  state: GameState;
  parent: SearchNode | null;
  action: Action | null;
}

function reconstructPath(node: SearchNode): Action[] {
  const actions: Action[] = [];
  let cur: SearchNode | null = node;
  while (cur && cur.action !== null) {
    actions.push(cur.action);
    cur = cur.parent;
  }
  actions.reverse();
  return actions;
}

function scorePriority(pos: { floorId: number; row: number; col: number },
  state: GameState, data: GameData): number {
  const floor = data.floors.get(pos.floorId)!;
  const cell = floor.cells[pos.row][pos.col];
  const bl = data.bossLocation;
  switch (cell.kind) {
    case 'item': {
      const ef = data.items.get(cell.itemId)?.effect;
      return ef ? itemHpValue(ef, floor.area, state.player, data) : 0;
    }
    case 'monster': {
      const m = data.monsters.get(cell.monsterId);
      if (!m) return 0;
      const isBoss = m.isBoss ||
        (pos.floorId === bl.floorId && pos.row === bl.row && pos.col === bl.col);
      if (isBoss) return 1e9;
      return -calcDamage(state.player, m);
    }
    case 'stairsUp':   return 10;
    case 'stairsDown': return 5;
    case 'door':       return 8;
    case 'shop':       return 3;
    default:           return 0;
  }
}

// ============================================================
// 主求解器：束搜索（Beam Search）
//
// 关键修复：
//   1. visited 只在束成员确定后更新，避免被淘汰候选污染 visited
//   2. 使用排序哈希（非 XOR）减少哈希碰撞
// ============================================================

export interface SolverOptions {
  timeLimitMs?: number;
  beamWidth?: number;
  maxNodes?: number;
  verbose?: boolean;
}

export function solve(data: GameData, opts: SolverOptions = {}): SolverResult {
  const {
    timeLimitMs = 300_000,
    beamWidth = 2000,
    maxNodes = 10_000_000,
    verbose = false,
  } = opts;

  const startTime = Date.now();
  const deadline = startTime + timeLimitMs;
  const pot: GamePotential = buildGamePotential(data);

  const initPlayer: PlayerState = {
    ...data.initialPlayer,
    floorId: data.startFloor,
    row: data.startPos.row,
    col: data.startPos.col,
  };
  const initState: GameState = {
    player: initPlayer,
    consumed: new Set(),
    consumedHash: 0,
    shopBought: new Set(),
  };

  const bossKey = cellKey(data.bossLocation.floorId, data.bossLocation.row, data.bossLocation.col);
  const initNode: SearchNode = { state: initState, parent: null, action: null };
  let beam: SearchNode[] = [initNode];

  let bestHp = -Infinity;
  let bestNode: SearchNode | null = null;
  let nodeCount = 0;
  let iteration = 0;

  // visited 只记录已进入束的节点（被淘汰候选不更新 visited）
  const visited = new Map<string, number>();
  visited.set(stateKey(initState), initState.player.hp);

  if (verbose) console.log(`开始搜索（束搜索，束宽=${beamWidth}，时限=${timeLimitMs / 1000}s）...`);

  while (beam.length > 0 && nodeCount < maxNodes && Date.now() < deadline) {
    iteration++;
    const candidates: Array<{ node: SearchNode; score: number }> = [];

    for (const node of beam) {
      const { state } = node;
      nodeCount++;

      // === 胜利条件 ===
      if (state.consumed.has(bossKey)) {
        if (state.player.hp > bestHp) {
          bestHp = state.player.hp;
          bestNode = node;
          if (verbose) console.log(`  新最优：HP=${bestHp}（迭代${iteration}，节点${nodeCount}）`);
        }
        continue;
      }

      // === 剪枝：上界不优于当前最优 ===
      const ub = upperBound(state, data, pot);
      if (ub <= bestHp) continue;

      // === 展开：找所有可达行动 ===
      const reachable = getReachable(state, data);
      for (const pos of reachable) {
        const result = applyAction(state, pos, data);
        if (!result) continue;
        if (result.newState.player.hp <= 0) continue;

        let nextState = result.newState;

        // 若到达商店，立即做贪心购买
        const floor = data.floors.get(pos.floorId)!;
        const cell = floor.cells[pos.row][pos.col];
        if (cell.kind === 'shop') {
          nextState = greedyShopBuy(nextState, (cell as any).shopId, data);
        }

        const nextUb = upperBound(nextState, data, pot);
        if (nextUb <= bestHp) continue;

        // === 检查 visited（只读，不写——写操作推迟到束确定后）===
        const sk = stateKey(nextState);
        const prev = visited.get(sk);
        if (prev !== undefined && nextState.player.hp <= prev) continue;

        const localScore = scorePriority(pos, state, data);
        // devBonus: persistent reward for having collected ATK/DEF items.
        // Breaks UB invariance: paths that actually developed stats score higher.
        const ip = data.initialPlayer;
        const np = nextState.player;
        const devBonus = (np.attack - ip.attack) * 50 + (np.defense - ip.defense) * 30;
        candidates.push({
          node: { state: nextState, parent: node, action: result.action },
          score: nextUb + localScore * 0.5 + devBonus,
        });
      }
    }

    if (candidates.length === 0) break;

    // 跨父节点去重：同一 stateKey 只保留 HP 最高的候选（消除 2000 个相同父节点产生的冗余）
    const dedupMap = new Map<string, typeof candidates[0]>();
    for (const c of candidates) {
      const sk = stateKey(c.node.state);
      const existing = dedupMap.get(sk);
      if (!existing || c.node.state.player.hp > existing.node.state.player.hp) {
        dedupMap.set(sk, c);
      }
    }
    const unique = [...dedupMap.values()];

    // 按评分降序排列，保留前 beamWidth
    if (unique.length > beamWidth) {
      unique.sort((a, b) => b.score - a.score);
      unique.splice(beamWidth);
    }

    // 确定束成员后再更新 visited（避免被淘汰候选污染）
    beam = unique.map(c => {
      const sk = stateKey(c.node.state);
      const hp = c.node.state.player.hp;
      const prev = visited.get(sk);
      if (prev === undefined || hp > prev) visited.set(sk, hp);
      return c.node;
    });

    if (verbose && iteration % 10 === 0) {
      const elapsed = Date.now() - startTime;
      // Show floor distribution of beam members
      const floorCounts = new Map<number, number>();
      for (const n of beam) {
        const f = n.state.player.floorId;
        floorCounts.set(f, (floorCounts.get(f) ?? 0) + 1);
      }
      const topFloors = [...floorCounts.entries()].sort((a,b)=>b[0]-a[0]).slice(0,5)
        .map(([f,c])=>`F${f}×${c}`).join(' ');
      const maxFloor = Math.max(...floorCounts.keys());
      const maxFloorNodes = beam.filter(n => n.state.player.floorId === maxFloor);
      const maxHpNode = maxFloorNodes.reduce((a, b) => a.state.player.hp > b.state.player.hp ? a : b, maxFloorNodes[0]);
      const minHpNode = maxFloorNodes.reduce((a, b) => a.state.player.hp < b.state.player.hp ? a : b, maxFloorNodes[0]);
      const p = maxHpNode?.state.player;
      const pMin = minHpNode?.state.player;
      const yKeys = maxFloorNodes.map(n => n.state.player.yellowKeys);
      const yMin = Math.min(...yKeys), yMax = Math.max(...yKeys);
      const atkVals = maxFloorNodes.map(n => n.state.player.attack);
      const atkMin = Math.min(...atkVals), atkMax = Math.max(...atkVals);
      const keyInfo = p ? ` HP=[${pMin?.hp}-${p.hp}] ATK=[${atkMin}-${atkMax}] Y=[${yMin}-${yMax}] B=${p.blueKeys} R=${p.redKeys}` : '';
      console.log(`  迭代${iteration}：束宽=${beam.length}，节点=${nodeCount}，时间=${elapsed}ms`);
      console.log(`    最高楼F${maxFloor}${keyInfo} 分布：${topFloors}`);
    }
  }

  const elapsed = Date.now() - startTime;
  const timeoutHit = Date.now() >= deadline || nodeCount >= maxNodes;
  const nodeMsg = `节点数=${nodeCount}，迭代=${iteration}`;

  if (verbose) {
    console.log(`搜索结束：${elapsed}ms，${nodeMsg}${timeoutHit ? '（超时/达节点上限）' : ''}`);
  }

  if (bestHp === -Infinity) {
    return {
      success: false,
      finalHp: 0,
      actions: [],
      summary: `未找到通关路线（${nodeMsg}，耗时${elapsed}ms）`,
    };
  }

  const bestPath = reconstructPath(bestNode!);
  return {
    success: true,
    finalHp: bestHp,
    actions: bestPath,
    summary: buildSummary(bestPath, bestHp, elapsed, nodeCount, timeoutHit),
  };
}

// ============================================================
// 构建结果摘要
// ============================================================

function buildSummary(
  actions: Action[], finalHp: number,
  elapsedMs: number, nodes: number, timeout: boolean
): string {
  const lines: string[] = [
    '╔══════════════════════════════════╗',
    '║        最优路线搜索结果          ║',
    '╚══════════════════════════════════╝',
    `搜索耗时：${(elapsedMs / 1000).toFixed(1)}s${timeout ? '（达时间上限）' : ''}`,
    `访问节点：${nodes.toLocaleString()}`,
    `最终HP：  ${finalHp}`,
    `步骤数：  ${actions.length}`,
    '',
  ];
  return lines.join('\n');
}
