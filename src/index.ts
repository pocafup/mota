import * as fs from 'fs';
import * as path from 'path';
import { SAMPLE_GAME } from './data';
import { solve } from './solver';
import { printRouteReport } from './renderer';
import { loadFromUniversal, UGameFormat } from './loader/format';
import { GameData } from './types';
import { scrapeGame } from './scraper';

// ============================================================
// 配置
// ============================================================

const TIME_LIMIT_MS = parseInt(process.env.TIME_LIMIT ?? '300000');  // 默认5分钟
const SHOW_MAPS     = process.env.NO_MAPS !== '1';                    // 默认显示地图

// ============================================================
// 加载游戏数据
// 优先从 --url= 自动抓取；其次 --file= 或 FILE= 加载JSON；否则使用内置示例
// 用法：
//   npx ts-node src/index.ts --url=https://h5mota.com/games/51/
//   FILE=game.json npx ts-node src/index.ts
//   npx ts-node src/index.ts --file=game.json
// ============================================================

async function loadGame(): Promise<GameData> {
  // 从命令行参数 --url=xxx 读取（自动抓取模式）
  const urlArg = process.argv.find(a => a.startsWith('--url='));
  const url = urlArg ? urlArg.slice('--url='.length) : process.env.URL;
  if (url) {
    const uFormat = await scrapeGame(url);
    console.log(`✅ 已加载游戏：${uFormat.meta?.name ?? url}`);
    return loadFromUniversal(uFormat);
  }

  // 从命令行参数 --file=xxx 读取
  const fileArg = process.argv.find(a => a.startsWith('--file='));
  const filePath = fileArg
    ? fileArg.slice('--file='.length)
    : process.env.FILE;

  if (!filePath) return SAMPLE_GAME;

  const resolved = path.resolve(filePath);
  if (!fs.existsSync(resolved)) {
    console.error(`❌ 找不到文件：${resolved}`);
    process.exit(1);
  }

  try {
    const raw = fs.readFileSync(resolved, 'utf-8');
    const json: UGameFormat = JSON.parse(raw);
    console.log(`✅ 已加载外部游戏：${json.meta?.name ?? filePath}`);
    return loadFromUniversal(json);
  } catch (e: any) {
    console.error(`❌ 解析失败：${e.message}`);
    process.exit(1);
  }
}

async function main() {
  const game = await loadGame();

  // ============================================================
  // 显示游戏信息
  // ============================================================

  const bossLoc  = game.bossLocation;
  const bossFloor = game.floors.get(bossLoc.floorId)!;
  const bossCell  = bossFloor.cells[bossLoc.row][bossLoc.col];
  const bossName  = bossCell.kind === 'monster'
    ? (game.monsters.get(bossCell.monsterId)?.name ?? '未知Boss')
    : '未知Boss';
  const bossDef   = bossCell.kind === 'monster'
    ? (game.monsters.get(bossCell.monsterId)?.defense ?? 0) : 0;

  console.log('\n╔══════════════════════════════╗');
  console.log('║     魔塔AI求解器 v2.0        ║');
  console.log('╚══════════════════════════════╝\n');
  console.log(`游戏楼层数：${game.floors.size}`);
  console.log(`目标 Boss：${bossName}（F${bossLoc.floorId}，DEF=${bossDef}）`);
  console.log(`初始属性：HP=${game.initialPlayer.hp} ATK=${game.initialPlayer.attack} DEF=${game.initialPlayer.defense}`);
  console.log(`时间限制：${TIME_LIMIT_MS / 1000}s\n`);

  // ============================================================
  // 运行求解器
  // ============================================================

  const startTime = Date.now();
  const result = solve(game, {
    timeLimitMs: TIME_LIMIT_MS,
    beamWidth: 2000,
    verbose: true,
  });
  const elapsed = Date.now() - startTime;

  console.log(`\n搜索耗时：${(elapsed / 1000).toFixed(2)}s`);

  if (!result.success) {
    console.log('\n❌ 未找到通关路线！');
    console.log('建议：');
    console.log('  1. 检查Boss是否可击败（ATK需高于Boss DEF）');
    console.log('  2. 检查地图钥匙数量是否足够');
    process.exit(1);
  }

  // ============================================================
  // 输出路线报告
  // ============================================================

  printRouteReport(result.actions, result.finalHp, game, { showMaps: SHOW_MAPS });
}

main().catch(err => {
  console.error('❌ 运行出错：', err);
  process.exit(1);
});
