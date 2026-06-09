# floor_graph.md — 全塔跨层连通（楼梯/飞行/事件传送）源码事实

> 用途：把楼梯/飞行建成「缩点边」之前的源码事实清单（玩家 2026-06-08 要求审计）。
> 复现：`python extract/audit_stairs.py`（直接读 50 个 `floors/MT*.json` 的 `changeFloor`/`events`，不手推）。
> 口径（门禁边/飞行边怎么进搜索）由玩家拍板后再补到本文件末尾，**未确认前不写进搜索代码**。

## 1. 普通楼梯（双向，常规）
- MT0–MT49 主链：每对相邻层一上一下两格楼梯，互为反向边。逐格清单见审计脚本【1】节。
- 落点：到达目标层后停在目标层的 `downFloor`/`upFloor` 坐标（见审计脚本【7】节）。
- 缩点边口径（玩家点1已定）：普通楼梯 = **真实 `step()` 触发换层**，不做零代价抽象（保 firstArrive/落点/剧情副作用）。

## 2. 隐藏层 MT44（isHide=true）
- 引擎解析 `:next`/`:before` **跳过隐藏层** → **MT43 ↔ MT45 楼梯直连**（楼梯图里不存在 MTxx↔MT44）。
- MT44 **只能飞行进入**：`upFly`（从 MT43，物理 +1）/ `downFly`（从 MT45，物理 −1）；`canFlyTo=false`（中心飞行魔杖不能选它为目标）。
- MT44 出口：其 (1,1) 上楼梯 → `:next` = MT45。无下行梯回 MT43。
- 层内永久资源：`shield5(44)@(6,6)`（防御宝石）、`redPotion×4`、`redGuard×2`、`specialDoor@(6,8)`。
- 注：sim/ 已实现 MT44 单向规则（见 mechanics 记录），跨层边只需把它暴露给搜索。

## 3. 地下室 MT0（仅飞行可入）
- `canFlyTo=false, canFlyFrom=true`：仅 `downFly`（从 MT1，物理 −1）可入；中心飞行魔杖不能落 MT0。
- 唯一楼梯 (1,1) 上行 → MT1。无任何楼梯指向 MT0。
- 层内：仅 (6,6) 幸运金币(53)，无怪无门无事件。

## 4. 带门禁的跨层边（条件满足才存在）
| 边 | 实现 | 门禁条件 | 开启动作（源码） | 置信 |
|---|---|---|---|---|
| MT10 (6,11)→MT11 | changeFloor 楼梯格 + `events["6,11"].enable=false` | `flag:10f战胜骷髅队长` | 打 MT10 boss(骷髅队长) → `afterBattle["6,1"]`：`show[[6,11]]` 揭示上楼梯 + `setValue flag:10f战胜骷髅队长=true`（并 openDoor 4,4/6,7/8,4） | **已确认** |
| MT40 (6,1)→MT41 | 事件传送 `events["6,1"]`：`if flag:402 → changeFloor :next` | `flag:402` | MT40 某触发 `events` 单元：setBlock 清场 + `setValue flag:402=true` + `show[[6,1]]`（MT40.json 行~342–359）。`afterBattle` 为空，故为事件触发非战后。**触发格/条件待编码前再核** | 边已确认/触发待核 |
| MT24 (6,2)→MT50 | 事件传送 `events["6,2"]`：`if flag:营救公主 → 过场 + changeFloor MT50 loc[6,7]` | `flag:营救公主` | 结局传送。MT50 无任何楼梯（终点层）、MT49 无上行梯 → **MT50 仅经此结局传送可达** | **已确认** |

## 5. 非可路由的事件传送（搜索须排除）
- **MT3 → MT2 [3,8]（开局噩梦）**：`events` 单元，`flag:03` 一次性。动作含 `setValue hp=400/atk=10/def=10`、清 `nowWeapon/nowShield`、`魔法免疫=false`，再 `changeFloor MT2`。**会重置全部属性**，是开局剧情过场，**绝不能当作可路由楼梯边**（搜索若踏入＝清零进度）。

## 6. 飞行机制（route 实测确有使用）
- `centerFly` = **ITEM:50**（中心飞行魔杖）：CHOICE 菜单选一个已访问且 `canFlyTo≠false` 的层瞬移，消耗 1 个 ITEM:50。
- `upFly`/`downFly` = 键盘 K49/K50/K52：物理 ±1 层飞行（**不跳隐藏层**，故为进/出 MT44 的唯一手段）。
- 仅 MT0/MT44 `canFlyTo=false`；其余层默认可作飞行目标。
- route 三次飞行（`floor_transitions.json`）：centerFly ITEM:50 `MT46→MT37`；键盘 `MT45→MT37`(K50)、`MT48→MT47`(K49)。
- 飞行不耗 HP（见 docs/solver-design.md FLY-CHEAP）。

## 7. 口径（玩家 2026-06-08 已确认 ✅）
- A. 普通双向楼梯 → 真实 `step()` 边（不要零代价算子抽象，保副作用）。
- B. **门禁边（MT10/MT40/MT24）= 条件 flag 满足才出现的 `step()` 边，不写死**。满足条件本身（如打 MT10 boss）就是一次「付代价合并」，由第一性原理自然纳入搜索。
- C. **接入顺序：先只接楼梯边把跨层缩点结构跑通 + 拿真实膨胀数据；飞行边（centerFly/up/downFly）作为紧随其后的第二步，在同一框架加**。一次少引入变量。
- D. MT3 开局噩梦重置边：搜索**完全排除**（非可路由边）。
- E. **MT0 地下室 / MT44 隐藏层都纳入可达空间**。两层均为飞行专属入口（down/upFly），故在「楼梯优先」第一步里仍不可达，待第二步飞行边接入后自然连通；MT44 的 `shield5` 防御宝石届时由搜索自行判断值不值得绕进去。

## 8. 落地实现顺序（据 §7 口径）
1. **第一步（本轮）**：`solver/quotient.py` 解除单层限制——可达性放行离层 child；把当前块内**可达且已启用**的楼梯格作为算子，用真实 `step()` 触发换层生成子状态（免资源代价）；门禁未满足的楼梯格因引擎不可踏而自然不生成边。先跑通 + 看真实状态膨胀，不预优化控宽。
2. **第二步**：同框架加飞行边（centerFly=ITEM:50 选层；up/downFly=物理±1，可入 MT0/MT44）。
3. route 层序骨架（`phase1._forced_block` 的 `⟶换层`）与 `excursion_experiment.py` 在第一步跑通后退役。
