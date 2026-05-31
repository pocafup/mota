# 跨层模拟器开发交接文档

**写于**：2026-05-31（机制侦察阶段收尾）  
**目的**：新会话快速上手，不重复上一阶段已确认的结论。

---

## 一、当前进度

| 模块 | 状态 | 关键 commit |
|------|------|------------|
| 战斗引擎（含 special 全套） | ✅ 已验证（oracle 比对） | 8afbd69 |
| MT10 单层重放真绿 | ✅ 全 148 token 逐格对齐 | b3b12fa |
| 机制文档 §A–§I | ✅ 全部落盘 | ae114c1 |
| 飞行系统（三种道具） | ✅ 已落盘 §I | ae114c1 |
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

### ① 切层 token 记录方式

- **fly魔杖**：`core.flyTo` 推入 `"fly:MTn"` → 编码为 `FMTn:` → 解码为 `FLOOR:MTn`
- **走楼梯**：**不产生任何 token**。英雄踩上楼梯格时引擎自动 changeFloor；回放时 UDLR 走到楼梯格即触发，无需显式标记
- **upFly/downFly 使用**：记录 `"item:upFly"` / `"item:downFly"`（ITEM token），不产生 FLOOR token
- **centerFly 使用**：记录 `"item:centerFly"`（ITEM token），不换层，不产生 FLOOR token

**本存档数据**：route_raw 中 FMTn: 共 **220** 个，全部为 fly魔杖。MT50（canFlyTo=false+canFlyFrom=false，通关必经，走楼梯到达）FMT50:=0，铁证楼梯不产生 FMT token。

floor_transitions.json 的 `type` 字段（"changeFloor"/"centerFly"/"keyboard_fly"）**全部错误**，不可信。

### ② MT3 伏击（强制必经，永久改变基线）

玩家进入 MT3 并踩到 (5,9) 时触发伏击事件，**无法绕过**：

```
setValue: hp=400, atk=10, def=10
clearItem: sword5, shield5（装备丢失）
removeFlag: 魔法免疫
changeFloor → MT1 (1,1)
```

**伏击后永久基线**：HP=400, ATK=10, DEF=10（无装备），魔法免疫消失。  
后续所有伤害计算均以此为基础重建；伏击前积累的 ATK/DEF 宝石全部清零（钥匙/金币不受影响）。

**模拟器必须实现此事件**：`sim/` 里不能有 ATK=100/DEF=100 假设。

### ③ 双层地图（terrain + entity）

每个楼层有两张独立的 13×13 矩阵：

- `terrain[y][x]`：地形 tile（墙=1, 地板=0, 楼梯/毒地等各有 tile ID），**静态，不受战斗影响**
- `entities[y][x]`：实体（怪物/门/道具/机关门等），**动态，战斗/事件后清零**

`step()` 判断可通行：`terrain[ny][nx] != 1（非墙）且 entities[ny][nx] 不阻挡`。  
`terrain` 不随事件改变（已验证），`entities` 在怪物死亡/门开/道具拾取后清零。

### ④ 拦截型事件（intercepting events）

部分格子踩上去会触发事件（如 MT10 埋伏、MT3 伏击），事件期间英雄坐标**不更新**，  
事件结束后（changeFloor 等）才切层；`step()` 需识别 intercepting event 并正确处理  
"冻结"状态（当前层结束，后续 token 交给新层）。

### ⑤ 三种飞行道具规则（详见 §I）

| 道具 | 换层？ | 落点 | 绕过 flyTo 检查？ | 目标限制 |
|------|-------|------|-----------------|---------|
| fly魔杖 | ✅ 换层 | 向上飞→目标层 downFloor；向下飞→目标层 upFloor | 否（gate1+gate2） | canFlyTo=false 的层不可飞入（MT0/MT44/MT50） |
| centerFly | ❌ 不换层 | (12-x, 12-y) | — | **对称格须为空**（canUseItemEffect 检查 getBlockId） |
| upFly/downFly | ✅ 换层 | 当前英雄坐标 | ✅ 完全绕过 | ±1层，无其他限制 |

gate1（楼梯连通检查）玩家视角：**不要求站在楼梯旁**，只要当前层存在一条可达楼梯格的无阻碍路径即可飞。

---

## 三、跨层模拟器要解决的核心问题

### (a) 每层持久状态

38 个楼层被 fly魔杖 多次进入（MT31 进入 11 次、MT1/MT20/MT45 各 9 次等）。  
每层的 `entities[y][x]` 必须跨访问持久化：第 1 次打死的怪，第 3 次进来时仍然消失。  
`FloorState` 须从"单层只用一次"升级为"全局 floor registry，每层有且只有一份 state"。

**当前 MT10 实现**：单层 `FloorState`，无此问题；跨层需扩展为 `dict[floorId, FloorState]`。

### (b) 切层的两条路径

```
路径 A：走楼梯
  触发条件：英雄移动到楼梯格（terrain 或 entity 有 changeFloor 事件）
  无 token，UDLR 步骤中自动发生
  落点：由该楼层的 changeFloor 事件指定（loc 字段）
  需要：step() 检测楼梯格踩踏，返回"切层信号 + 目标层 + 目标坐标"

路径 B：fly魔杖（FMTn: token）
  触发条件：收到 FLOOR:MTn token（=route 中 FMTn: 解码结果）
  落点：
    fromIndex ≤ toIndex（向上飞）→ 目标层 downFloor 坐标
    fromIndex > toIndex（向下飞）→ 目标层 upFloor 坐标
  需要：step() 收到 FLOOR:MTn 时直接切层，不检查英雄当前位置
```

### (c) changeFloor 从"冻结"升级为"移交控制权"

MT10 单层实现：踩楼梯格后设 `floor._exited=True`，冻结后续 token。  
跨层实现：需升级为 `floor._exited=True` 时 **切换到目标层**，继续处理剩余 token。

建议接口：
```python
# step() 返回值扩展
StepResult = NewType('StepResult', GameState)
# 或在 GameState 上加字段 pending_floor_change: Optional[FloorChange]
# 外层循环检测后切层，再继续 step()
```

---

## 四、待办（可边做边定，不阻塞跨层开发）

| 编号 | 问题 | 影响 |
|------|------|------|
| J8 | `flag:fly` 的设置条件（决定 gate1 是否生效） | 影响能否飞到某些层 |
| 楼梯识别 | 本存档走楼梯的具体次数/位置（模拟器跑通后可统计） | 验证用 |

---

## 五、目录结构速查

```
data/games51/
  hero_init.json        路由起始状态（引擎直读）
  floors/MT1–MT10.json  已提取（含 map/terrain/events/changeFloor）
  floors/MT11+          待提取（跨层开发需要）
  monsters.json         怪物属性
  items.json            道具定义
  shops.json            商店/祭坛
  floor_transitions.json 220条切层记录（type字段不可信，见§I.8）
  mt10_route_trace.json  MT10段路由（148 tokens）

docs/
  mechanics_51.md       §A–§I 机制全文（事实来源）
  handoff.md            本文件

sim/
  simulator.py          GameState/HeroState/FloorState/step()（MT10已验证）

extract/
  gen_floors.py         提取楼层数据（需扩展到 MT11–MT50）
```

---

## 六、跨层开发建议起点

1. **先提取 MT1–MT50 所有楼层数据**（扩展 gen_floors.py），否则无法跑全程。  
   重点补充各层 `upFloor`/`downFloor`/`canFlyTo`/`canFlyFrom` 字段。
2. **扩展 GameState**：`floor` 字段从单个 `FloorState` 改为 `floors: dict[str, FloorState]` + `current_floor: str`。
3. **实现楼梯切层检测**：step() 移动后检查目标格的 changeFloor 事件，返回切层信号。
4. **实现 FLOOR:MTn token 处理**：step() 遇到该 token 按 §I.3.2 落点规则切层。
5. **全程回放验证**：以 hero_init 为起点，回放完整 route，最终状态与通关存档对齐。
