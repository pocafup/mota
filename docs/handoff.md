# 跨层模拟器开发交接文档

**写于**：2026-05-31（机制侦察阶段封板）  
**目的**：新会话快速上手，不重复上一阶段已确认的结论。

---

## ⚠ 当前最高优先级BUG（新会话必读，禁止跳过）

### 不可推翻的事实（网站实测铁证）

- `rle[69]`：英雄踩上 MT3(5,9) → 触发伏击事件 → HP/ATK/DEF 强制赋值为 400/10/10 → sword5/shield5/魔法免疫全部清除 → `changeFloor` 强制传送至 MT2(3,8)。
- `rle[70]` 起：英雄已在 MT2 继续移动。
- **route 必经此伏击，不存在绕开的可能**（MT3(5,9) 是左侧唯一纵向通道）。
- 这是玩家在网站实际运行存档的亲眼所见，是终极证据，高于任何代码输出。

### BUG 定性

**模拟器重放未能在 rle[69] 触发伏击 = 【模拟器重放 bug】**，绝不是"伏击没发生"或"路线绕开了伏击"。**禁止再质疑伏击是否发生。**

上一会话出现的严重错误：用有 bug 的模拟器输出推翻了玩家网站实测确认的事实，并据此篡改了 `docs/mechanics_51.md §H` 和 `memory/project_overview.md`。已回退。**绝不允许再犯同样的错误。**

### 关键矛盾线索（指向 bug 位置）

模拟器报告：
- decoded[0–185] 英雄全程停留在 MT1
- decoded[20–55] 英雄连续几十步撞墙（卡在 MT1(5,3) 附近）

事实：rle[69] 英雄已在 MT3(5,9)。

**结论**：模拟器在 MT1 早期（约 decoded[20] 附近）就让英雄走错了路径或卡死，根本没能走到 MT3 伏击格。

**修复方向**：查英雄为何在 MT1 早期被卡住或走错路径。可能原因：
1. 地图 tile 读错——某个应该可通行的格子被误判为墙
2. `firstArrive` 未实现——导致初始通路状态没有正确设置（例如某道机关门应被打开但实际未打开）
3. 钥匙/门逻辑错误——英雄拿了黄钥匙但模拟器没有正确更新可通行格

**修的是"让英雄走对路径"，不是改伏击事件本身。**

### 严禁事项（新会话必须遵守）

1. **禁止**用模拟器输出推翻 `docs/mechanics_51.md §H` 或 `memory/project_overview.md` 里的既定事实。
2. **禁止**修改测试断言来"凑绿"——断言失败说明模拟器有 bug，应修模拟器。
3. **改任何文档（§H、memory）或测试断言之前，必须先得到人工确认。**
4. 模拟器结果与事实矛盾时，结论只能是"模拟器有 bug"，永远不能是"事实有误"。

---

## 一、当前进度

| 模块 | 状态 | 关键 commit |
|------|------|------------|
| 战斗引擎（含 special 全套） | ✅ 已验证（oracle 比对） | 8afbd69 |
| MT10 单层重放真绿 | ✅ 全 148 token 逐格对齐 | b3b12fa |
| 机制文档 §A–§I（含飞行系统全貌） | ✅ 全部落盘 | 见最新 commit |
| 机制侦察阶段封板 | ✅ 完成 | 见最新 commit |
| 跨层模拟器 | ❌ 尚未开始 | — |

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
| J9 | `flag:营救公主` 在何处设置 | 重放中事件执行到该 setValue 时自动写入 hero.flags；跑通后可查 |
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

## 七、13检查点回归状态（2026-06-02 更新）

### 已确认结论

#### (a) ⚠ 检查点口径：tokens[:N+1]，tokens[0] 为不计步的初始化事件

**这是之前所有"差一格/晚1步"位置偏差的总根因，已修正（2026-06-02）。**

`tokens[0] = CHOICE:1` 是初始化事件，不计入玩家步数。  
玩家的 tok[N] = 执行完第 N 步之后的状态 = 处理完 `tokens[0..N]`（共 N+1 个 token）。  
正确口径：`tokens[:N+1]`，**禁止改回 `tokens[:N]`**。

- `tokens[:N]` 每点少跑 1 步，坐标偏 1 格，但因相邻步通常无属性变化，大多数点碰巧 PASS 而遮盖偏差。
- 只有当第 N+1 步恰好跨越属性事件（如血瓶拾取）时才暴露（tok[500] 就是典型案例）。

验证：改为 `tokens[:N+1]` 后，原 8 个 PASS 点仍全部 PASS，tok[500] 从 FAIL 转 PASS。**当前 9/13 PASS。**

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

#### (d) 当前 PASS/FAIL 状态（口径修正后，2026-06-02）

| 检查点 | 状态 | 备注 |
|--------|------|------|
| tok[100..900]（9个） | ✅ PASS | 含 tok[500]（口径修正后转绿） |
| tok[1000] | ❌ FAIL | floor:MT11≠MT10, HP+45, ATK-1（深层独立bug） |
| tok[1100] | ❌ FAIL | HP-292, ATK-1（深层独立bug） |
| tok[1200] | ❌ FAIL | HP-292, ATK-1（深层独立bug） |
| tok[1300] | ❌ FAIL | floor:MT10≠MT14, HP-414, ATK-13（深层独立bug） |

tok[1000..1300] 的偏差与口径无关，是 tok[900] 之后独立的模拟器 bug，下个会话调查。

---

## 六、跨层开发建议起点

1. **提取 MT1–MT50 所有楼层数据**（扩展 gen_floors.py），重点补充 `upFloor`/`downFloor`/`canFlyTo`/`canFlyFrom` 字段。
2. **修复 simulator.py 的两个已知 bug**：
   - `_execute_instruction()` 新增 `changeFloor` 指令分支（MT3伏击/MT24事件均依赖）
   - `_set_value()` 补充 `"null"` → `None` 映射（伏击卸装依赖）
3. **扩展 GameState**：`floor` → `floors: dict[str, FloorState]` + `current_floor: str` + `pending_floor_change: Optional[...]` + `visited_floors: set[str]`。
4. **实现四条切层路径**（见三(b)），以 fly魔杖（220次）为主路径优先验证。
5. **全程回放验证**：以 hero_init 为起点，回放完整 route；终止条件 = MT50 内 `win` 指令触发。
