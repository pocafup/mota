/**
 * 自动从 h5mota.com 游戏 URL 抓取游戏数据
 * 使用 Playwright 加载游戏，在浏览器中执行提取脚本，返回 UGameFormat
 *
 * 用法（在 index.ts 中通过 --url= 参数调用）：
 *   npx ts-node src/index.ts --url=https://h5mota.com/games/51/
 */

import { chromium } from 'playwright';
import { UGameFormat } from './loader/format';

export async function scrapeGame(url: string): Promise<UGameFormat> {
  console.log(`\n🌐 正在加载游戏：${url}`);
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage();
    page.on('console', msg => {
      if (msg.type() === 'error') console.error('  [游戏错误]', msg.text().slice(0, 100));
    });

    await page.goto(url, { waitUntil: 'domcontentloaded' });

    // 等待 core 对象和地图数据完全加载（最多30秒）
    await page.waitForFunction(() => {
      const c = (window as any).core;
      return c?.floorIds?.length > 0 && c?.material?.enemys && c?.floors;
    }, { timeout: 30000 });

    console.log('✅ 游戏数据已加载，开始提取...');

    const data = await page.evaluate(() => {
      const c = (window as any).core;

      // ── 工具函数 ──────────────────────────────────────────────
      const values = (c.data?.values || {}) as Record<string, number>;

      function findValueKey(expr: string): number {
        // 从 itemEffect 表达式里找 core.values.xxx 对应的数值
        const m = expr.match(/core\.values\.(\w+)/);
        if (!m) return 0;
        return values[m[1]] || 0;
      }

      function detectItemEffect(id: string, item: any): any {
        // 钥匙
        if (item.cls === 'tools') {
          if (/yellow/i.test(id)) return { type: 'yellowKey' };
          if (/blue/i.test(id))   return { type: 'blueKey' };
          if (/red/i.test(id))    return { type: 'redKey' };
          return null;
        }
        // 装备（sword/shield）—— 返回绝对加成，上层代码计算 delta
        if (item.equip?.value) {
          const ev = item.equip.value;
          if (ev.atk) return { type: 'sword',  bonus: ev.atk };
          if (ev.def) return { type: 'shield', bonus: ev.def };
        }
        const ef = item.itemEffect || '';
        const hasRatio = ef.includes('.ratio');
        // 血瓶
        if (/\.hp\s*\+=/.test(ef) && hasRatio) {
          const base = findValueKey(ef);
          if (!base) return null;
          return { type: base >= 200 ? 'hpLarge' : 'hp', base };
        }
        // 攻击宝石
        if (/\.atk\s*\+=/.test(ef) && hasRatio) {
          const base = findValueKey(ef);
          return base ? { type: 'attack', base } : null;
        }
        // 防御宝石
        if (/\.def\s*\+=/.test(ef) && hasRatio) {
          const base = findValueKey(ef);
          return base ? { type: 'defense', base } : null;
        }
        // 复合固定加成（如黄宝石：HP+N, ATK+N, DEF+N，无 ratio 倍数）
        if (!hasRatio && (/\.hp\s*\+=/.test(ef) || /\.atk\s*\+=/.test(ef) || /\.def\s*\+=/.test(ef))) {
          const hpM  = ef.match(/\.hp\s*\+=\s*(\d+)/);
          const atkM = ef.match(/\.atk\s*\+=\s*(\d+)/);
          const defM = ef.match(/\.def\s*\+=\s*(\d+)/);
          const hp  = hpM  ? parseInt(hpM[1])  : 0;
          const atk = atkM ? parseInt(atkM[1]) : 0;
          const def = defM ? parseInt(defM[1]) : 0;
          if (hp > 0 || atk > 0 || def > 0) return { type: 'compound', hp, attack: atk, defense: def };
        }
        return null;
      }

      function tileToCell(info: { id: string; cls: string }, floorNum: number): string | null {
        const { id, cls } = info;
        if (cls === 'animates') {
          if (/Wall/i.test(id) || id === 'wall') return 'wall';
          if (id === 'yellowDoor') return 'door:yellow';
          if (id === 'blueDoor')   return 'door:blue';
          if (id === 'redDoor')    return 'door:red';
          if (id === 'specialDoor' || id === 'steelDoor') return 'door:yellow';
          // star, lava, portal 等 = 可通行（忽略特殊效果）
          return null;
        }
        if (id === 'upFloor')   return `stairsUp:${floorNum + 1}`;
        if (id === 'downFloor') return `stairsDown:${floorNum - 1}`;
        if (cls === 'enemys') return `monster:${id}`;
        if (cls === 'items')  return `item:${id}`;
        if (cls === 'npcs') {
          // 用楼层号区分同类型的不同商店实例
          if (id === 'blueShop')  return `shop:blueShop_f${floorNum}`;
          if (id === 'trader')    return `shop:trader_f${floorNum}`;
          return null; // 其他NPC（剧情、一次性奖励）视为空地
        }
        return null;
      }

      function findAdjacentEmpty(
        cells: (string | null)[][], pos: { row: number; col: number },
        h: number, w: number
      ): { row: number; col: number } {
        const dirs = [{ dr: -1, dc: 0 }, { dr: 1, dc: 0 }, { dr: 0, dc: -1 }, { dr: 0, dc: 1 }];
        for (const { dr, dc } of dirs) {
          const nr = pos.row + dr, nc = pos.col + dc;
          if (nr >= 0 && nr < h && nc >= 0 && nc < w && cells[nr][nc] === null)
            return { row: nr, col: nc };
        }
        return { row: Math.max(0, pos.row - 1), col: pos.col };
      }

      // ── 全局 tileId → {id, cls} 映射 ────────────────────────
      const allTileIds = new Set<number>();
      for (const fid of c.floorIds) {
        const f = c.floors[fid];
        if (!f?.map) continue;
        for (const row of f.map as number[][])
          for (const t of row) if (t) allTileIds.add(t);
      }
      const tileMap: Record<number, { id: string; cls: string }> = {};
      for (const t of allTileIds) {
        try {
          const info = c.getBlockInfo(t);
          if (info) tileMap[t] = { id: info.id, cls: info.cls };
        } catch { }
      }

      // ── 预扫描 setEnemy 事件修改（boss 的真实属性可能在 setBlock 前被修改）─
      const enemyStatOverrides: Record<string, Record<string, number>> = {};
      for (const fid of c.floorIds) {
        const f = c.floors[fid];
        if (!f?.events) continue;
        for (const evList of Object.values(f.events) as any[][]) {
          if (!Array.isArray(evList)) continue;
          for (const ev of evList) {
            if (ev?.type === 'setEnemy' && ev.id && ev.name && ev.value !== undefined) {
              if (!enemyStatOverrides[ev.id]) enemyStatOverrides[ev.id] = {};
              enemyStatOverrides[ev.id][ev.name] = parseInt(ev.value) || 0;
            }
          }
        }
      }

      // ── 怪物 ─────────────────────────────────────────────────
      const enemyDefs = c.material?.enemys || {};
      // 将 setEnemy 修改应用到 enemyDefs 副本中
      const effectiveEnemyDefs: Record<string, any> = {};
      for (const [id, e] of Object.entries(enemyDefs) as [string, any][]) {
        const overrides = enemyStatOverrides[id];
        effectiveEnemyDefs[id] = overrides ? { ...e, ...overrides } : e;
      }

      const monsters = Object.entries(effectiveEnemyDefs)
        .filter(([, e]: [string, any]) => e && (e.hp > 0 || e.atk > 0))
        .map(([id, e]: [string, any]) => {
          const s = typeof e.special === 'number' ? e.special : 0;
          const special: string[] = [];
          if (s & 2) special.push('magic');
          if (s & 4) special.push('firstStrike');
          return {
            id, name: e.name || id,
            hp: e.hp || 0, attack: e.atk || 0, defense: e.def || 0,
            gold: e.money || 0,
            isBoss: !!(s & 1),
            special,
          };
        });

      // ── 物品（装备做 delta 处理）──────────────────────────────
      const itemDefs = c.material?.items || {};

      // 先收集所有装备的绝对加成，之后计算 delta
      const swordList: { id: string; bonus: number }[] = [];
      const shieldList: { id: string; bonus: number }[] = [];
      for (const [id, item] of Object.entries(itemDefs) as [string, any][]) {
        if (!item?.equip?.value) continue;
        const ev = item.equip.value;
        if (ev.atk) swordList.push({ id, bonus: ev.atk });
        if (ev.def) shieldList.push({ id, bonus: ev.def });
      }
      swordList.sort((a, b) => a.bonus - b.bonus);
      shieldList.sort((a, b) => a.bonus - b.bonus);

      // 初始装备等级（从玩家已装备等级开始计算 delta，低于此的装备捡了无效）
      const _heroForEquip = c.firstData?.hero || {};
      const _nowWeapon = _heroForEquip.flags?.nowWeapon;
      const _nowShield = _heroForEquip.flags?.nowShield;
      const _startWeaponAtk = _nowWeapon ? (itemDefs[_nowWeapon]?.equip?.value?.atk || 0) : 0;
      const _startShieldDef = _nowShield ? (itemDefs[_nowShield]?.equip?.value?.def || 0) : 0;

      // 计算装备 delta（从初始装备等级起步，低于初始的给 0 加成）
      const swordDelta: Record<string, number> = {};
      let prevSword = _startWeaponAtk;
      for (const { id, bonus } of swordList) {
        swordDelta[id] = Math.max(0, bonus - prevSword);
        if (bonus > prevSword) prevSword = bonus;
      }
      const shieldDelta: Record<string, number> = {};
      let prevShield = _startShieldDef;
      for (const { id, bonus } of shieldList) {
        shieldDelta[id] = Math.max(0, bonus - prevShield);
        if (bonus > prevShield) prevShield = bonus;
      }

      const items: any[] = [];
      for (const [id, item] of Object.entries(itemDefs) as [string, any][]) {
        if (!item) continue;
        let ef = detectItemEffect(id, item);
        if (!ef) continue;
        // 用 delta 替换装备的绝对加成
        if (ef.type === 'sword') ef = { type: 'sword', bonus: swordDelta[id] ?? ef.bonus };
        if (ef.type === 'shield') ef = { type: 'shield', bonus: shieldDelta[id] ?? ef.bonus };
        items.push({ id, name: item.name || id, effect: ef });
      }

      // ── 商店 ─────────────────────────────────────────────────────
      // 支持两类商店：
      //   1. blueShop（蓝祭坛）：重复购买ATK/DEF/HP，费用按 commonEvent['商店'] 递增
      //   2. trader（商人）：一次性购买钥匙，按 commonEvent['商人'] switch 分支
      const shops: any[] = [];
      const commonEvents: Record<string, any[]> = (c as any).events?.commonEvent || {};
      const shopCommonEvent = commonEvents['商店'];   // 蓝商店事件
      const traderCommonEvent = commonEvents['商人']; // 商人事件

      // 用 tileMap 找对应类型的 NPC，需在楼层循环后才能用
      // 先预计算 floorIds（后面楼层循环也用），这里提前声明
      const floorIds_: string[] = c.floorIds;

      // 解析 blueShop 的 ratio
      const blueShopRatioMap: Record<string, number> = {};
      for (let i = 0; i < floorIds_.length; i++) {
        const fid = floorIds_[i];
        const f = c.floors[fid];
        if (!f?.map) continue;
        const h_: number = f.height || 13, w_: number = f.width || 13;
        for (let r = 0; r < h_; r++) {
          for (let cc = 0; cc < w_; cc++) {
            const t = (f.map as number[][])[r]?.[cc];
            if (!t) continue;
            const inf = tileMap[t];
            if (!inf || inf.id !== 'blueShop') continue;
            const evKey = `${cc},${r}`;
            const evList = (f.events || {})[evKey];
            let ratio = 1;
            if (Array.isArray(evList)) {
              for (const ev of evList) {
                if (ev?.type === 'setValue' && ev.name === 'flag:ratio') {
                  ratio = parseInt(ev.value) || 1;
                  break;
                }
              }
            }
            blueShopRatioMap[`${fid},${r},${cc}`] = ratio;
          }
        }
      }

      // 生成蓝商店
      if (shopCommonEvent) {
        for (const [key, ratio] of Object.entries(blueShopRatioMap)) {
          const [fid, r, cc] = key.split(',');
          const floorIdx = floorIds_.indexOf(fid) + 1;
          const shopId = `blueShop_f${floorIdx}`;
          const items: any[] = [];
          // 生成 12 个 ATK 购买档位（共享全局 times1 计数，这里独立建模近似）
          for (let k = 0; k < 12; k++) {
            const cost = 20 + 10 * (k + 1) * k;
            items.push({ label: `攻击+${2 * ratio}`, effect: 'attack', amount: 2 * ratio, cost, repeatable: false });
          }
          // 8 个 DEF 购买档位
          for (let k = 0; k < 8; k++) {
            const cost = 20 + 10 * (k + 1) * k;
            items.push({ label: `防御+${2 * ratio}`, effect: 'defense', amount: 2 * ratio, cost, repeatable: false });
          }
          shops.push({ id: shopId, items });
        }
      }

      // 解析商人 switch cases（按 floorIdx-1 匹配）
      if (traderCommonEvent) {
        const switchCases: Record<string, { money: number; effects: any[] }> = {};
        for (const ev of traderCommonEvent) {
          if (ev?.type !== 'switch') continue;
          for (const caseItem of (ev.caseList || [])) {
            const caseNum: string = String(caseItem.case);
            let money = 0;
            const effects: any[] = [];
            for (const action of (caseItem.action || [])) {
              if (action?.type === 'setValue' && action.name === 'flag:money') {
                money = parseInt(action.value) || 0;
              }
              if (action?.type === 'setValue' && action.name === 'flag:text') {
                const txt: string = action.value || '';
                const numCn = (s: string) => {
                  const m = s.match(/(\d+)/);
                  return m ? parseInt(m[1]) : 1;
                };
                if (/兰钥匙/.test(txt)) effects.push({ effect: 'blueKey',   amount: numCn(txt.match(/(\d+)把兰钥匙/)?.[0] || '') || 1 });
                if (/黄钥匙/.test(txt)) effects.push({ effect: 'yellowKey', amount: numCn(txt.match(/(\d+)把黄钥匙/)?.[0] || '') || 1 });
                if (/红钥匙/.test(txt)) effects.push({ effect: 'redKey',    amount: numCn(txt.match(/(\d+)把红钥匙/)?.[0] || '') || 1 });
                const hpM = txt.match(/(\d+)点/);
                if (/生命/.test(txt) && hpM) effects.push({ effect: 'hp', amount: parseInt(hpM[1]) });
              }
            }
            if (money > 0 && effects.length > 0) switchCases[caseNum] = { money, effects };
          }
        }

        // 匹配各楼层的 trader NPC
        for (let i = 0; i < floorIds_.length; i++) {
          const fid = floorIds_[i];
          const f = c.floors[fid];
          if (!f?.map) continue;
          const floorIdx = i + 1;
          const arg1 = String(floorIdx - 1);
          const caseData = switchCases[arg1];
          if (!caseData) continue;
          const h_: number = f.height || 13, w_: number = f.width || 13;
          for (let r = 0; r < h_; r++) {
            for (let cc = 0; cc < w_; cc++) {
              const t = (f.map as number[][])[r]?.[cc];
              if (!t) continue;
              const inf = tileMap[t];
              if (!inf || inf.id !== 'trader') continue;
              const shopId = `trader_f${floorIdx}`;
              // 为每种效果创建单独商品（同一价格，各自一次性）
              const items: any[] = caseData.effects.map(ef => ({
                label: `购买`,
                effect: ef.effect,
                amount: ef.amount,
                cost: caseData.money,
                repeatable: false,
              }));
              shops.push({ id: shopId, items });
              break;
            }
          }
        }
      }

      // ── 楼层 ─────────────────────────────────────────────────
      const floorIds: string[] = floorIds_;

      // 辅助：递归查找事件列表中所有 changeFloor 动作
      function findChangeFloorActions(actions: any[]): any[] {
        const found: any[] = [];
        for (const ev of actions) {
          if (!ev || typeof ev !== 'object') continue;
          if (ev.type === 'changeFloor') found.push(ev);
          if (Array.isArray(ev.true))   found.push(...findChangeFloorActions(ev.true));
          if (Array.isArray(ev.false))  found.push(...findChangeFloorActions(ev.false));
          if (Array.isArray(ev.action)) found.push(...findChangeFloorActions(ev.action));
          if (Array.isArray(ev.caseList)) {
            for (const ci of ev.caseList) {
              if (Array.isArray(ci?.action)) found.push(...findChangeFloorActions(ci.action));
            }
          }
        }
        return found;
      }

      // 辅助：将 h5mota floorId 字符串解析为 1-indexed floorNum
      function resolveFloorNum(floorIdStr: string, currentFloorNum: number): number {
        if (floorIdStr === ':next')     return currentFloorNum + 1;
        if (floorIdStr === ':previous') return currentFloorNum - 1;
        const idx = floorIds.indexOf(floorIdStr);
        return idx >= 0 ? idx + 1 : -1;
      }

      // 预扫描所有楼层的 changeFloor 事件，仅收集向上传送（dest > currentFloor）的目标抵达坐标
      const teleportArrivals: Record<number, { row: number; col: number }> = {};
      for (let si = 0; si < floorIds.length; si++) {
        const sf = c.floors[floorIds[si]];
        if (!sf?.events) continue;
        const sFloorNum = si + 1;
        for (const sEvList of Object.values(sf.events as Record<string, any[]>)) {
          if (!Array.isArray(sEvList)) continue;
          for (const cf of findChangeFloorActions(sEvList)) {
            if (!cf.floorId || !cf.loc) continue;
            const dest = resolveFloorNum(cf.floorId, sFloorNum);
            // 只记录向上的传送（避免覆盖正常 stairsDown 确定的 startPos）
            if (dest > sFloorNum) teleportArrivals[dest] = { row: cf.loc[1], col: cf.loc[0] };
          }
        }
      }

      const floors: any[] = [];
      let bossLocation: { floorId: number; row: number; col: number } | null = null;
      let maxBossHp = 0;

      for (let i = 0; i < floorIds.length; i++) {
        const fid = floorIds[i];
        const f = c.floors[fid];
        if (!f?.map) continue;

        const floorNum = i + 1;   // 1-indexed
        const w: number = f.width  || 13;
        const h: number = f.height || 13;
        const area: number = f.ratio ?? 0;

        // 初始化网格
        const cells: (string | null)[][] = Array.from({ length: h }, () => Array(w).fill(null));

        // 静态地图
        for (let r = 0; r < h; r++) {
          for (let cc = 0; cc < w; cc++) {
            const t = (f.map as number[][])[r][cc];
            if (!t) continue;
            const info = tileMap[t];
            if (!info) continue;  // unknown tile = passable decoration
            cells[r][cc] = tileToCell(info, floorNum);
          }
        }

        // 注入事件触发型 Boss（在触发位置插入怪物）
        // changeFloor key 格式："{col},{row}" (mota-js x,y)
        const events: Record<string, any[]> = f.events || {};
        for (const [key, evList] of Object.entries(events)) {
          if (!Array.isArray(evList)) continue;
          const parts = key.split(',');
          // key 可能是 "col,row" 或 "row,col"，尝试两种解析
          const cx = parseInt(parts[0]), cy = parseInt(parts[1]);
          if (isNaN(cx) || isNaN(cy)) continue;
          // 在 mota-js 中，事件坐标为 x=col, y=row
          const r = cy, cc = cx;
          if (r < 0 || r >= h || cc < 0 || cc >= w) continue;

          for (const ev of evList) {
            if (ev?.type === 'setBlock' && ev.number) {
              const em = effectiveEnemyDefs[ev.number];
              if (!em) continue;
              // 只注入高HP怪物作为Boss候选（HP > 1000）
              if (em.hp > 1000 && !cells[r][cc]) {
                cells[r][cc] = `monster:${ev.number}`;
                if (em.hp >= maxBossHp) {
                  maxBossHp = em.hp;
                  bossLocation = { floorId: floorNum, row: r, col: cc };
                }
              }
            }
          }
        }

        // 注入事件触发型楼梯（changeFloor 事件 → stairsUp）
        // 仅处理向上传送（destFloorNum > floorNum），且目标格为空或怪物
        for (const [evKey2, evList2] of Object.entries(events)) {
          if (!Array.isArray(evList2)) continue;
          const ep = evKey2.split(',');
          const ecx = parseInt(ep[0]), ecy = parseInt(ep[1]);
          if (isNaN(ecx) || isNaN(ecy)) continue;
          const er = ecy, ecc = ecx;
          if (er < 0 || er >= h || ecc < 0 || ecc >= w) continue;

          for (const cf of findChangeFloorActions(evList2)) {
            if (!cf.floorId) continue;
            const dest = resolveFloorNum(cf.floorId, floorNum);
            if (dest <= floorNum) continue;
            const existing = cells[er][ecc];
            // 替换空格、墙（事件触发型传送门常挂在墙上）或怪物（击败后传送）
            if (!existing || existing === 'wall' || existing.startsWith('monster:')) {
              cells[er][ecc] = `stairsUp:${dest}`;
              break;
            }
          }
        }

        // startPos：优先使用传送到本楼层时的抵达坐标，其次找 stairsDown 相邻空格
        let stairDownPos: { row: number; col: number } | null = null;
        for (let r = 0; r < h; r++) {
          for (let cc = 0; cc < w; cc++) {
            if (cells[r][cc]?.startsWith('stairsDown:')) {
              stairDownPos = { row: r, col: cc };
            }
          }
        }
        const startPos = teleportArrivals[floorNum]
          ?? (stairDownPos
            ? findAdjacentEmpty(cells, stairDownPos, h, w)
            : { row: Math.max(0, h - 2), col: Math.floor(w / 2) });

        floors.push({ id: floorNum, area, width: w, height: h, startPos, cells });
      }

      // ── 玩家初始属性 ──────────────────────────────────────────
      const hero = c.firstData?.hero || {};
      // 初始装备加成（hero.atk/def 是裸属性，需加上已装备的武器/盾牌加成）
      const nowWeapon = hero.flags?.nowWeapon;
      const nowShield = hero.flags?.nowShield;
      const weaponBonus = nowWeapon ? (itemDefs[nowWeapon]?.equip?.value?.atk || 0) : 0;
      const shieldBonus = nowShield ? (itemDefs[nowShield]?.equip?.value?.def || 0) : 0;
      const initialPlayer = {
        hp:      hero.hp    || 1000,
        attack:  (hero.atk   || 100) + weaponBonus,
        defense: (hero.def   || 100) + shieldBonus,
        gold:    hero.money || 0,
        yellowKeys: hero.items?.tools?.yellowKey || 0,
        blueKeys:   hero.items?.tools?.blueKey   || 0,
        redKeys:    hero.items?.tools?.redKey     || 0,
      };

      // ── 起始楼层和位置 ────────────────────────────────────────
      const startFid = c.firstData?.floorId || floorIds[0];
      const startFloorIdx = floorIds.indexOf(startFid);
      const startFloor = startFloorIdx + 1;  // 1-indexed
      const heroLoc = hero.loc || {};
      const startPos = {
        row: heroLoc.y ?? (floors[startFloorIdx]?.height ?? 13) - 2,
        col: heroLoc.x ?? Math.floor((floors[startFloorIdx]?.width ?? 13) / 2),
      };

      // ── 组装 ─────────────────────────────────────────────────
      return {
        meta: {
          name:    (window as any).document.title || 'h5mota游戏',
          source:  (window as any).location.href,
          version: c.version || '1.0',
        },
        initialPlayer,
        startFloor,
        startPos,
        bossLocation: bossLocation ?? { floorId: floors.length, row: 1, col: 6 },
        monsters,
        items,
        shops,
        floors,
      };
    });

    console.log(`✅ 提取完成：${data.floors.length} 层楼，${data.monsters.length} 种怪，${data.items.length} 种物品`);
    console.log(`   Boss: ${JSON.stringify(data.bossLocation)}`);
    return data as UGameFormat;
  } finally {
    await browser.close();
  }
}
