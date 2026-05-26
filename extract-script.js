/**
 * h5mota 游戏数据提取脚本（mota-js 引擎通用版）
 * ============================================================
 * 使用方法：
 *   1. 打开任意 h5mota.com 游戏，等待完全加载（出现游戏画面）
 *   2. 按 F12 → Console（控制台）
 *   3. 粘贴以下代码并按 Enter 运行
 *   4. 复制控制台输出的 JSON，保存为 game.json
 *   5. 运行：FILE=game.json npx ts-node src/index.ts
 *
 * 支持：mota-js 引擎（h5mota.com 主流框架）
 * ============================================================
 */

(function extractMotaGame() {
  const core = window.core;
  if (!core) {
    console.error('未找到 core 对象。请确认已打开 h5mota 游戏并等待加载完成。');
    return;
  }

  // ── 怪物数据 ──
  const enemyDefs = core.material?.enemys || core.enemys || core.status?.enemys || {};
  const monsters = Object.entries(enemyDefs)
    .filter(([, e]) => e && (e.hp > 0 || e.atk > 0))
    .map(([id, e]) => {
      const specMap = { 1: 'boss', 2: 'magic', 3: 'poison', 4: 'hpDouble',
                        5: 'atkDouble', 6: 'vampire', 11: 'firstStrike', 21: 'noHp' };
      const special = (e.special || []).map(s => specMap[s] || String(s));
      return {
        id,
        name:    e.name || id,
        hp:      e.hp   || 0,
        attack:  e.atk  || e.attack  || 0,
        defense: e.def  || e.defense || 0,
        gold:    e.money || e.gold   || 0,
        isBoss:  special.includes('boss'),
        special: special.filter(s => s !== 'boss'),
      };
    });

  // ── 物品数据 ──
  const itemDefs = core.material?.items || core.items || core.status?.items || {};
  const items = [];
  for (const [id, item] of Object.entries(itemDefs)) {
    if (!item || typeof item !== 'object') continue;
    const ef = detectItemEffect(id, item);
    if (ef) items.push({ id, name: item.name || id, effect: ef });
  }

  function detectItemEffect(id, item) {
    const v = item.value || 0;
    const cls = item.cls || '';
    // 装备
    if (cls === 'equips' || /sword|blade|dagger|knife/i.test(id))
      return { type: 'sword',  bonus: v || 10 };
    if (/shield|armor|mail/i.test(id))
      return { type: 'shield', bonus: v || 10 };
    // 钥匙
    if (/yellow.*key|ykey|key.*yellow/i.test(id)) return { type: 'yellowKey' };
    if (/blue.*key|bkey|key.*blue/i.test(id))     return { type: 'blueKey' };
    if (/red.*key|rkey|key.*red/i.test(id))       return { type: 'redKey' };
    if (/green.*key|gkey/i.test(id))              return { type: 'yellowKey' };
    // 血瓶（大）
    if (/big.*potion|hpLarge|blue.*pot|potion.*blue|bigHp/i.test(id))
      return { type: 'hpLarge', base: v || 200 };
    // 血瓶
    if (/potion|hp|life|blood|heal/i.test(id))
      return { type: 'hp', base: v || 50 };
    // 攻击宝石
    if (/atk.*gem|gem.*atk|attack.*gem|red.*gem|gem.*red|atkstone/i.test(id))
      return { type: 'attack', base: v || 1 };
    // 防御宝石
    if (/def.*gem|gem.*def|defense.*gem|blue.*gem|gem.*blue|defstone/i.test(id))
      return { type: 'defense', base: v || 1 };
    // 通用宝石（fallback：看value类型）
    if (/gem|stone|crystal/i.test(id)) return { type: 'attack', base: v || 1 };
    return null;
  }

  // ── 商店数据（从 core.shops 或 events 中提取） ──
  const shops = extractShops(core);

  function extractShops(core) {
    const result = [];
    // 部分游戏在 core.shops 里存放商店
    const rawShops = core.shops || core.material?.shops || {};
    for (const [id, s] of Object.entries(rawShops)) {
      if (!s || !s.items) continue;
      result.push({
        id,
        items: (s.items || []).map(si => ({
          label:      si.text || si.label || '购买',
          effect:     mapShopEffect(si.id || ''),
          amount:     si.value || si.amount || 1,
          cost:       si.need  || si.cost   || 10,
          repeatable: si.repeat !== false,
        })).filter(si => si.effect),
      });
    }
    return result;
  }

  function mapShopEffect(id) {
    if (/atk|attack/i.test(id)) return 'attack';
    if (/def|defense/i.test(id)) return 'defense';
    if (/hp|life|blood/i.test(id)) return 'hp';
    if (/yellow.*key|ykey/i.test(id)) return 'yellowKey';
    if (/blue.*key|bkey/i.test(id))   return 'blueKey';
    if (/red.*key|rkey/i.test(id))    return 'redKey';
    return null;
  }

  // ── 地图数据 ──
  const floorIds = core.floorIds || Object.keys(core.maps || core.status?.maps || {});

  // 玩家起始楼层（通常是第一个楼层）
  const firstFid = floorIds[0];
  const heroInfo = core.status?.hero || core.firstData?.hero || {};
  const initialHero = core.maps?.[firstFid] || {};
  let startFloor = 1;
  let startPos   = { row: 10, col: 6 };   // fallback

  if (heroInfo.floorId !== undefined) {
    startFloor = floorIds.indexOf(heroInfo.floorId) + 1;
    startPos   = { row: heroInfo.py || heroInfo.y || 10, col: heroInfo.px || heroInfo.x || 6 };
  } else if (initialHero.hero) {
    const h = initialHero.hero;
    startPos = { row: h.y || 10, col: h.x || 6 };
  }

  let bossLocation = null;
  const floors = [];

  floorIds.forEach((fid, idx) => {
    const floorDef = core.maps?.[fid] || core.status?.maps?.[fid];
    if (!floorDef) return;

    const w    = floorDef.width  || 13;
    const h    = floorDef.height || 13;
    // 区域：默认每10层一个区域，从1开始
    const area = floorDef.area != null ? floorDef.area : Math.floor(idx / 10) + 1;
    const floorNum = idx + 1;  // 1-indexed floor number

    // 初始化空格子网格
    const cells = Array.from({ length: h }, () => Array(w).fill(null));

    // 记录楼梯位置，用于确定入口
    let stairDownPos = null;

    // 用 blocks（pre-parsed block array）解析地图 ——
    // blocks 格式：[{x, y, id, event: {cls, ...}}]
    const blocks = floorDef.blocks || floorDef.map_blocks || [];

    for (const blk of blocks) {
      const r = blk.y;
      const c = blk.x;
      if (r < 0 || r >= h || c < 0 || c >= w) continue;

      const id  = blk.id || '';
      const cls = blk.event?.cls || blk.cls || guessClass(id);

      cells[r][c] = classifyBlock(id, cls, floorNum, floorIds);

      if (cells[r][c]?.startsWith('stairsDown')) stairDownPos = { row: r, col: c };

      // Boss 检测
      if (cls === 'enemys') {
        const m = enemyDefs[id];
        if (m && (m.special?.includes(1) || /boss|dragon|lord|king|final|zhumo/i.test(id))) {
          bossLocation = { floorId: floorNum, row: r, col: c };
        }
      }
    }

    // 如果 blocks 为空，尝试从 map 数组解析（数字格式）
    if (blocks.length === 0 && floorDef.map) {
      parseNumericMap(floorDef.map, w, h, cells, floorNum, floorIds, core);
    }

    // startPos：本层的"入口"（从下层楼梯上来的落点）
    // 通常是下行楼梯旁边的空格
    const thisStartPos = stairDownPos
      ? findAdjacentEmpty(cells, stairDownPos, h, w)
      : { row: h - 2, col: Math.floor(w / 2) };

    floors.push({
      id:   floorNum,
      area,
      width:  w,
      height: h,
      startPos: thisStartPos,
      cells,
    });
  });

  // 找Boss（若未检测到，取最后一层中间怪）
  if (!bossLocation && floors.length > 0) {
    const last = floors[floors.length - 1];
    outer:
    for (let r = 0; r < last.height; r++) {
      for (let c = 0; c < last.width; c++) {
        if (last.cells[r][c]?.startsWith('monster:')) {
          bossLocation = { floorId: last.id, row: r, col: c };
          break outer;
        }
      }
    }
    bossLocation = bossLocation || { floorId: floors.length, row: 1, col: 6 };
  }

  function guessClass(id) {
    if (enemyDefs[id]) return 'enemys';
    if (itemDefs[id])  return 'items';
    if (/stair|stairs/i.test(id)) return 'terrains';
    if (/door/i.test(id))         return 'terrains';
    if (/wall/i.test(id))         return 'terrains';
    return 'terrains';
  }

  function classifyBlock(id, cls, floorNum, floorIds) {
    if (cls === 'enemys')  return `monster:${id}`;
    if (cls === 'items')   return `item:${id}`;
    if (cls === 'npcs')    return null;  // NPC — 暂不处理

    // terrain
    if (/^wall$/i.test(id) || cls === 'autotile')  return 'wall';
    if (/stair.*up|up.*stair|stairUp/i.test(id))   return `stairsUp:${floorNum + 1}`;
    if (/stair.*down|down.*stair|stairDown/i.test(id)) return `stairsDown:${floorNum - 1}`;
    if (/yellowDoor|yellow.*door|door.*yellow/i.test(id)) return 'door:yellow';
    if (/blueDoor|blue.*door|door.*blue/i.test(id))       return 'door:blue';
    if (/redDoor|red.*door|door.*red/i.test(id))          return 'door:red';

    return null;  // 未知 terrain → 视为空地
  }

  function findAdjacentEmpty(cells, pos, h, w) {
    const dirs = [{row:-1,col:0},{row:1,col:0},{row:0,col:-1},{row:0,col:1}];
    for (const d of dirs) {
      const nr = pos.row + d.row, nc = pos.col + d.col;
      if (nr >= 0 && nr < h && nc >= 0 && nc < w && cells[nr][nc] === null) {
        return { row: nr, col: nc };
      }
    }
    return { row: Math.max(0, pos.row - 1), col: pos.col };
  }

  function parseNumericMap(map, w, h, cells, floorNum, floorIds, core) {
    // 数字tile映射（fallback for old-style maps）
    const numericIds = core.material?.icons?.terrains || {};
    for (let r = 0; r < h; r++) {
      for (let c = 0; c < w; c++) {
        const tileId = Array.isArray(map[r]) ? map[r][c] : map[r * w + c];
        if (!tileId) continue;
        // 基本数字约定
        if (tileId === 1 || tileId === 2) { cells[r][c] = 'wall'; continue; }
        // 尝试从 core.getBlock 获取
        if (core.getBlock) {
          try {
            const blk = core.getBlock(c, r, floorIds[floorNum - 1]);
            if (blk) {
              const cls = blk.event?.cls || guessClass(blk.id);
              cells[r][c] = classifyBlock(blk.id, cls, floorNum, floorIds);
            }
          } catch(e) {}
        }
      }
    }
  }

  // ── 初始属性 ──
  const hero = heroInfo;
  const initialPlayer = {
    hp:      hero.hp     || hero.life   || 1000,
    attack:  hero.atk    || hero.attack || 10,
    defense: hero.def    || hero.defense|| 10,
    gold:    hero.money  || hero.gold   || 0,
    yellowKeys: hero.keys?.yellow || hero.yellowKey  || 0,
    blueKeys:   hero.keys?.blue   || hero.blueKey    || 0,
    redKeys:    hero.keys?.red    || hero.redKey      || 0,
  };

  // ── 组装结果 ──
  const result = {
    meta: {
      name:    document.title || 'h5mota游戏',
      source:  location.href,
      version: core.version || '1.0',
    },
    initialPlayer,
    startFloor,
    startPos,
    bossLocation: bossLocation || { floorId: floors.length, row: 1, col: 6 },
    monsters,
    items,
    shops,
    floors,
  };

  // 输出统计
  const monsterCount = floors.reduce((s, f) => s + f.cells.flat().filter(c => c?.startsWith('monster:')).length, 0);
  const itemCount    = floors.reduce((s, f) => s + f.cells.flat().filter(c => c?.startsWith('item:')).length, 0);
  console.log(`✅ 提取完成！楼层：${floors.length}，怪物种类：${monsters.length}（共${monsterCount}只），物品：${itemCount}个`);
  console.log(`Boss：${JSON.stringify(bossLocation)}`);
  console.log('=== 复制以下JSON保存为 game.json ===');
  console.log(JSON.stringify(result, null, 2));
  return result;
})();
