# 跨层模拟器开发交接文档

**写于**：2026-05-31（机制侦察阶段封板）  
**目的**：新会话快速上手，不重复上一阶段已确认的结论。

---

## 🟢 实现 earthquake/bomb/pickaxe/upFly-downFly + KEY 派发表 + MT44 隐藏层单向楼梯：token4417/4504/4528/4582 转绿，32/32 检查点全 PASS，对齐至 token4582(MT47)（2026-06-04，commit 1e84590）

- **进展**：**32/32 检查点全 PASS**，**模拟器逐 token 对齐至 token4582**，**全塔 50 层数据齐备**，**全部道具（snow / centerFly / earthquake / bomb / pickaxe / 飞翼 upFly-downFly）已实现**。本段把 KEY 快捷键体系坐实并补齐最后几个道具，消掉 token4417/4504/4528/4582 四个 FAIL：
  1. **KEY 派发表坐实（引擎硬编码 `onKeyUp`，非存档配置）**：49→pickaxe（破墙镐，无备选）、50→bomb（否则 hammer）、51→centerFly（瞬移面板）、52→[icePickaxe,freezeBadge,earthquake,upFly,downFly,…] 首个可用。50/52 两行与玩家实测（bomb/earthquake）吻合 → 表权威 → 49=pickaxe 一并坐实。绑定落 `data/games51/replay_keybindings.json`（`{"52":"earthquake","50":"bomb","49":"pickaxe"}`），sim 按表派发不硬编码。`decode_route.py` 补 `K<keyCode>`（无冒号）→ `KEY:<keycode>` 解析。
  2. **earthquake / bomb / pickaxe / upFly / downFly 五道具实现**：earthquake（§L.6，键'4'，清当前层全图 canBreak 墙 tile1/2，**这是 token4417 根因**——破 MT37 内墙后拾齐 11黄2蓝1红/ATK+16/DEF+16）；**bomb**（§I.7，键'2'，炸英雄四方向相邻 hp<500 的怪，**走 afterBattle 路径**与战斗死亡同——MT44(6,9) 一发炸 (5,9)(7,9) 两 redGuard→openDoor(6,8)→上取 redPotion×?/shield5，**这是 token4528 根因**）；**pickaxe**（§L.5，键'1'，破四方向相邻 canBreak 墙，earthquake 的相邻版）；**upFly/downFly**（§I.7，飞翼，唯一进入 MT44 隐藏层的手段）。
  3. **MT44 隐藏层单向楼梯**：`isHide:true` → `canFlyTo=false / canFlyFrom=true`，MT43↔MT45 楼梯直连跳过 MT44，MT44 楼梯只能**出**不能**进**，唯一入口 = upFly/downFly。修 `_copy_state` 漏传 `is_hide`（每步被重置 False）的根因 bug。
  4. **真值订正两处**（玩家主动裁定，非凑绿）：token4417 (2,4)→(2,3)、**token4582 层 MT44→MT47**（route 末两跳 FLOOR 显式飞 MT47 + 坐标/HP/属性/钥匙全吻合为证）。
- **剩余**：**终局段 token4582→6360（约 1800 token）无真值覆盖**。已知路上有：**tok5131 踩章鱼区**、**tok5315–5326 八个 help 键（no-op）**、**tok5391 KEY:49 用 pickaxe**、**tok6354 第三次 centerFly**、**MT26 公主设 flag**、**MT24 传送 MT50**、**MT49 竞技场（/10 魔王）**、**MT50 终局 boss（杀死即 win = 重放终止）**。**N-b（真假结局口径）按假结局对齐**。
- **下一步**：玩家提供终局段真值，对齐到通关。

---

## 🟢 扩层最后一批 MT42–MT50 + 四种地形伤 + MT44 隐藏层跳层 + MT31 商人：token4222/4350 转绿，28/32 检查点 PASS（2026-06-04，commit 7696385）

- **进展**：**28/32 检查点 PASS**，**MT1–MT47 段逐 token 推进中**，**全塔 50 层数据已提取完毕（各 0 处不一致）**。本段把最后九层（MT42–MT50）落盘并实现四类地形伤 + 两个跨层/商人机制，消掉 token4222/4350 两个 FAIL：
  1. **MT42–MT50 九层提取落盘**（raw capture + clean JSON）；附带 **tile 4 订正为 star**、**§N 终局 boss 链**、**whiteKing 核实订正**。全塔 50 层至此提取完毕。
  2. **四种地形伤实现**：魔法警卫**夹击**(special 16)、巫师**领域**(15)、**阻击**(18) 按格损血，外加既有血网/毒地，统一走 `_apply_zone_damage`。
  3. **MT44 隐藏层跳层**（数据驱动，非硬编码）：`isHide:true` → 楼梯 `:next/:before` 解析对隐藏层透明（`_resolve_floor_id` 跳过），**MT43↔MT45 楼梯直连**，MT44 只能用 upFly/downFly 进入（当前 sim 未建模，为后续待办）。新增 `FloorState.is_hide` 字段从 JSON `isHide` 读入。
  4. **MT31 商人落盘**（消 token4350 的 黄−2蓝−1 真因）：`shops.json` 补 MT31(1,11) 4黄+1蓝/1000金条目（之前只在 _note、catalog=None 早退致购买空转）；核实 `_handle_trader` 的 CHOICE:1 状态机正确（不置 flag、商人留存、可反复对话）、多件 give 循环正确（之前只验过 MT6 单件）。回归 68 测试 + 既有商人检查点零波及。
- **下一步**：从首个 FAIL token4417 起逐笔账（见下方剩余检查点 + ledger）。

---

## 🟡 首个 FAIL = token4417（下个会话起点）+ 剩余检查点 4504/4528/4582

- **首个 FAIL — token4417**：真值 `MT37(2,4) HP=1479 ATK=202 DEF=154 黄=11 蓝=2 红=1`，sim 停在 `MT38(2,1) HP=1479 ATK=186 DEF=138 黄=2 蓝=0 红=0`——**HP 吻合，但 ATK/DEF 各缺 16、黄缺 9 蓝缺 2 红缺 1**（大量道具/属性没拿到，且落错层）。窗口 **token[4350→4417] 逐笔全状态账**已写入 `checkpoint_ledger.txt`。
  - 窗口关键 Δ：tok4352 `ITEM:50` centerFly、tok4353 蓝1→0、tok4360 `CHOICE:0` 金−4000 +earthquake（**MT47 商人买地震卷轴已生效**）、tok4367 `L`→MT48、tok4368 `FLOOR:MT37`、tok4396 `U`→MT38，随后 **tok4396 起 tok4397–4416 在 MT37↔MT38 之间 L/U 楼梯横跳**（疑似机关，sim 当作普通楼梯反复弹）。
  - **玩家预告该段含三项已登记待确认**（铁律：不自行猜根因/改真值/改断言凑绿，待源码坐实）：
    - **J13 神圣盾免疫地形伤**（`docs/mechanics_51.md` §J）：神圣盾对应哪个 flag、获取楼层/条件待坐实；当前未实现免疫。
    - **J14 MT43 移动的魔法警卫**：whiteKing 是否每步/每回合移动、移动规则待坐实；sim 当前按静态怪处理，若实为移动怪则夹击触发格随之变。
    - ~~**J15 MT48 地震卷轴破 MT37 墙**~~ → ✅ **已解决（2026-06-04）**：商人在 **MT47(5,2)**（**非 MT48**，原笔误已订正 handoff/mechanics，shops.json 本就对）。tok4369 `KEY:52`（键'4'）= 使用 earthquake（玩家实测坐实，推翻旧推测"K52=upFly"），效果 = 清**当前层全图**所有 canBreak 墙（tile 1/2），不跨层。实现见 §L.6 + `_use_earthquake`。**这正是 token4417 根因**：破墙后 MT37 内部连通，tok4370–4417 拾齐 11黄2蓝1红/ATK+16/DEF+16，**token4417 属性全吻合**（旧"MT37↔MT38 横跳"消失，改为正常遍历内部）。残留仅终点坐标 sim(2,3) vs 真值(2,4) 差一步，待裁定（见下）。
- **剩余检查点（3 个，4417 之后）**：token **4504 / 4528 / 4582**，集中在 **DEF 暴涨段 134→204→309**（疑 shield5 / 大盾拾取）：
  ```
  token4504: MT43 (9,4)   HP=123  ATK=202 DEF=204  黄=5 蓝=2
  token4528: MT44 (6,5)   HP=623  ATK=202 DEF=304  黄=5 蓝=2
  token4582: MT44 (11,2)  HP=4723 ATK=202 DEF=309  黄=5 蓝=2
  ```
  注：token4528/4582 在 **MT44 隐藏层**内（验证 upFly/downFly 进入 + 层内战斗/拾取），token4504 HP=123 是极限态（损血精度验金石）。

---

## 🟢 MT40 boss存活才打(§M.7) + 死亡硬终止(§M.8) + changeFloor stair 落点：token4141 转绿，26/26 全 PASS，MT1–MT41 全程对齐（2026-06-04，commit eb1470e）

- **进展**：**26/26 检查点全 PASS**，**MT1–MT41 全程逐 token 对齐**，**68/68 测试全绿**（原 64 + 新增 4）。本段三件事，消掉最后一个 FAIL（4141）：
  1. **MT40 boss「存活才打」(§M.7)**：核对 events["6,7"] 内原始 JS（`extract/mt40_raw_capture.json`）——`for i=0..12: if core.getBlockId(a[i])!==null { move+battle }`，红门以上 13 格只对**还活着**的怪逐个先攻强制战斗，**已清格 getBlockId===null 跳过、零伤**。修：`MT40.json` 13 场 battle 各带 `loc:[x,y]`（顺序即源码 a 数组）；`simulator` battle 分支带 loc 走存活判断（entities==0 跳过、非 0 取该格怪 force 战斗后清格），**无 loc 保持无条件（MT32 不受波及）**。本路线 centerFly 瞬移 (2,1) 后先清光 13 格 → 踩 (6,7) 一场不打、HP 恒 262（吻合真值）。**纠正上一段误判**：旧 MT40.json 把 13 场展开为无条件 battle、丢了 getBlockId 存活判断——这才是 4141 HP 崖真因（非上段所列 (a)(b)(c)）。
  2. **死亡硬终止 (§M.8)**：`GameState.dead`，`step()` 入口 dead 则一切 token no-op（冻结死亡点）；任何 hp≤0 结算（强制战斗 / 事件扣血 setValue / step 末尾兜底）置 dead；强制战斗序列中途致死 → `_execute_event_list` 立即停剩余指令。重放路线不触发，**为 solver 探索"会死路线"准备**（普通战斗 damage≥hp 拦截不变、永不致死，能死的只有 force/事件/地形）。
  3. **changeFloor 支持 stair 字段落点（G7 解决）**：事件驱动的 `changeFloor` 原只认 `loc`、缺省 (0,0)；补上**有 loc 用 loc、无 loc 有 stair 查目标层 down_floor/up_floor、都无则报错**，与 fly 魔杖 / `_apply_stair_change` 同一套解析。MT40 events["6,1"] 的 `changeFloor :next stair:downFloor` → 落 MT41.downFloor=[6,2] → **token4141 转绿**。
- **新增 4 测试**（`test_force_battle_mt32.py`）：§M.7 全清零伤 / 部分清场只打存活；§M.8 死亡 token no-op 冻结 / 死亡中途停战。
- **G7（MT41 跨层机关）已解决**（= changeFloor stair 解析），从待确认移除。
- **下一步**：**MT42–MT50 待提取**（raw capture + 落盘 `data/`）；**营救公主终局待验证**（通关条件 + 终局事件）。MT1–MT41 已是逐 token 金标准基线。

---

## 🟢 多格boss footprint + setBlock跨层 + getBlock条件 + centerFly：token3371/3704/4012 转绿（2026-06-04，25/26 检查点 PASS，commit c33934d）

- **进展**：**25/26 检查点 PASS**，**MT1–MT40 基本逐 token 对齐**，**64/64 测试全绿**。本段实现四件事，一次性消掉级联 FAIL 中的三个（3371/3704/4012）：
  1. **多格 boss footprint（魔龙/章鱼九宫格占位）**：`monsters.json` 给 magicDragon(257)/octopus(258) 声明 `footprint`（3×3，锚点=怪实体格向上展开两行），活着时九格全 noPass，只能站锚点正下方朝上触发战斗；afterBattle `hide remove` 清占位（配套清 terrain 层）。`tiles.json` 把 17 订正回 `airwall`（noPass:true 保留）。→ **token3371/3704 转绿**。
  2. **setBlock 跨层**：`setBlock` 支持 `floorId` 指向非当前层（按需加载目标层），数字 / 字符串 number 两种写法（字符串走 `_id_to_tile_full` 解析），区分 entity / terrain 层落子。
  3. **getBlock 裸条件分支（口径已坐实）**：`_eval_single` 新增 `core.getBlock(x,y) ===/!== null`（区别于 getBlockId）。口径：blockObjs 收录所有 tile≠0 的格（墙/门/楼梯/地形/装饰/怪/道具），tile==0→null；双层模型映射为 **entity≠0 或 terrain≠0 即非 null**。用于 MT39 `autoEvent[8,4]` 九宫格条件（开两扇黄门后 (4,4) 黄门→`openDoor`+`setBlock centerFly3`）。
  4. **centerFly（ITEM:50 瞬移，消耗性已坐实）**：中心对称瞬移到 (W-1-x, H-1-y)，**不切层**；canUseItemEffect 校验对称点 `getBlockId ∈ {null,'none','airwall'}`（airwall 可落——与移动 noPass 是两套判定）；消耗性：`items.json` centerFly `cls=tools`，`_afterUseItem` 源码 tools 用即 −1（§K.2），故"配 3 用 3"是消耗必然、非巧合。centerFly3(331) 拾取给 3 个 centerFly。→ 勇者 tok3925 拿 centerFly3、tok4085 瞬移进 MT40 段、黄钥匙不多耗 → **token4012 转绿**。
- **唯一 FAIL — token4141**（下个会话起点）：真值 `MT41(6,2) HP=262 ATK=182 DEF=134 黄=7`，sim 停在 `MT40(7,9) HP=1246 黄=4`（连楼层都没进对）。新窗口 **token[4012→4141]（129 步）逐笔全状态账**已写入 `checkpoint_ledger.txt`。**三个待玩家裁定材料**（铁律：不自行猜根因 / 改真值 / 改断言凑绿）：
  - **(a) tok4075 `L` @ MT36(1,11) HP+800**：这 +800 是什么？（祭坛 / 祝福 / 血瓶？还是误算）
  - **(b) tok4084–4095 MT40↔MT39 往返**：`FLOOR:MT40` 后又 R 到 MT39(11,10)、再 D 回 MT40——这段楼梯 / 边界相邻行为 sim 是否建模对了？
  - **(c) 真值黄钥匙多 3 把（真值 7 vs sim 4）**：真实路线在 sim 未到达的格拿了 3 把黄钥匙 → sim 路线在窗口内提前分叉，没走到那些格。
- **G7（MT41 跨层机关 `events[10,2]`，setBlock destruct 语义 + hasVisitedFloor 条件）仍挂待确认**（详见 memory/mechanics_status.md）。token4141 要进 MT41，**大概率与 G7 相关**，下个会话处理。

---

## 🟢 扩层 MT34–MT41 + token2965 转绿（2026-06-04，22/26 检查点 PASS，commit 533c2e2）

- **进展**：**22/26 检查点 PASS**，**MT1–MT33 全程逐 token 对齐 + MT34–MT41 八层已提取**，**64/64 测试全绿**。本段三件事：扩层 MT34–MT41（含原始 raw capture 落盘）、实现 snow 冰魔法（§K）、补 MT40 骑士队长 boss 13 连战测试（§M）；核心是**修正 flower(168) 误标 noPass**。
- **token2965 根因 = flower(168) 提取误标 noPass，非"踩格机关"**（玩家原假设两处踩格事件，依铁律核对源码后报告差异）：
  - **机关二（踩(10,5)→关(10,4)/(10,8)机关门）源码里存在且 sim 早已正确实现**：`MT33.events["10,5"]`（setBlock specialDoor + flag:骑士剑机关 + getBlockCls 四角怪判断）配 `autoEvent["11,4"]` 开门半。
  - **机关一（踩(9,10)→(8,10)变墙）源码里查无此事件**（clean JSON、live raw capture、firstArrive/parallelDo/afterBattle 全空）。真因：`extract/blocksInfo_full.json['168']={id:flower,cls:terrains}` **无 noPass 字段** → h5mota terrains 默认可通行；旧 tiles.json 误标 `noPass:true` 把 (8,10) 当墙。
  - **玩家实测路线坐实**：tok2939–2942 自 (7,10) 连按 R 向右穿 (8,10)→(9,10)→(10,10) 取 sword3(+40 ATK)，sim 误判撞墙 → ATK 卡 114(真值 154，差正好 40)。
  - **修正** `tiles.json` 168 `noPass:false`（来源订正 blocksInfo + 路线印证）→ token2965 精确命中 `MT33(8,3) HP=6 ATK=154`，级联 token3212 同时转绿。（玩家所述"变墙"那条回退路最优路线未走，sim 不杜撰源码无据机制。）
- **当前 FAIL（4 个，级联自 3371）**：token **3371 / 3704 / 4012 / 4141**。
  - **首个 FAIL = token3371 MT32(1,4)：仅 HP sim=1006 vs 真值=606（差 +400），ATK/DEF/坐标/黄钥匙全吻合**——即 sim 在 [3212→3371] 这 159 步**少挨 400 HP**（与原 ATK 缺口无关，是另一回事）。
  - **首个 FAIL 窗口 token[3212→3371] 已逐笔摆账**（`checkpoint_ledger.txt`，跑分器自动生成）。HP 收支净 +100（906→1006），真值要 606。**三个待玩家裁定的可疑点**：
    - **(a) tok3253 `CHOICE:0` @ MT2(11,5)**：sim 只判"金币+1000"。这是什么选项事件？是否还应扣 400 HP 或别的代价？（语义未确认）
    - **(b) tok3301 蓝血瓶 @ MT35(5,5)**：sim 给 +800（base200×ratio4，数据模型自洽）。真实回血是 +800 还是 +400？
    - **(c) 五场战斗**（tok3228/3230/3333/3365/3367，损血 −220/−220/−260/−140/−260）某场是否带未建模 special 而少算损血。
  - **G7（MT41 跨层机关 `events[10,2]`）继续挂待确认**（详见 memory/mechanics_status.md），**token4141 依赖它**，按玩家指示先不动。
- **下个会话**：玩家裁定上述 (a)(b)(c) 三个可疑点后，据此定位并修复 token3371（铁律：不自行猜根因/改真值/改断言凑绿），随后看 3704/4012 级联，4141 待 G7 裁定。

---

## 🔵 扩层第三批 MT29–MT33（2026-06-04，20/21 检查点 PASS，唯 token2965 待查）

> ⚠ **本段 token2965 已于上方 🟢 段解决（根因 flower(168) 误标 noPass，commit 533c2e2）。以下保留作历史。**


- **进展**：**20/21 检查点 PASS，MT1–MT33 基本对齐**（差 token2965）。61/61 测试全绿，17 个 pytest 检查点 + token2400/2501/2804 端点全 PASS（commit 50af961）。
- **本段修复**（commit 50af961）：
  1. **删除「同步 move 后对话→拦截」死规则**：源码坐实纯文字对话 `\t[name]text` 在回放中一律不拦截（引擎 replayActions 无文字处理器，文字非 token 类型，仅 choices 读取选择 token）。该规则当年为 MT10 小偷事件所加，但 **MT10 自 f28ceab 起已不依赖它**（小偷事件靠 move+hide 独立成立），全塔扫描仅误伤 MT32 boss 演出（`extract/scan_sync_dialog.py` 证实仅 2 处，均 MT32）。删除后 token2501 的 HP/楼层/位置/DEF/黄钥匙全部对齐。
  2. **祭坛购买补金币守卫**：`data/games51/common_events.json` 商店三档购买（HP/ATK/DEF）各包一层 `if status:money >= flag:money1`——**钱不够→不成交、不扣钱、不加属性、times1 不变，但 CHOICE token 仍被消化**（玩家连按 7 次买攻击，第 4 次起金币 <440 被引擎拒绝）。修前无条件成交致 ATK 多加 +32（4 次）。修后 token2501 ATK=102、gold=401 逐项吻合。（times1 跨层累计经核对正确，入 MT32 时 =3，非 bug。）
- **§G.7.3 标注**：`docs/mechanics_51.md` §G.7.3 旧时间线已与现状不符，已标注「已过时，以 §M 和当前实现为准」（只加标注，未删原文）。
- **唯一 FAIL — token2965**（下个会话起点）：真值 `MT33(8,3) HP=6 ATK=154 DEF=70 黄2`，sim 出 `MT33(5,9) HP=226 ATK=114`。token2804(854/112) → 2965(6/154) 之间 **HP-848、ATK+42**——这段有恶战 + 大量加攻（宝石/祭坛?），新分叉待查。**HP=6 是极限态，意味着这一段每场战斗损血必须一字不差，是损血精度的验金石**。下个会话需用玩家中间真值夹逼定位第一处分叉。

---

## ✅ MT1–MT28 全程逐 token 对齐（2026-06-03，18/18 检查点全 PASS）

扩层第二批 MT21–MT28 已彻底对齐：**token2400 转绿（MT28(2,11) 1261/78/64 5黄），MT1–MT28 全程逐 token 忠实复现，54/54 测试全绿**（commit 95e1b4f）。第一批 MT15–MT20（tok[2000] 转绿，commit b11f9c2）见 §八(0)；第二批根因/发现见 §八(0.5)。进度详见 §一。

> 检查点口径：17 个在 `tests/test_checkpoints.py`（tok[100..2000]，pytest 套件内）；第 18 个 token2400 由 `extract/verify_tok2400.py` 独立验证（端点 MT28）。合计 **18/18** 金标准锚点全绿。

> 历史（已解决）：上一阶段曾长期卡在「模拟器重放未在 rle[69] 触发 MT3(5,9) 伏击」。根因是 MT1 早期路径走错（非伏击未发生）。现已修复——tok[100] 即为伏击后基线 ATK=10/DEF=10（正确触发），MT3 伏击机制详见 §二②。

### ⚠ 永久铁律（新会话必须遵守，禁止跳过）

1. **禁止**用模拟器输出推翻 `docs/mechanics_51.md §H` 或 `memory/project_overview.md` 里的既定事实。
2. **禁止**修改测试断言来"凑绿"——断言失败说明模拟器有 bug，应修模拟器。
3. **改任何文档（§H、memory）或测试断言之前，必须先得到人工确认。**
4. 模拟器结果与玩家实测矛盾时，结论只能是"模拟器有 bug"，永远不能是"事实有误"。

---

## 一、当前进度

| 模块 | 状态 | 关键 commit |
|------|------|------------|
| 战斗引擎（含 special 全套） | ✅ 已验证（oracle 比对） | 8afbd69 |
| MT10 单层重放真绿 | ✅ 全 148 token 逐格对齐 | b3b12fa |
| 机制文档 §A–§I（含飞行系统全貌） | ✅ 全部落盘 | 见最新 commit |
| 机制侦察阶段封板 | ✅ 完成 | 见最新 commit |
| 跨层模拟器 MT1–MT14 | ✅ 13/13 检查点全PASS，24/24测试全绿 | f28ceab |
| 商店/祭坛购买（insert/while/break/CHOICE） | ✅ 通用实现，MT12祭坛+商店验证 | f28ceab |
| MT12/MT13/MT14 楼层数据 | ✅ 已提取校验（各0处不一致） | f28ceab |
| **跨层模拟器 MT1–MT20（扩层第一批）** | ✅ **17/17 检查点全PASS，54/54 测试全绿，MT1–MT20 逐 token 对齐** | **b11f9c2** |
| 老人对话事件 + 打不过原地不动(canBattle) | ✅ 通用实现，tok[2000] 转绿 | b11f9c2 |
| 商人(trader)≠祭坛(blueShop)、cross双倍攻、祭坛格noPass | ✅ 见 §八(0) 根因 | e7f20d0 / 75687ea / b11f9c2 |
| **跨层模拟器 MT1–MT28（扩层第二批）** | ✅ **18/18 检查点全PASS，54/54 测试全绿，MT1–MT28 逐 token 对齐** | **95e1b4f** |
| MT14红钥匙(三僵尸autoEvent/getBlockCls)、MT28钥匙回收商人、MT26公主改写MT24、tiles.json修怪名 | ✅ 见 §八(0.5) 根因 | 95e1b4f |
| **跨层模拟器 MT1–MT33（扩层第三批）** | 🔵 **20/21 检查点 PASS（差 token2965），MT1–MT33 基本对齐** | **50af961** |
| 删除「同步move后对话拦截」死规则 + 祭坛购买金币守卫 | ✅ 见顶部🔵段 | 50af961 |

**路由起始状态**（来源：`data/games51/hero_init.json`，引擎直读）：

```
楼层：MT1  位置：(6, 11)  朝向：down
HP=1000  ATK=100  DEF=100  mdef=0  gold=0
持有道具：fly×1
flag：nowWeapon=sword5, nowShield=shield5, 魔法免疫=true
```

注：ATK=100 已含 sword5 buff，DEF=100 已含 shield5 buff；初始即有 fly魔杖（startText 给的）。

---

## 二、关键事实速查（新会话最易踩坑）

### ① 切层方式分类（共四类）

| 类型 | 路由表现 | 本存档计数 | 备注 |
|------|---------|-----------|------|
| **fly魔杖** | `fly:MTn` → `FMTn:` → `FLOOR:MTn` | **220 次** | 绝对主路径 |
| **走楼梯** | 无 token，UDLR 走到楼梯格自动触发 | 极少（需模拟器统计） | 包含 MT1→MT2 首次跨层 |
| **upFly/downFly** | `item:upFly`/`item:downFly` → `ITEM:{n}` | 若有则在 ITEM token 中 | 不产生 FLOOR token |
| **事件 changeFloor** | 无任何 token | 至少 2 次（MT3伏击→MT2；MT24事件→MT50） | 不产生任何 token |

`floor_transitions.json` 的 `type` 字段（"changeFloor"/"centerFly"/"keyboard_fly"）**全部错误**，不可信。

**"无 FMT token ≠ 走楼梯"**：无 FMT token 意味着"未被 fly魔杖 飞入"，可能是走楼梯、upFly/downFly（ITEM token）、事件 changeFloor（无 token）或根本未访问。禁止用排除法默认"走楼梯"。

### ② MT3 伏击（强制必经，永久改变基线）

玩家进入 MT3 并踩到 (5,9) 时触发伏击事件，**无法绕过**（(5,9) 是 MT3 唯一上行路径）：

```
setValue: hp=400, atk=10, def=10
setValue: flag:nowWeapon = null   （卸装，sword5 永久失去）
setValue: flag:nowShield = null   （卸装，shield5 永久失去）
setValue: flag:魔法免疫 = false
hide loc=(5,9) remove=true        （触发格变空地，不再触发）
changeFloor → MT2 (3,8)           ← 目标是 MT2，不是 MT1
```

**伏击后永久基线**：HP=400, ATK=10, DEF=10（无装备），魔法免疫消失。  
伏击前积累的 ATK/DEF 宝石全部清零（钥匙/金币不受影响）。

**模拟器必须实现**：`_execute_instruction()` 需支持 `changeFloor` 指令类型；`_set_value()` 需支持 `"null"` → Python `None`。

### ③ 双层地图（terrain + entity）

每个楼层有两张独立的 13×13 矩阵：

- `terrain[y][x]`：地形 tile（墙=1, 地板=0, 楼梯/毒地等各有 tile ID），静态
- `entities[y][x]`：实体（怪物/门/道具/机关门等），动态，战斗/事件后清零

`step()` 判断可通行：`terrain[ny][nx] != 1 且 entities[ny][nx] 不阻挡`。

### ④ 拦截型事件（intercepting events）

同步 move/generateMove 之后紧跟字符串对话 → 事件暂停，等待 CHOICE token 推进；英雄坐标不更新。事件脚本内的 `changeFloor` 指令触发后须立即设置 `pending_floor_change` 并停止当前事件执行。

### ⑤ 飞行道具规则（详见 §I）

| 道具 | 换层？ | 落点 | canFlyTo/From 生效？ | 实际限制 |
|------|-------|------|---------------------|---------|
| fly魔杖 | ✅ | 向上飞→目标层 downFloor；向下飞→目标层 upFloor | ✅ 均检查 | gate1+gate2；canFlyTo=false 层不可飞入（MT0/MT44/MT50） |
| centerFly | ❌ 不换层 | (12-x, 12-y) 对称格 | — | 对称格须为空（getBlockId==null） |
| upFly | ✅ | 当前英雄坐标 | ❌ **不检查** | **硬编码 `index >= 49` 封顶**（从 MT49 起飞被拒） |
| downFly | ✅ | 当前英雄坐标 | ❌ **不检查** | 硬编码 `index < 1` 地板；目标格须为空 |

**upFly/downFly 可用范围**：只能在 floorIds 下标 1–48 之间的楼层起飞（即 MT1–MT48），MT0/MT49/MT50 均受限（MT0 被 index<1 挡，MT49/MT50 被 index>=49 挡）。

gate1（楼梯连通检查）：不要求站在楼梯旁，只要当前层存在可达楼梯格的无阻碍路径即可飞。

### ⑥ MT50 完整进出规则（特殊，封板确认）

**进入 MT50：唯一路径是 MT24(6,2) 事件 changeFloor**

触发条件：踩 MT24(6,2) 且 `flag:营救公主=true`  
落点：MT50(6,7)  
原因：fly魔杖（canFlyTo=false 被 flyTo 拒）、upFly（index=49≥49 被硬编码拒）、downFly（MT51 不存在）均不可达。

**离开 MT50：打通关后游戏自动结束**

MT50 内战胜最终 BOSS 后触发 `win` 事件，游戏结束——这是**全塔重放的终止条件**，不需要模拟器处理离场。MT50 内 `canFlyFrom=false`（fly魔杖被拒），upFly（index=50≥49 被拒）；downFly 不检查 canFlyFrom，理论上可用于测试，但正常通关流程不需要离场。

**MT50 的模拟器处理**：重放到 MT50 内 BOSS afterBattle 的 `win` 指令时，终止重放，记录最终状态。

---

## 三、跨层模拟器要解决的核心问题

### (a) 每层持久状态

38 个楼层被 fly魔杖 多次进入（MT31 最多 11 次）。每层的 `entities[y][x]` 必须跨访问持久化。  
`FloorState` 升级为 `dict[floorId, FloorState]`（全局 registry）+ `current_floor: str`。

### (b) 切层的四条路径（扩展自两条）

```
路径 A：走楼梯
  触发条件：UDLR 移动后目标格在 change_floor 字典中
  落点：change_floor[loc_key]["loc"] 坐标 + floorId
  实现：step() 设 pending_floor_change，外层循环完成切层

路径 B：fly魔杖（FLOOR:MTn token）
  触发条件：action 以 "FLOOR:" 开头
  落点：fromIndex≤toIndex → 目标层 downFloor；否则 upFloor
  实现：step() 内直接切层 + 更新 visited_floors

路径 C：事件 changeFloor 指令
  触发条件：事件脚本执行到 {"type":"changeFloor",...} 指令
  落点：指令内 loc 字段（如 MT3伏击→MT2(3,8)；MT24事件→MT50(6,7)）
  实现：_execute_instruction() 新增 changeFloor 分支，设 pending_floor_change

路径 D：upFly / downFly（ITEM:{n} token）
  触发条件：ITEM token 对应 upFly 或 downFly 道具
  落点：当前英雄坐标（不用 upFloor/downFloor 字段）
  目标层：floorIds[currentIndex ± 1]
  实现：step() 处理 ITEM token 时识别，直接切层
```

### (c) changeFloor 从"冻结"升级为"移交控制权"

楼梯/事件 changeFloor → 设 `pending_floor_change`（含目标 floorId+坐标）+ `_exited=True`，外层循环检测后切层，后续 token 在新层处理。fly魔杖/upFly/downFly → step() 内直接完成切层。

---

## 四、待办分类

### 不阻塞跨层开发——靠全程 route 重放自然解决

| 编号 | 问题 | 为何不阻塞 |
|------|------|-----------|
| J8 | `flag:fly` 的设置条件（gate1 开关） | 重放时 flag 状态由 route 事件自然更新；全程跑通后从状态快照读出 |
| J9 | ✅ **已解决**：`flag:营救公主` 在 MT26(6,6) 公主事件设置 | 详见 §八(0.5)；该事件还 setBlock 改写 MT24 第6列(6,2/6,3/6,4)打通——跨层动态建图点，待走 MT50 流程端到端验证 |
| J10 | MT21–MT23、MT27–MT30 是否实际访问 | 普通层无特殊机制；全程模拟器跑通后统计访问记录即可 |
| J11 | MT24(6,2) 事件可否重复触发 | 无 `hide/remove=true`，理论可重复；重放中若多次踩格则自然测试到 |

### 仍需查证（不紧急）

| 编号 | 问题 | 优先级 |
|------|------|--------|
| J5 | 护身符（amulet）获取楼层和条件 | 中 |
| J6 | 魔法免疫 flag 的其他设置条件（MT3 伏击已确认为移除路径） | 中 |
| J12 | MT50 实际离场坐标（正常通关不需要，仅调试用） | 低 |

---

## 五、目录结构速查

```
data/games51/
  hero_init.json        路由起始状态（引擎直读）
  floors/MT1–MT10.json  已提取（含 map/terrain/events/changeFloor）
  floors/MT11+          待提取（跨层开发第一步）
  monsters.json         怪物属性
  items.json            道具定义
  shops.json            商店/祭坛
  floor_transitions.json 220条切层记录（type字段全部错误，不可信）
  mt10_route_trace.json  MT10段路由（148 tokens，已验证）

docs/
  mechanics_51.md       §A–§I 机制全文（唯一事实来源）
  handoff.md            本文件
  solver-design.md      求解器设计待办

sim/
  simulator.py          GameState/HeroState/FloorState/step()（MT10已验证）

extract/
  gen_floors.py         提取楼层数据（需扩展到 MT11–MT50）
  mt24_raw_events.txt   MT24 events 原始数据（含 MT50 特殊传送脚本）
  mt49_mt50_raw.txt     MT49/MT50 连通结构原始数据
  upfly_downfly_src.txt upFly/downFly/fly魔杖 canUseItemEffect 源码对比
```

---

## 七、检查点回归状态（2026-06-03 更新，17/17 PASS ✅）

> 注：本节的 13 点指 tok[100..1300]，仍全 PASS。扩层新增 4 点 tok[1400/1500/1603/2000] **全部转绿**（commit e7f20d0、75687ea、b11f9c2）。**合计 17/17 PASS，MT1–MT20 全程逐 token 对齐**；本批根因与待办见 §八(0)。

### 已确认结论

#### (a) ⚠ 检查点口径：tokens[:N+1]，tokens[0] 为不计步的初始化事件

**这是之前所有"差一格/晚1步"位置偏差的总根因，已修正（2026-06-02）。**

`tokens[0] = CHOICE:1` 是初始化事件，不计入玩家步数。  
玩家的 tok[N] = 执行完第 N 步之后的状态 = 处理完 `tokens[0..N]`（共 N+1 个 token）。  
正确口径：`tokens[:N+1]`，**禁止改回 `tokens[:N]`**。

- `tokens[:N]` 每点少跑 1 步，坐标偏 1 格，但因相邻步通常无属性变化，大多数点碰巧 PASS 而遮盖偏差。
- 只有当第 N+1 步恰好跨越属性事件（如血瓶拾取）时才暴露（tok[500] 就是典型案例）。

验证：改为 `tokens[:N+1]` 后，原 8 个 PASS 点仍全部 PASS，tok[500] 从 FAIL 转 PASS。

#### (b) Route 记录撞墙 token（纠正旧假设）

旧假设（"route 不记录撞墙，撞墙不产生 token"）**已被推翻**。

实测：tok[259-263] 对应原始字符串 `R5`（5步向右），在 MT4 上因墙被模拟器处理为 BLOCKED，英雄位置/HP/钥匙全部无变化。这些 token 存在于解析列表中，模拟器正确处理为无操作，checkpoint 索引不受影响。

**结论**：route 会记录撞墙移动；模拟器 BLOCKED 处理正确；checkpoint 定位无误。

#### (c) 解析器 Bug：`M<n>:` 后数字被丢弃（已记录，暂不修）

**现象**：原始 route 中存在 `M<mapID>:<count>` 格式的 token（如 `M8:4U`、`M10:1R`）。  
解析器将 `M8:` 解析为 `UNKNOWN:M8:`，然后紧随的数字 `4` 因不是字母而落入 `else: i += 1`，**被静默丢弃**。

**影响范围**：
- 第一个丢弃字符在原始串 raw[1544]，对应 tok[2200]
- 共丢弃 149 个字符，全部在 tok[2200]..tok[6138] 区间
- 当前 13 个检查点（tok[100]..tok[1300]）**完全不受影响**

**待办**：`M<n>:<count>` 的语义待确认（可能是商店/飞行道具调用），修复解析器前需先理解其含义。当前优先级：低（不阻塞 tok[1300] 以内的回归）。

#### (d) MT10(6,11) 楼梯门 enable 机制（已修复，commit 335dfd8）

**根因**：`show` 指令在模拟器里是 no-op，导致 MT10(6,11) 的 `events["6,11"].enable` 永远不从 `false` 变为 `true`。同时 `_apply_stair_change` 不检查 `enable`，导致楼梯在 Visit4 之前（tok[946]、tok[992]）就错误触发，英雄过早进入 MT11。

**修复内容**（simulator.py，commit 335dfd8）：
1. `show` 指令实现：遍历 `loc` 列表，将 `events[loc_key]["enable"]` 置为 `True`。
2. `_apply_stair_change` 新增 enable 检查：若 `events[loc_key].get("enable") is False`，则返回 False（楼梯不触发）。

**连锁效果**：tok[1000]（floor 从 MT11→MT10）、tok[1100]、tok[1200] 均因此转绿。

#### (e) 当前 PASS/FAIL 状态（2026-06-02，commit f28ceab）

| 检查点 | 状态 | 备注 |
|--------|------|------|
| tok[100..900]（9个） | ✅ PASS | 原有全部保持，无回归 |
| tok[1000] | ✅ PASS | enable修复后转绿（floor=MT10, HP=304, ATK=27） |
| tok[1100] | ✅ PASS | 连锁转绿 |
| tok[1200] | ✅ PASS | 连锁转绿 |
| tok[1300] | ✅ PASS | floor=MT14, HP=785, ATK=42, DEF=30（2026-06-02 转绿） |

**总计：13/13 PASS。MT1–MT14 全程逐 token 对齐完毕。24/24 回归测试全绿（含 test_checkpoints.py + test_replay_mt1_mt11.py）。**

#### (f) generateMove 异步误判修复（2026-06-02，commit f28ceab）

**根因**：`_execute_event_list` 对 `generateMove` 设置了 `had_sync_anim=True`，导致 MT10 events["6,9"]（小偷事件）后续对话字符串被误升级为拦截型事件，英雄卡在 MT10(6,9) 无法前往 MT11。

**源码证据**（`extract/mt6_10_raw.txt`）：
- events["6,5"]（埋伏）：所有 `generateMove` 均有 `"async":true` + `waitAsync`——需同步时**显式声明**
- events["6,9"]（小偷）：`generateMove` 无 `async` 字段、无 `waitAsync`——纯异步/fire-and-forget

**修复**（simulator.py 556行）：`t in ("move", "generateMove")` → `t == "move"`

**效果**：tok[1300] 从 `floor=MT10` 推进到 `floor=MT11`；原有 12 个 PASS 全部保持，无回归。

#### (g) tok[1300] 转绿：MT12-MT14 提取 + 商店/祭坛购买实现（2026-06-02）

**已提取并校验**：MT12.json / MT13.json / MT14.json，各楼层逐格比对 0 处不一致。

**已实现（simulator.py + common_events.json）**：
- `insert:"商店"` → 展开公共事件 `商店`（while+choices 循环）
- `while` / `break` / `CHOICE:n` token 推进选项分支
- 祭坛 `setValue flag:ratio` + 商店 `setValue +=` 通用实现（按 §D 公式，不硬编码）
- NPC 交互后英雄坐标移动到 NPC 格（修复旧 bug：hero 卡在相邻格）
- fly魔杖 MT12→MT13→MT12→MT13→MT14 双弹跳路径正确执行

**tok[1300] 验证值**：floor=MT14, HP=785, ATK=42(30+4×3), DEF=30。

---

## 八、下个会话待办（已知，先别动）

### (0) ✅ 扩层第一批 MT15–MT20 全部对齐（2026-06-03）：tok[2000] 转绿，17/17 全 PASS

**重大进展**：17/17 检查点全 PASS，**MT1–MT20 全程逐 token 忠实复现**，54/54 测试全绿（commit b11f9c2）。

**本批修复的根因（供参考）**：

1. **商人(trader 122) ≠ 祭坛(blueShop 131)**（commit 75687ea）：两套独立脚本。商人卖钥匙/二次对话消失，**不**共用祭坛"商店"commonEvent。
2. **祭坛格 7/8 标 noPass + 模拟器数据驱动读 noPass**（commit e7f20d0）：不再硬编码 WALL_TILES，塔特有装饰墙由 `tiles.json` 的 `noPass:true` 声明。
3. **互动格统一不移入**：fakeWall / 祭坛 / 激活 NPC / 商人 / 老人——触发互动后英雄**当步不移入**，需再按一次同向 token 才走入（与引擎"撞 NPC 不移动"一致）。
4. **cross 双倍攻击**：持十字架对兽人/吸血鬼 ATK ×2（cross 由 MT19 门事件给予，到达后生效）。
5. **打不过的怪原地不动（canBattle 规则）**（commit b11f9c2）：`_fight_monster` 中 `if result.damage >= hero.hp: return`——损血 ≥ 当前 HP（战后 HP≤0）则引擎 `canBattle(damage<hp)` 拒战，英雄原地不动（等同撞墙），HP/坐标/钥匙/金币全不变。
6. **老人对话事件（commonEvent "对话"）**（commit b11f9c2）：撞 oldman(121) → `systemEvents.oldman` → `insert "对话" args=[楼层号,x,y,0]` → 按 `flag:arg1`(楼层号) `switch` 显示提示 → 末尾 `hide loc=[arg2,arg3] remove` 老人消失。MT18 老人(纯提示)即此机制；通用支持 `insert args`(设 flag:arg1..arg4)、`switch/caseList`、`hide` 动态 loc 表达式。MT2(给1000金币)/MT3(给手册)的老人因 `有选择的对话=true` 会挂 choices 拦截，由路线中的 CHOICE token 消化（本路线仅 MT3 老人在 tok[115] 被撞、tok[116]=CHOICE:0 干净消化；MT2 老人全程未撞）。

**金标准锚点（全部已对齐 ✅）**：

```
tok[1809]: MT15 (7,10)  HP=179 ATK=68 DEF=54   ✅  （恶战 599→179，损 420）
tok[1902]: MT20 (6,10)  HP=591 ATK=68 DEF=54   ✅
tok[2000]: MT16 (3, 1)  HP=618 ATK=72 DEF=56   ✅  （区域内累计 ATK 68→72、DEF 54→56）
```

MT18 老人逐 token 吻合玩家真值：tok[1827]→(2,2)、tok[1828] 撞老人对话→老人消失/原地不动、tok[1829]→走入(3,2)。

**两个待办（都不影响当前结果）**：

- **(待办α) `item:` 前缀在 `_set_value` 是 no-op**：涉及 `item:book`(MT3老人手册)、`item:superPotion`(MT16)、`item:yellowKey`(MT12) 三处 setValue。当前 no-op 下 17/17 全绿（含受检的 HP/yk），说明现口径不依赖这三处生效。**若改为生效会同时激活 superPotion(动 HP)/yellowKey(动 yk) 两个受检字段，有打破现绿之险**；故将来确需时再单独评估 + 跑全回归，绝不顺手加。
- **(待办β) 解析器 `M<n>:` 吞数字 / snow 冰冻 / 矿镐(pickaxe)** 待实现：分别在扩到 tok[2200+]、MT35、用 `ITEM:47` 时才需要，当前不阻塞（详见 §八(b)(c)）。

**第二批 MT21–MT28 已完成**（✅ 端点验证 token2400 转绿，详见 §八(0.5)）。

复现脚本：`diag_1730_2000.py`（逐 token 打印 tok[1730..2000] + 锚点对比；注：脚本内 tok[1680] 锚点坐标 (1,11) 系手记写反，sim 实为 (11,1)、属性全对，非检查点、不影响结论）。第二批端点脚本：`extract/verify_tok2400.py`。

### (0.5) ✅ 扩层第二批 MT21–MT28 全部对齐（2026-06-03）：token2400 转绿，18/18 全 PASS

**重大进展**：18/18 检查点全 PASS，**MT1–MT28 全程逐 token 忠实复现**，54/54 测试全绿（commit 95e1b4f）。token2400 端点 = MT28(2,11) HP1261/ATK78/DEF64/5黄，逐项吻合。

**本批关键发现（已提取落盘 data/，模拟器已实现）**：

1. **MT14 红钥匙 = 三僵尸全灭的 autoEvent**：`MT14.autoEvent["1,3"]`，条件 `core.getBlockCls(1,1)!=='enemys' && (3,1) && (2,2)`（三只 zombieKnight 全杀），动作 `openDoor(1,3)`(清 330 不可破坏墙) + `setBlock redKey (1,3)`(放红钥匙)。英雄 tok2173 捡到，tok2322 飞 MT20 后开 (6,9) 红门上行。
   - **根因**：`_eval_single` 原不认 `core.getBlockCls(x,y) ===/!== 'enemys'` → 三子条件全 False → autoEvent 永不触发 → redKey 恒 0 → MT20 红门封死、英雄卡底排倒退回 MT19、token2400 停在 MT21（而非 MT28）。
   - **修复**（simulator.py `_eval_single`，commit 95e1b4f）：加 getBlockCls 分支，数据驱动判该格 entity 是否在 `_tile_to_enemy`（tiles.json enemys 段），不硬编码楼层。全 50 层仅 MT14 一处用 getBlockCls，影响面孤立。零回归。

2. **J9 解决：`flag:营救公主` 在 MT26(6,6) 公主(princess 132)事件设置**：撞公主 → events[6,6] false 分支设 `flag:营救公主=true` + setBlock 改写 **MT24 第6列**(6,2)/(6,3)/(6,4) 为地板——**跨层动态建图点**（一层事件改另一层地图，呼应建图铁律"地图连通性是动态的"）。此后踩 MT24(6,2) 且 flag 成立 → changeFloor MT50(6,7)。已完整提取，待英雄实走 MT50 流程端到端验证。

3. **MT28 钥匙回收商人（specialTrader 124，(8,4)）**：while+choices 循环，卖 1 黄钥匙 −1黄/+100金；"卖5把"/"全卖了" 受 `flag:额外功能开关` 门控；"下次再说"=break。已通用实现。

4. **tiles.json 怪物错名修正**（依据 `extract/blocksInfo_full.json` 引擎权威，commit 95e1b4f）：230/234/238–243/245–251/258 共 **16 个 enemys** id+_monster 重生成 + 补 **npcs 132=princess**（commit message 计为"17 处"）。MT15(6,6) 那只由错名 steelRock 正为 octopus（大章鱼 hp1200/atk180/def20）。零回归（MT15 那只本路线未打）。**仍缺** 9 个引擎正确怪名未进 monsters.json（yellowKing/poisonSkeleton/skeletonKing/skeletonWizard/redSkeletonCaption/demon/demonPriest/whiteHornSlime/badPrincess），当前已提取楼层均未用到，第三批若遇到再补。

**下一步：扩层第三批 MT29+**。玩家已给新检查点金标准真值：

```
token2501: MT32 (6,10)  HP=143  ATK=102 DEF=64  黄=5
token2804: MT33 (7,11)  HP=854  ATK=112 DEF=68  黄=3
token2965: MT33 (8,3)   HP=6    ATK=154 DEF=70  黄=2   ← HP 仅剩 6，极限状态
```

注意：**MT32 有祭坛**（§D 加点公式，搜索/重放须含祭坛加点）；token2965 HP=6 是极限状态（多损一格地形/战斗即致死，最易暴露损血/地形 bug）。token2400 已穿过 tok[2200]（§七c 解析器 `M<n>:` 吞数字起点）仍逐项对齐，说明 tok≤2400 解析无碍；但 §八(b) 的 `M<n>:` bug 影响区延伸到 tok[6138]，扩到 token2501+ 前需确认该区间是否出现 `M<n>:` token，必要时先修解析器。

### (a) ✅ test_replay_mt10.py — 7个埋伏机关测试已升级（commit 48693c1）

7 个隔离测试已全部替换为全路径真实重放验证（从 hero_init 出发，使用完整 51_*.h5route）。
MT10 埋伏访问为 Visit 5（tok[1168]），关键时刻：tok[1190]触发(6,3)→85；tok[1204]autoEvent(6,3)→0；tok[1250]进入MT11(HP=701,gold=305,RK=0)。
50/50 全测试全绿。

### (b) 解析器 Bug：`M<n>:` 后数字被吞（tok[2200] 后）

已记录于 §七(c)。`M<mapID>:<count>` 格式语义待确认，修复前须先理解含义。影响范围 tok[2200..6138]，当前检查点全部在 tok[1300] 以内，不阻塞。

### (c) 冰冻徽章 snow 机制（模拟器待实现）

机制已记入 `docs/mechanics_51.md §K`（数据来源：源码）。模拟器尚未实现。扩展到 MT35 层时再实现，当前不阻塞。

---

## 六、跨层开发建议起点

1. **提取 MT1–MT50 所有楼层数据**（扩展 gen_floors.py），重点补充 `upFloor`/`downFloor`/`canFlyTo`/`canFlyFrom` 字段。
2. **修复 simulator.py 的两个已知 bug**：
   - `_execute_instruction()` 新增 `changeFloor` 指令分支（MT3伏击/MT24事件均依赖）
   - `_set_value()` 补充 `"null"` → `None` 映射（伏击卸装依赖）
3. **扩展 GameState**：`floor` → `floors: dict[str, FloorState]` + `current_floor: str` + `pending_floor_change: Optional[...]` + `visited_floors: set[str]`。
4. **实现四条切层路径**（见三(b)），以 fly魔杖（220次）为主路径优先验证。
5. **全程回放验证**：以 hero_init 为起点，回放完整 route；终止条件 = MT50 内 `win` 指令触发。
