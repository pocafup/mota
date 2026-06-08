# 全塔 block 级 event/outEvent 盲区审计（games/51）

**日期** 2026-06-06　**方法** Playwright live 抓取 h5mota.com/games/51（`status.played=false` 标题屏，pristine 静态）
**结论** ✅ **清白** —— 除已封进 sim 的 flower 单向阀（MT33/MT38）外，全塔无任何"引擎建模、sim 没建模"的可被 solver 钻的机制。

本审计是 C 段教训（solver 重穿 MT33 flower 薅增益再折返造假赢，根因是该机制 sim 没建模）的直接排雷：开工阶段一前先扫清同类洞。

---

## 0. 根因发现：block 事件是【类型级】的，不在 floor.events

排查 MT33/MT38 flower 单向阀为何被系统性漏提时，定位到真相：

- `core.floors['MT33'].events` 只有 `{'10,5'}` —— **(8,10) 的阀门事件根本不在 floor.events 里**（pristine 静态也没有，排除"runtime 消费后删除"假设）。
- `core.maps.blocksInfo`（**完整版**，230 项）才是真源：block **类型** 168=flower 自带
  `noPass:true, canPass:true, event:[switch floorId…], outEvent:[hide remove destruct + closeDoor yellowWall]`。
  阀门脚本用 `switch core.status.floorId` 一个共享脚本分 MT33(right) / MT38(down) 两 case，逐 case 硬编码 loc。
- 早先 `extract/blocksInfo_full.json` 是 **删减版**（只有 `{id,cls}`，无 event 字段），所以历史提取看不到。
- raw_capture 全是 `JSON.stringify(core.floors[fid])`，类型级事件天然不在其中 → **整类 block 内联事件被系统性遗漏**（旧待办说的盲区，根因即此）。

> **泛化铁律**：换塔时，block 级 event/outEvent 必须抓 `core.maps.blocksInfo` 的【类型定义】，
> 不能只抓 `core.floors[fid].events`。前者是类型级共享脚本（flower/light 这类），后者是实例级（坐标触发）。

**权威落盘**：`extract/audit_blocksInfo_with_events_51.json`（完整 blocksInfo + 所有带机制字段的类型）。

---

## 1. 类型级机制全表（19 个带 event/outEvent/trigger 的 block 类型）

对全 51 层 `map` 做存在性扫描（静态），并查全塔 events 有无 `setBlock` 动态放置（无）：

| id | 名称 | 机制 | 全塔出现 | sim 建模 |
|----|------|------|---------|---------|
| 168 | flower | event(switch floorId)+outEvent → 单向阀/防回头墙 | **MT33(8,10), MT38(2,5)** | ✅ 已封（outEvents 口径，单测 test_one_way_valve_mt33/38） |
| 2 | fakeWall | trigger=openDoor, keys={}, canBreak=true → 无钥匙暗墙，撞上自动开 | MT5/9/12/14/16/18/19/35（31 处，MT35 有 22 格暗墙阵） | ✅ sim:26/303/1064/1354 |
| 3 | fakeWall2 | 同上但 canBreak=false | MT12(11,1)/MT16(11,11)/MT19(6,3)（3 处） | ✅ 同 fakeWall（震不破，镐/震只清 canBreak） |
| 81-86 | 各色门 | trigger=openDoor | 普遍（黄门 239 处等） | ✅ 标准门 |
| 121 | oldman | trigger=oldman | 18 层 | ✅ sim:1039 |
| 122 | trader | trigger=trader | 9 层 | ✅ sim:1035 |
| **165** | **light** | **outEvent: setBlock darkLight（踩离自封 noPass）** | **0 处（静态+动态均无）** | 无需（不出现） |
| 167 | ski | trigger=ski（冰面滑行） | 0 处 | 无需（不出现） |
| 169/170 | box/boxed | trigger=pushBox（推箱子） | 0 处 | 无需（不出现） |
| 11-14 | lava/poison/weak/curseNet | trigger=passNet（地形伤害网） | 0 处 | 无需（本塔无网格地形伤） |
| 84 | greenDoor | trigger=openDoor | 0 处 | —— |

**关键**：唯一另一个"自封型"（与 flower 同类、最易造假赢）的 **light(165) 的 outEvent，全塔 0 处使用**（静态 map 无、events 里也无 `setBlock light`）。flower 是全塔唯一在用的自封/单向机制，已封。**无残留洞。**

---

## 2. 实例级（floor.events 等）交叉核对：51 层全对

把 live `core.floors[fid]` 的 12 个事件承载字段（events / autoEvent / afterBattle / afterGetItem /
afterOpenDoor / firstArrive / eachArrive / parallelDo / cannotMove / cannotMoveIn / beforeBattle /
changeFloor）逐层 diff 我的 `data/games51/floors/*.json`：

- **0 个 MISSING**（我的数据没漏任何 live 有的事件 loc）。
- 仅 3 处 VALUE 差异，**全部良性**：
  1. `MT1 events[7,10]` —— `enable:false` 的"作者 king"更新日志 NPC，我省略了版本日志正文（无行走触发效果）。
  2. `MT1 firstArrive` —— 我省略了一个纯 UI 的 `function`(strokeRect 提示框，`if isReplaying return` 重放即 no-op)。实质 token（item:I333、flag:开启特性/addhp 选择）全在。
  3. `MT40 events[6,7]` —— **故意的忠实展开**：把 live 的 boss-战 JS `function(){…insertAction(todo)}` 翻成 13 个显式 `battle` token（鬼战士×3/士兵×3/双手剑士×3/红骑士×3+黄骑士队长），带 `_comment` 记录 `getBlockId!==null` 存活判定与 force/special 语义（符合 CLAUDE.md 逐条翻译铁律）。

**地形伤害网（cannotMove/cannotMoveIn）**：全 51 层 **均空** → 本塔"空气墙"（魔王/骷髅队长/章鱼/公主周围隐形墙）不靠 cannotMoveIn，而是**静态 map tile**。

**权威落盘**：`extract/audit_floors_events_live_51.json`。

---

## 3. 地图几何核对：51 层逐格全等

live `core.floors[fid].map` vs 我的 `data/.../map`：**51/51 完全一致，0 格差异**。
→ 所有静态墙（含 boss 隐形"空气墙"）已逐格捕获，**solver 无"穿不存在的墙"幻影捷径风险**。
**权威落盘**：`extract/audit_floors_maps_live_51.json`。

---

## 4. 事件 token 类型全覆盖（27 类）

全塔出现的 27 种 event token `type`，对照 sim dispatch：

- **状态/控制流**：setValue / if / switch / while / for / break —— ✅（for 见下）
- **块变更**：setBlock / hide / show / openDoor / closeDoor / break / setBgFgBlock / update —— ✅（setBgFgBlock/update 在 no-op 组，不改碰撞）
- **移动**：move / generateMove / insert —— ✅
- **战斗**：setEnemy / battle —— ✅
- **楼层**：changeFloor / win —— ✅
- **演出 no-op**：playSound/playBgm/sleep/waitAsync/tip/setCurtain/**function**/**for** —— sim 显式 no-op（simulator.py:1533）

### function token（8 个）逐一甄别
| # | 层/路径 | 性质 |
|---|---------|------|
| 0 | MT1 firstArrive | UI strokeRect，`if isReplaying return` —— 演出 |
| 1 | MT3 events[5,9] | rotateVec 图心旋转**动画**（伏击的视觉），伏击的真正 token 是同 event 内的 setValue 400/10/10 —— 演出 |
| 2 | MT24 events[6,2] | statusBar 标题刷新 —— 演出 |
| 3 | **MT32 events[6,10]** | `hero.hp=0; afterBattle` —— 骑士队长"圣水复活"分支（见 §5） |
| 4 | **MT40 events[6,7]** | boss 战 —— **已在我数据展开为 battle token** |
| 5 | MT42 events[5,10] | drawImage(battle **图标**)，关键词误命中，实为演出 |
| 6 | MT50 afterBattle | 数敌人数填 flag:t（通关结算显示）—— 演出 |
| 7 | MT50 afterBattle | countNonKeyItems 通关评分 —— 演出 |

→ 唯一实质性 function 是 MT40（已展开）。其余演出，no-op 安全。

---

## 5. 已记录待核（非盲区，已捕获，仅 sim 行为待确认）

**MT32(6,10) 骑士队长 = 脚本化"打不死、退场去 MT40"遭遇**：
```
IF core.canBattle('yellowKnight')         # 能撑过这场 → 打（掉血、队长退场）
  TRUE:  battle yellowKnight
  FALSE: IF (!flag:addhp && flag:开启特性)  # 撑不过 + 特性版
           IF status:atk > yellowKnight.def # 能破防 → hp=0 后 afterBattle 圣水复活
             TRUE:  function{ hero.hp=0; afterBattle('yellowKnight') }
             FALSE: battle yellowKnight      # 破不了防 → 真打 → 死
         FALSE: battle yellowKnight          # addhp/纯净版 → 正常打
move(6,10); "到 40 楼再打"; 队长退到(6,9); setEnemy special=0
```
- 数据**已捕获**（与 live 全等），非盲区。route 走 canBattle=TRUE 分支（挨一场 yellowKnight 伤、队长退场），**46 检查点已验证该分支**。
- 复活分支（hp=0 function）sim no-op = **悲观安全**（sim 不会凭空给出引擎才有的"败而复生"，只会更保守，不造假赢）。仅在"撑不过+特性版+能破防"才触发，HP 最大化的 solver 不会主动走死局。
- ⚠ sim 需正确求值条件 `core.canBattle('yellowKnight')` / `status:atk>getEnemyInfo().def`；taken 分支已被检查点保证。若 phase-1 solver 在 MT32 出现异常掉血/卡死，回看此处。

---

## 复现方法（换塔/重核）
1. Playwright 打开 `h5mota.com/games/<id>/`，等 `window.core` 就绪（标题屏即可，`status.played=false` 取 pristine 静态）。
2. 抓 `core.maps.blocksInfo`（类型级 event/outEvent/trigger）+ `core.floors[fid]`（实例级 events 等 + map）。
3. 类型级：列出所有带 `event/outEvent/trigger` 的 id → 对每层 map 扫存在性 + 查 events 有无 `setBlock <id>` 动态放置。
4. 实例级：12 事件字段 + map 逐层 diff 已落盘 data/。
5. function token 逐个甄别演出 vs 玩法。
