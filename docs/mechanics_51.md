# 50层魔塔 机制规格文档

来源：h5mota.com/games/51  
提取时间：2026-05-29  
所有数据均从游戏源码提取，禁止凭空推断。

---

## A. 战斗伤害公式

### A.1 基础战斗流程

确定性，无随机数。每回合：玩家先手（除非怪物有先攻特殊属性）。

**来源**：`core.enemys.enemydata.getDamageInfo` 的完整实现（从运行中引擎通过 `toString()` 取得）。

### A.2 调用链

```
core.getDamage(enemy, x, y, floorId)
  → core.enemys.getDamage(id, x, y, floorId)
    → core.enemys._getDamage(enemy, hero, x, y, floorId)
      → core.enemys.getDamageInfo(enemy, hero, x, y, floorId)
        → core.enemys.enemydata.getDamageInfo(enemy, hero, x, y, floorId)
```

`getDamageInfo` 返回对象 `{mon_hp, mon_atk, mon_def, init_damage, per_damage, hero_per_damage, turn, damage}` 或 `null`（无法击杀）。

### A.3 getEnemyInfo — 怪物属性修正

战斗前先通过 `getEnemyInfo` 修正怪物属性（**来源**：`core.enemys.enemydata.getEnemyInfo`）：

```
# special 10（模仿）
if hasSpecial(10): mon_atk = hero_atk; mon_def = hero_def

# special 3（坚固）
if hasSpecial(3) and mon_def < hero_atk - 1:
    mon_def = hero_atk - 1
    → 保证 hero_per_damage = max(0, hero_atk - mon_def) = 1（恰好能打动）

# special 25（光环）：buff 周围敌人 HP/ATK/DEF，百分比叠加
# special 26（支援）：将相邻同类怪物加入战斗（累加 HP，取最大 ATK/DEF）
```

### A.4 getDamageInfo — 完整伤害计算

```python
def get_damage_info(enemy, hero):
    # 1. 攻击力修正
    hero_atk = hero.atk
    if flag_skill == 1:         hero_atk *= 2   # 二倍斩
    if hasItem('cross') and enemy is zombie/zombieKnight/vampire:  hero_atk *= 2
    if hasItem('knife') and enemy is magicDragon:  hero_atk *= 2

    # 2. 无敌检查
    if hasSpecial(20) and not hasItem('cross'):
        return None  # 无敌，无法击杀

    # 3. 初始伤害
    init_damage = 0

    # special 11（吸血）
    if hasSpecial(11):
        vampire_damage = floor(hero_hp * enemy.value)
        init_damage += vampire_damage
        if enemy.add: mon_hp += vampire_damage   # 血量回复

    # 4. 每轮伤害
    per_damage = mon_atk - hero_def
    if hasSpecial(2):                            # 魔攻：无视防御
        per_damage = mon_atk
    per_damage = max(0, per_damage)
    if hasSpecial(4):   per_damage *= 2          # 2连击
    if hasSpecial(5):   per_damage *= 3          # 3连击
    if hasSpecial(6):   per_damage *= (enemy.n or 4)  # n连击；redSwordsman n=8

    # 5. 反击伤害（每轮）
    counter_damage = 0
    if hasSpecial(8):                            # 反击
        counter_damage = floor((enemy.atkValue or 0.1) * hero_atk)

    # 6. 先手 / 破甲 / 净化
    if hasSpecial(1):   init_damage += per_damage          # 先攻：多挨一轮
    if hasSpecial(7):   init_damage += floor((enemy.defValue or 0.9) * hero_def)  # 破甲
    if hasSpecial(9):   init_damage += floor((enemy.n or 3) * hero_mdef)          # 净化

    # 7. 能否击杀
    hero_per_damage = max(0, hero_atk - mon_def)
    if hero_per_damage == 0:
        return None  # 无法击杀

    # 8. 回合数（含守卫系统）
    turn = ceil(mon_hp / hero_per_damage)
    turn += getFlag('__extraTurn__', 0)          # 守卫系统额外回合

    # 9. 总伤害
    damage = init_damage + (turn - 1) * per_damage + turn * counter_damage
    damage -= hero_mdef                          # 魔防一次性减免
    if not flag_enableNegativeDamage:
        damage = max(0, damage)

    # 10. 附加
    if hasSpecial(17): damage += getFlag('hatred', 0)  # 仇恨：积累的仇恨值
    if hasSpecial(22): damage += enemy.damage or 0     # 固伤

    return {mon_hp, mon_atk, mon_def, init_damage, per_damage,
            hero_per_damage, turn, damage}
```

**标志**：
- `flag_enableNegativeDamage = false`（不允许负伤害，data.js 确认）
- `flag_betweenAttackMax = false`（夹击伤害不取 min，data.js 确认）

### A.5 引擎预言机验证表

英雄属性：ATK=100, DEF=50, HP=10000, mdef=0（除第一组）

| 怪物 ID | 属性（HP/ATK/DEF）| specials | init | per | hero_per | turn | 引擎 damage | 公式 damage | 一致 |
|---------|-------------------|----------|------|-----|----------|------|-------------|-------------|------|
| greenSlime | 35/18/1 | 0 | 0 | 8 | 14 | 3 | 16 | (3-1)×8=**16** | ✓ |
| bat | 35/38/3 | 0 | 0 | 28 | 12 | 3 | 56 | (3-1)×28=**56** | ✓ |
| skeletonSoldier | 55/52/12 | 0 | 0 | 42 | 3 | 19 | 756 | (19-1)×42=**756** | ✓ |
| skeleton | 50/42/6 | 0 | 0 | 32 | 9 | 6 | 160 | (6-1)×32=**160** | ✓ |
| vampire | 444/199/66 | 0 | — | — | 0 | — | null | null（不可击）| ✓ |
| evilBat | 1000/1/0 | [2,3] | 0 | 1 | 1 | 1000 | 999 | (1000-1)×1=**999** | ✓ |
| redSwordsman | 100/120/0 | 6(n=8) | 0 | 560 | 100 | 1 | 0 | (1-1)×560=**0** | ✓ |
| blueKnight | 100/120/0 | 8 | 0 | 70 | 100 | 1 | 10 | 0+1×10=**10** | ✓ |

注：前4组英雄属性为 ATK=15, DEF=10, HP=1000, mdef=0。

*evilBat 特殊验证*：special[2]（魔攻）→ per=mon_atk=1；special[3]（坚固）→ mon_def=hero_atk-1=99 → hero_per=1；turn=1000。  
*redSwordsman 特殊验证*：per=max(0,120-50)=70；n=8 → per×=8=560；turn=1；damage=(1-1)×560=0（一刀秒杀，无损）。  
*blueKnight 特殊验证*：counter=floor(0.1×100)=10；turn=1；damage=(1-1)×70+1×10=10。

---

## B. 属性值与比率

### B.1 基础值（data.js `values` 字段，引擎已验证）

```javascript
lavaDamage:    100   // 每步血网/熔岩地形伤害
poisonDamage:   10   // 中毒状态每步 HP 损失（精确值待实现确认）
weakValue:      20   // 衰弱状态 ATK 和 DEF 减少量
redGem:          1   // 红宝石基础 ATK（× ratio）
blueGem:         1   // 蓝宝石基础 DEF（× ratio）
greenGem:        5   // 绿宝石基础 mdef（× ratio）
redPotion:      50   // 红血瓶基础 HP（× ratio）
bluePotion:    200   // 蓝血瓶基础 HP（× ratio）
yellowPotion:  500   // 黄血瓶基础 HP（× ratio）
greenPotion:   800   // 绿血瓶基础 HP（× ratio）
breakArmor:    0.9   // 破甲（special 7）系数：init += floor(0.9 × hero_def)
counterAttack: 0.1   // 反击（special 8）默认系数：counter += floor(0.1 × hero_atk)
purify:          3   // 净化（special 9）系数：init += floor(3 × hero_mdef)
hatred:          2   // 仇恨每次击杀积累的仇恨值（special 17 用）
```

### B.2 比率（ratio）规则

从游戏所有楼层的 `core.floors[floorId].ratio` 提取：

| 楼层范围 | ratio |
|----------|-------|
| MT0（大厅）| 0 |
| MT1–MT10 | 1 |
| MT11–MT20 | 2 |
| MT21–MT30 | 3 |
| MT31–MT40 | 4 |
| MT41–MT50 | 5 |

**道具拾取 vs 背包使用的区别（来源：items.js + 引擎预言机验证）**：

| 触发方式 | 字段 | 公式 |
|----------|------|------|
| 踩格拾取 | `item.itemEffect` | `gain = base_value × thisMap.ratio` |
| 背包手动使用 | `item.useItemEffect` | `gain = base_value`（无缩放） |

引擎通过 `core.items.getItemEffect()` eval `item.itemEffect`；背包使用 eval `item.useItemEffect`。

**道具拾取公式预言机验证表**（eval `itemEffect` 直接验证，非 getItemEffect）：

| ratio | redGem ATK | blueGem DEF | greenGem MDEF | redPotion HP | bluePotion HP |
|-------|-----------|------------|--------------|-------------|--------------|
| 1 (MT1–10)  | +1 | +1 | +5  | +50  | +200  |
| 2 (MT11–20) | +2 | +2 | +10 | +100 | +400  |
| 3 (MT21–30) | +3 | +3 | +15 | +150 | +600  |
| 4 (MT31–40) | +4 | +4 | +20 | +200 | +800  |
| 5 (MT41–50) | +5 | +5 | +25 | +250 | +1000 |

同理：yellowPotion HP += 500×ratio；greenPotion HP += 800×ratio。

### B.3 超级药水（superPotion，道具 ID = "superPotion"，tile ID = 56）

来源：items.js `superPotion.use` 字段：
```javascript
HP += round(0.74 * (atk + def)) * 10
```

### B.4 道具识别（tile ID → item ID，blocksInfo 完整提取）

路由相关道具（`I<n>:` token 含义）：

| Tile ID | Item ID | 说明 |
|---------|---------|------|
| 48 | icePickaxe | 冰镐，打开面前方格的门 |
| 49 | bomb | 炸弹，消灭周围≤500血目标 |
| 50 | centerFly | 中心飞行器，瞬移到地图对称位置 |
| 51 | upFly | 上飞行器，飞到上一层 |
| 52 | downFly | 下飞行器，飞到下一层 |
| 55 | cross | 十字架（被动），对不死/吸血鬼双倍攻击，可击杀无敌怪 |
| 56 | superPotion | 超级药水 |
| 57 | earthquake | 地震卷，消灭所有可破震目标 |
| 58 | poisonWine | 解毒酒，清除中毒状态 |
| 59 | weakWine | 解弱酒，清除衰弱状态 |
| 60 | curseWine | 解咒酒，清除诅咒状态 |

注：cross 和 amulet 均无 `useItemEffect`（被动道具，无主动使用效果）。  
注：keys（21-26）、gems（27-30）、potions（31-34）、equipment（35-44）拾取时自动入库，无需 I token。

### B.5 升级系统（击杀计数）

来源：data.js `levelUp` 字段：

| 击杀数 | 效果 |
|--------|------|
| 20 | ATK +10, DEF +10 |
| 40 | 提示"恭喜升级"（无属性加成） |

---

## C. 地形 / 区域伤害

### C.1 地形（来自 updateCheckBlock）

每步触发，不需要战斗：

| 触发条件 | 伤害 | 免疫条件 |
|----------|------|----------|
| 踩血网格（lavaNet）| `values.lavaDamage` = 100 | 持有护身符（amulet） |

### C.2 领域伤害（special 15）

触发时机：玩家站在怪物周围格。伤害预存在 `core.status.checkBlock.damage[loc]`，踩格时扣血。

```
range = enemy.range or 1
shape = 菱形（曼哈顿距离 ≤ range），若 enemy.zoneSquare=true 则方形
受影响格：以怪物为中心，range 范围内所有格（不含怪物本格）
damage[loc] += enemy.value
免疫：flag:no_zone = true 或 flag:魔法免疫 = true
```

### C.3 阻击（special 18）

踩进阻击怪物正交相邻格时触发，并可能被推退：

```
scan_dirs = 正交4方向（若 enemy.zoneSquare=true 则8方向）
damage[loc] += enemy.value（进入相邻格时扣血）
同时有 repulse 效果（击退至空格）
免疫：flag:no_repulse = true 或 flag:魔法免疫 = true
```

**后退（repulse）方向与阻挡（玩家实测，2026-06-04 坐实补全）：**
- **被击退的是「怪」**（不是勇者）：勇者踩进阻击怪正交相邻格 → 受 value 伤 → **该怪后退一格**。
- **方向 = 远离勇者**：怪沿 `(怪 − 勇者)` 单位向量再走一格（= 勇者来向的反方向；勇者在怪某侧出现，怪朝对侧退）。
- **阻挡则不退**：目标格被 **墙 / noPass / 门 / 楼梯 / 任何实体（道具·怪·NPC） / 越界** 占用 → 怪原地不动。
- ⚠ **games51 全 50 层数据中无任何 special[18] 怪物**（redWizardRepulse / skeletonPriest / steelGuard 均未在任何 floor 出现）。故本后退分支在 games51 **永不触发**，方向规则按实测落盘但未经 games51 oracle 校验；泛化到含阻击怪的塔时需逐字回引擎 `_sysEvents` 校验。

### C.4 夹击（special 16）

玩家处于两个相同 special 16 怪物之间时触发（横向或纵向）：

```
两怪物 ID 必须相同（getFaceDownId 相同）
damage = floor((hero_hp - current_damage) / 2)
若 flags.betweenAttackMax = true：damage = min(floor(hp/2), fight1, fight2)
（本游戏 betweenAttackMax = false，即取 floor(hp/2)）
免疫：flag:no_betweenAttack = true 或 flag:魔法免疫 = true
```

### C.5 激光（special 24）

怪物所在整行 + 整列均为危险格：

```
damage[整行每格] += enemy.value
damage[整列每格] += enemy.value
（怪物本格不加）
免疫：flag:no_laser = true 或 flag:魔法免疫 = true
```

### C.6 伏击（special 27）

不扣血，但触发捕捉效果（ambush），详细行为待确认。

### C.7 区域伤 sim 实现（`_apply_zone_damage`）+ games51 适用范围

> 落盘日期 2026-06-04。来源：§C.2/C.3/C.4（引擎 checkBlock）+ monsters.json special 编号 + 玩家实测。实现于 `sim/simulator.py`，**数据驱动**（special 编号/value/range/zoneSquare 全读 monsters.json，不认具体怪），过 68 测试 + 26 检查点零回归。

- **结算时机**：英雄**走到（per-arrival）**某格后立即结算该格所受区域伤。接入英雄"走入新格"的全部落点：普通走入 / 拾取后走入 / 禁用NPC通过 / **战斗后落怪格**（杀怪后站怪格，受相邻存活怪的区域伤）。`MOVE:`（moveDirectly 直跳）暂不沿途结算区域伤（仅 poison 按曼哈顿步数），待撞到再补。
- **叠加顺序**：①领域(15)按 `菱形/方形 ≤range` 命中累加 `value`；②阻击(18)按 `正交相邻(距1)` 命中累加 `value` → 合为 `acc`；③夹击(16)在 `acc` 之上对剩余血减半 `floor((hp−acc)/2)`（`betweenAttackMax=false`，不取 min）。即最终 `hp ← ceil((hp−acc)/2)`（当被夹击时）。
- **半血取整 = floor**（§C.4：`floor((hp−acc)/2)`）。
- **免疫**：`flag:魔法免疫` 全免；或各机制 `flag:no_zone / no_repulse / no_betweenAttack`。本路线 **token4527 拾神圣盾 shield5 置 `flag:魔法免疫=true`**（见 §C.8）→ 此后所有区域伤全免；**持盾前**（tok4527 前）经过的区域伤格全额生效。两段均被 46 检查点验证吻合。
- **致死走 §M.8**：区域伤致 `hp≤0` → 置 `state.dead` 冻结，**不再后退怪、不触发本格事件**（`_fire_events` 入口加 dead 守卫）。
- **games51 实际触发范围**：仅 **领域**（brownWizard 219 value100 / redWizard 220 value200，range1 菱形=正交4格）与 **夹击**（whiteKing 246），且只出现于 **MT41–MT49**。MT1–MT40 无任何区域怪 → 实现对前 40 层为 no-op（token4141 MT41 仍稳 262，证路线避开了 zone 格）。
### C.8 神圣盾 = `flag:魔法免疫` → 区域伤全免（G5/G6/J13 已解决，玩家裁定 2026-06-05）

> 坐实来源：引擎 items.js（itemEffect 字面量）+ updateCheckBlock 源码 + MT44.json + common_events.js。已实现+单测 `tests/test_holy_shield.py`（6 测全过），过 46 检查点零回归。

- **道具**：神圣盾 = `shield5` = tile 44，唯一在 **MT44(6,6)**。MT44 是异空间隐藏层（`isHide`，靠 upFly/downFly 进）；拿法 = 杀 (5,9)(7,9) 两个 redGuard → 第二只 `afterBattle` `openDoor(6,8)` 开特殊门 → 进中心拾取（common_events.js 备忘录 case44/45 印证"神圣盾藏在异空间楼层"）。
- **itemEffect（引擎原文）**：`hero.def += 100; setFlag('nowShield','shield5'); setFlag('魔法免疫', true)`。注：`equip.value.mdef=100` 仅装备模式给，**itemEffect 不加 mdef**（本塔按 itemEffect 拾取，故只 +def100，对齐 checkpoint 4528 DEF 204→304）。
- **免疫范围（updateCheckBlock 源码）**：`flag:魔法免疫` 一律置 0 于 **领域15 / 夹击16 / 阻击18 / 激光24 / 伏击27** 全部区域伤。即神圣盾 = 区域伤（魔法攻击）全免。
- **本塔"地形伤"澄清（重要）**：本塔唯一"踩格扣血"= 巫师领域/夹击，神圣盾正免之。**血网（lavaNet）是另一套**免疫（`hasItem('amulet')` 护符），**全塔无 lavaNet 地形、无 amulet → 该机制空置**。`lava`(tile5) 是 noPass 障碍（MT13/MT26），不扣血，由 snow 清除（§K）。tiles.json tile5 旧 `_terrain_damage` 注释（lavaDamage/amulet）已订正为误导残留。
- **sim 实现（已就绪，数据驱动）**：拾取走 `_apply_item_effect` "stat" 分支 `set_flags`（simulator.py:1242）→ def+100 + 魔法免疫；免疫走 `_apply_zone_damage` 入口 `if fl.get("魔法免疫"): return`（simulator.py:930）。**无需为本机制改产品代码**。
- **本路线覆盖度**：token4527（移动 U 进 MT44(6,6)）拾取。持盾后路线**大量**经过区域伤格（MT41/42/43/45/46/47/48/49 巫师领域+夹击，几十处），全因免疫吃 0 伤——被 checkpoint 4582/4723/5378/5833/6066… 全 PASS **重度隐性验证**（非"无真值"）。

---

## D. 商店 / 祭坛

### D.1 系统架构

商店通过 NPC 事件实现，不使用标准 h5mota shop 系统（`core.status.shops` 在本游戏为空）。

### D.2 祭坛公共事件（"商店"，来源：project.min.js）

祭坛 NPC 事件先设 `flag:ratio = <本区ratio值>`，再调用公共事件 `insert:"商店"`。

公共事件 "商店" 结构（while 循环，选"离开"才退出）：

```javascript
// 每轮重算本次费用
flag:money1 = 20 + 10 * (flag:times1 + 1) * flag:times1

// 三个购买选项（均需 status:money >= flag:money1）
HP  +100*(flag:times1+1)  →  status:hp  += 100*(times1+1);  status:money -= money1;  times1 += 1
ATK +2*flag:ratio         →  status:atk += 2*ratio;         status:money -= money1;  times1 += 1
DEF +4*flag:ratio         →  status:def += 4*ratio;         status:money -= money1;  times1 += 1
// 第四个选项：离开（break）
```

**关键变量**：
- `flag:times1`：全局购买总次数（HP/ATK/DEF/任意楼层累计），初始=0
- `flag:ratio`：进入祭坛时设置，等于本层 `thisMap.ratio`

**累计追踪 flag**（用于排行榜）：
- `${r}区购买hp/atk/def`：各区累计属性增益
- `${r}区购买hp/atk/def次数`：各区购买次数

### D.3 祭坛位置与收益表（来源：floors.min.js，全部已确认）

| 楼层 | 坐标 | flag:ratio | ATK/次 | DEF/次 |
|------|------|------------|--------|--------|
| MT4  | (6,1) | 1 | +2 | +4 |
| MT12 | (6,9) | 2 | +4 | +8 |
| **无** | — | **3（MT21-30 无祭坛）** | — | — |
| MT32 | (10,10) | 4 | +8 | +16 |
| MT46 | (6,1) | 5 | +10 | +20 |

HP收益（全部祭坛相同）：第 n 次购买（n 从1起）= `100 × n` HP。  
金币消耗：第 n 次购买 = `20 + 10 × n × (n-1)` 金币（times1 = n-1 时）。

购买序列示例（times1 从0起）：

| 购买次 | times1 | 费用 | HP获得 |
|--------|--------|------|--------|
| 1 | 0 | 20 | 100 |
| 2 | 1 | 40 | 200 |
| 3 | 2 | 80 | 300 |
| 4 | 3 | 140 | 400 |
| 5 | 4 | 220 | 500 |

### D.4 钥匙回收商店（公共事件 "回收钥匙商店"，来源：events.js）

| 出售物品 | 获得金币 |
|----------|----------|
| 黄钥匙 × 1 | 10 |
| 蓝钥匙 × 1 | 50 |

追踪：`flag:黄钥匙出售次数`。  
进入条件：需先与该 NPC 接触（`isShopVisited` 为 true 后可通过快捷键重复使用）。

---

## E. 路由 Token 格式

### E.1 编码层（.h5route 文件）

```
外层：LZString.decompressFromBase64(file_content) → JSON
JSON 字段：{name, version, hard, seed, route}
内层：LZString.decompressFromBase64(json.route) → RLE 动作字符串
```

### E.2 RLE 动作字符串 Token 完整对照表

来源：`core.utils.encodeRoute` / `decodeRoute` / `_encodeRoute_encodeOne` / `_decodeRoute_decodeOne` 源码。

| 编码格式 | 解码动作 | 说明 |
|----------|----------|------|
| `U[n]` `D[n]` `L[n]` `R[n]` | 移动 n 步（n 省略=1） | up/down/left/right |
| `C<n>` | `choices:<n>` | 对话选项，0-indexed；本游戏路由共 65 处 |
| `c` | `choices:none` | 取消选择 |
| `FMT<n>:` | `fly:MT<n>` | 楼层传送（正常上下楼也用此 token） |
| `I<n>:` | `item:<number2id(n)>` | 使用道具（n = tile ID） |
| `S<shopId>:` | `shop:<shopId>` | 进入商店（本游戏路由中无此 token） |
| `K<n>` | `key:<n>` | 按键，n 为 ASCII 码；本游戏：49='1', 50='2', 52='4' |
| `(help)` | `help` | 打开游戏说明菜单（触发"游戏说明"公共事件） |
| `M<x>:<y>` | `move:<x>:<y>` | 直接跳转到坐标 |
| `T` | `turn` | 转身 |
| `t<D>:` | `turn:<dir>` | 转向特定方向 |
| `G` | `getNext` | 触发前方格子 |
| `p` | `input:none` | 输入框取消 |
| `P<x>` | `input:<x>` | 输入框输入 x |
| `Q<x>:` | `input2:<x>` | 输入框输入 x（另一类型） |
| `N` | `no` | 否 |
| `u<x>` | `unEquip:<x>` | 卸下装备 |
| `e<n>:` | `equip:<number2id(n)>` | 装备道具 |
| `s<x>` | `saveEquip:<x>` | 保存装备方案 |
| `l<x>` | `loadEquip:<x>` | 加载装备方案 |
| `X<n>` | `random:<n>` | 随机数选择 |

### E.3 本游戏存档元数据

来源：`51_20260529133740.h5route` 解码：

```json
{"name": "51", "version": "Ver 3.0", "hard": "", "seed": 1722097160}
```

- `hard = ""`：未开启 hard 模式（空字符串=关闭）
- `seed`：随机数种子，1722097160。用途：游戏中随机事件的确定性复现
- 路由总长：5188 字符原始，6235 个动作（含展开后的移动步）
- `help` token：2 次（打开游戏说明）
- `key` token：3 次（按键 '1'、'2'、'4'，均在 MT37-MT48 区域）

### E.4 选项索引确认（C token 0-indexed）

用户确认：`CHOICE:1` = 选第二个选项（即 C[0] = 选项0，C[1] = 选项1）。

---

## F. 后战斗状态效果

来源：`core.events.eventdata.afterBattle` 和 `core.control.controldata.triggerDebuff`（从运行中引擎通过 `toString()` 提取）。

| Special | 名称 | afterBattle 处理 | 效果 |
|---------|------|-----------------|------|
| 12 | 中毒 | `triggerDebuff("get","poison")` | `flag.poison = true`；每步损失 `values.poisonDamage`(=10) HP |
| 13 | 衰弱 | `triggerDebuff("get","weak")` | `flag.weak = true`；`ATK -= 20`，`DEF -= 20`（`values.weakValue`=20） |
| 14 | 诅咒 | `triggerDebuff("get","curse")` | `flag.curse = true`；无即时属性改变；后续战斗金币和经验归零 |
| 19 | 自爆 | `hero.hp = 1` | 战斗存活后英雄 HP 直接设为 1（无论当前 HP 多少） |

注：效果仅在英雄存活（HP > damage）时触发。多个 special 可叠加（如同时有 12+13）。

---

## G. MT10 第十层埋伏机制

**来源：** `core.maps['MT10']`（live engine）源码 + `51_20260529133740.h5route` 路线实测  
**验证时间：** 2026-05-30

### G.1 机制概述

MT10 的关键机关是位于 (6,3) 的一道 `specialDoor`（机关门，tile 85）。该门由事件动态设置，并由 `autoEvent` 在所有埋伏敌人被消灭后自动解开。

**勇者不可能绕过 (6,3)**：从 (6,5) 到 boss 位置 (6,1) 的唯一通道就是 (6,3)，路线存档证实勇者确实经过该格（Visit 4 第 43 步）。

### G.2 完整机制链（来源：route 实测 + 源码验证）

| 步骤 | 触发条件 | 发生事件 | 地图状态变化 |
|------|----------|----------|-------------|
| 1 | Visit 4 开始（从 MT1 fly 到 MT10） | 落点 (1,10)（`downFloor=[1,10]`） | 无 |
| 2 | 第 1–20 步：移动 | 从 (1,10) 经左列→下行走廊→中央列 | 无 |
| 3 | 第 21 步：踩 (6,5) | `events["6,5"]` 触发（一次性，thereafter removed） | ① 关 (6,7) 门；② 开 (4,4)(8,4)(5,6)(7,6)；③ tile17 清除：(5,4)(6,3)(7,4)(5,5)(7,5)；④ 队长 (6,4)→up:3→(6,1)；⑤ 8只骷髅就位（见§G.3）；⑥ 关 (4,4)(8,4)；⑦ **closeDoor specialDoor at (6,3)**；⑧ `flag:10f机关=true` |
| 4 | 步骤 22–42（21步） | 勇者击杀全部 8 只骷髅 | 8个位置逐一变 null |
| 5 | 全部 8 只死亡后 | `autoEvent["6,3"]` 条件满足 → **openDoor at (6,3)** → (6,3) 变地板 | (6,3) 可通行 |
| 6 | 第 43 步 | 勇者经过 (6,3) | — |
| 7 | 第 44–45 步 | 勇者经过 (6,2) → 踩 (6,1) 与队长决战 | — |
| 8 | token 45：afterBattle["6,1"]（**无条件**，不经 if 判断） | 物品奖励出现（gem/potion/key）；openDoor(4,4)(6,7)(8,4)；setBlock 0→(6,9) 清除红门；show([6,9]/[6,11])（引擎显示NPC+楼梯，模拟器当前 no-op）；setValue flag:10f战胜骷髅队长=true | (6,9) 红门消失，三扇门开 |
| 8b | token 45：events["6,1"]（afterBattle 之后触发） | condition flag:10f机关=True → **true branch（空）→ 无操作** | — |
| 9 | token 80（local[79]）：英雄踩 (6,9) | events["6,9"] 触发（拦截型）；generateMove 同步执行 → 小偷按脚本 steps 移动到 **(6,10)**（keep=true，entities[10][6]=123）；对话暂停，勇者锁在 (6,9) | 小偷在 (6,10)，(6,11) 此时为空 |
| 9b | tokens 81–102（local[80-101]）×22 | 22 UDLR 废弃输入；勇者始终在 (6,9)；小偷保持 (6,10) 不动 | — |
| 10 | token 103（local[102]）：CHOICE:1 | **第1个 CHOICE 关闭对话**；剩余指令同步执行：move(6,10)→(6,11) 无 keep → 小偷从 entities[10][6] 清除，(6,11) 不放置；hide 压制 events["6,9"]；**小偷完全消失** | (6,11) 可通行 |
| 10b | tokens 104–106（local[103-105]）：CHOICE:1/1/3 | 事件已结束，3个 CHOICE 均为 no-op | — |
| 11 | token 107（local[106]）：D | 勇者自由移动：(6,9)→(6,10) | — |
| 12 | token 108（local[107]）：D | 勇者踏上 (6,11)；changeFloor["6,11"] 触发→MT11；模拟器设 _exited=True | 本层退出 |
| 12b | tokens 109–148（local[108-147]）×40 | 全部 no-op（changeFloor 冻结）；对应真实游戏切层动画期间玩家按键 | — |
| — | global_idx 1317（local[147]+1）：FLOOR:MT11 | h5mota 引擎记录到达 MT11 | — |

### G.3 埋伏敌人最终就位坐标

`events["6,5"]` 执行后 8 只敌人的最终位置（均来自 move/generateMove 指令精确计算）：

| 坐标 | 敌人 | 原始位置 | 移动路径 |
|------|------|----------|----------|
| (6,4) | skeletonSoldier | (10,4) | left:4 |
| (5,4) | skeleton | (1,3) | down:1→right:4 |
| (7,4) | skeleton | (11,3) | down:1→left:4 |
| (5,5) | skeleton | (2,3) | down:1→right:3→down:1 |
| (7,5) | skeleton | (10,3) | down:1→left:3→down:1 |
| (5,6) | skeleton | (3,3) | down:1→right:2→down:2 |
| (6,6) | skeletonSoldier | (2,4) | right:3→down:2→right:1 |
| (7,6) | skeleton | (9,3) | down:1→left:2→down:2 |

### G.4 autoEvent 完整规格

```json
"autoEvent": {
  "6,3": {
    "0": {
      "condition": "flag:10f机关 && core.getBlockId(5,4) === null && core.getBlockId(6,4) === null && core.getBlockId(7,4) === null && core.getBlockId(5,5) === null && core.getBlockId(7,5) === null && core.getBlockId(5,6) === null && core.getBlockId(6,6) === null && core.getBlockId(7,6) === null",
      "currentFloor": true,
      "priority": 0,
      "delayExecute": false,
      "multiExecute": false,
      "data": [{"type": "openDoor"}]
    },
    "1": null
  }
}
```

触发逻辑：每步（`checkAutoEvent`）遍历所有 autoEvent 条目；条件为真且 `multiExecute=false` 时执行一次 `openDoor`（无 `loc` 参数 → 默认开当前 autoEvent 键所在格，即 (6,3)）。

### G.5 (6,3) 状态时间线

| 阶段 | (6,3) 的 tile | 可通行？ |
|------|--------------|---------|
| 初始地图（进入 MT10 时） | tile 17（`_unknown_visual`） | ✓ 可通行 |
| events["6,5"] 中 setBlock 0 | 0（地板） | ✓ 可通行 |
| events["6,5"] 中 closeDoor | 85（specialDoor） | **✗ 不可通行** |
| autoEvent 条件满足后 openDoor | 0（地板） | ✓ 可通行 |

**结论（route 实测确认）**：勇者的确经过 (6,3)（Visit 4 第 43 步），但这是在 8 只敌人被消灭、autoEvent 开门之后——而非"(6,3) 一直是地板"。

### G.6 模拟器建模要点

1. **动态地图必须**：`events["6,5"]` 触发后地图发生大量状态变化，不能用静态地图模拟 MT10。
2. **autoEvent 检测**：每步移动后运行 `check_auto_events(state)` —— 若 `flag:10f机关=true` 且 (5,4)(6,4)(7,4)(5,5)(7,5)(5,6)(6,6)(7,6) 均无敌人，则 openDoor(6,3)。
3. **顺序约束**：必须先杀全部 8 只才能通过 (6,3)；在此之前 (6,3) = specialDoor = 不可通行。
4. **afterBattle["6,1"] 不含 openDoor(6,3)**：(6,3) 完全由 autoEvent 负责，不是打 boss 的奖励。
5. **`move` keep 语义（已修复）**：引擎中 `move`/`generateMove` 若无 `keep:true`，实体在动画结束后消失，不放置于目标格。模拟器已实现：`if instr.get("keep") is True` 才在目标格放置实体，否则仅清除源格（小偷 move 步骤正确消失，(6,11) 不残留）。
6. **afterBattle vs events 的层次**：`flag:10f战胜骷髅队长` 由 afterBattle["6,1"] 设置（无条件），不在 events["6,1"] 的 false branch。events["6,1"] 在 Visit 4 时取 true branch（空），不执行任何操作。

### G.7 小偷离场与出口机制（events["6,9"]）

**来源：** MT10.json `events["6,9"]` 完整脚本 + `afterBattle["6,1"]` 源码 + trajectory diag（route token 实测）

#### G.7.1 出口楼梯 (6,11) 的启用方式

- `terrain[11][6] = 87`（upFloor stair 块）：**永久不阻挡**（noPass=False）
- `events["6,11"]`：`{enable:false, data:[]}`——初始禁用但 data 为空，enable/disable 不影响英雄能否踩上去
- `afterBattle["6,1"]` 中 `show([6,11])`：引擎会将 enable 改为 true；模拟器当前 no-op，但因 data 为空，对通行性无影响
- **结论**：terrain 87 本身就可通行，(6,11) 的唯一阻碍是实体层（小偷）

#### G.7.2 小偷事件完整脚本（events["6,9"] true branch，条件 flag:10f战胜骷髅队长）

```json
[
  {"type":"generateMove","loc":[1,11],"id":"thief","time":500,"keep":true,
   "steps":["up:3","right:2","down:3","right:2","up:1","right:1"]},
  "\t[小偷,thief]嘿！...",
  {"type":"move","loc":[6,10],"time":200,"steps":["down:1"]},
  {"type":"hide","remove":true,"time":0}
]
```

步骤解析：

| 步骤 | 指令 | 起点 | 路径 | 终点 | keep | 结果 |
|------|------|------|------|------|------|------|
| 1 | generateMove（同步） | (1,11) | up:3→right:2→down:3→right:2→up:1→right:1 | **(6,10)** | true | entities[10][6]=123；小偷驻留 (6,10) 直至对话结束 |
| 2 | 对话 | — | — | — | — | 拦截型；第1个 CHOICE（token[102]）关闭；余3个 CHOICE 为 no-op |
| 3 | move（同步，无 keep） | (6,10) | down:1 | (6,11) | 未指定 | entities[10][6]清零；(6,11) **不放置**（keep fix）；小偷完全消失 |
| 4 | hide remove=true | — | — | — | — | 压制 events["6,9"] |

#### G.7.3 已验证时间线（route 事实 + 模拟器实测）

> ⚠️ **已过时（2026-06-04），以 §M 和当前实现为准。** 本节下方表格（token[80-101] 「intercepting=True」、token[102] 「CHOICE:1 推进对话」）及结论 568 行 ② 描述的「同步 move/generateMove 后对话→需 CHOICE 拦截推进」时间线，**当年系据已删除的 `had_sync_anim` 推断规则写成，与现状不符**。源码坐实：纯文字对话 `\t[name]text` 在回放中一律**不拦截、不消费 token**（引擎 replayActions 无文字处理器，仅 choices 读取选择 token）；MT10 小偷事件自 f28ceab 起靠 move+hide 独立成立、不依赖此拦截。该死规则已于 commit 50af961 删除（全塔扫描仅误伤 MT32 boss 演出，见 `extract/scan_sync_dialog.py`）。下方原文仅作历史留存。

| token（local/0-indexed）| global_idx | 事件 | entities[10][6] | entities[11][6] | _exited |
|------------------------|-----------|------|----------------|----------------|---------|
| [79] D 踩 (6,9) | 1248 | generateMove 同步执行，对话暂停 | 123（小偷） | 0 | False |
| [80-101] UDLR×22 | 1249-1270 | 废弃输入，intercepting=True | 123 | 0 | False |
| [102] CHOICE:1 | 1271 | 对话关闭，move+hide 执行，小偷消失 | **0** | **0** | False |
| [103-105] CHOICE×3 | 1272-1274 | no-op | 0 | 0 | False |
| [106] D | 1275 | hero (6,9)→(6,10) | 0 | 0 | False |
| [107] D | **1276** | hero (6,10)→**(6,11)**，changeFloor，_exited=True | 0 | 0 | **True** |
| [108-147] ×40 | 1277-1316 | 全部 no-op（切层动画） | 0 | 0 | True |
| — | **1317** | **FLOOR:MT11**（紧跟 token[147]） | — | — | — |

**结论**：token[107]（global 1276）是英雄踏上 (6,11) 的真实时刻；token[108-147] 是切层动画期间的按键，changeFloor 冻结正确模拟此行为，非凑绿。小偷全程在 (6,10)，从未在 (6,11) 驻留。

**已修复**：① `move` keep 语义（keep 非 True 则不放置实体）；② 拦截型事件（同步 generateMove 前置→对话需 CHOICE 推进）；③ changeFloor 出口冻结（_exited=True 后所有 token 为 no-op）。

---

## H. MT3 第三层伏击重置事件

**来源：** `core.floors['MT3'].events["5,9"]`（live engine 源码）+ `51_*.h5route` 路线实测  
**验证时间：** 2026-05-31

### H.1 事件概述

MT3 坐标 (5,9) 有一次性触发的"伏击"事件。触发后：直接赋值重置英雄基础属性、卸下装备、移除魔法免疫，强制传送回 MT2 (3,8)。

### H.2 完整事件脚本（来源：MT3.json events["5,9"]）

触发条件：**无条件**（hero 踩格即触发，无 flag 检查）  
一次性：脚本末尾 `hide loc=[5,9] remove=true` 将触发格本身变为空地板，永不再触发。  
CHOICE token 消耗：5 个（演出对话 ×2 + 苏醒对话 ×3）。

关键指令顺序：

| 指令 | 参数 | 游戏效果 |
|------|------|---------|
| setValue | flag:03 = 1 | 伏击已触发标志 |
| setBlock | redKing at (5,7) | 演出：魔王出现 |
| 对话 | `[魔王,redKing]欢迎来到魔塔…` | CHOICE×1 |
| setBlock | whiteKing at (5,8)(4,9)(6,9)(5,10) | 演出：白王包围 |
| 对话 | `[hero]什么？` | CHOICE×1 |
| function + sleep + setCurtain | 旋转动画 + 黑屏演出（纯视觉）| 无属性变化 |
| **setValue** | **status:hp = "400"** | **HP 强制赋为 400** |
| **setValue** | **status:atk = "10"** | **ATK 强制赋为 10** |
| **setValue** | **status:def = "10"** | **DEF 强制赋为 10** |
| setValue | flag:nowWeapon = "null" | 卸下武器 |
| setValue | flag:nowShield = "null" | 卸下盾牌 |
| setValue | flag:魔法免疫 = "false" | 移除魔法免疫 |
| hide | loc=(5,7)(5,8)(4,9)(6,9)(5,10)**(5,9)**, remove=true | 清除演出实体及触发格 |
| **changeFloor** | **MT2, loc=(3,8), direction=down, time=0** | **强制传送到 MT2 (3,8)** |
| 对话 | `------` / `喂！` / `醒醒！` ×3 | CHOICE×3 |

赋值顺序说明：脚本先 setValue status:atk=10，再 setValue flag:nowWeapon="null"。用户确认触发后实际 ATK=10，与此顺序一致（nowWeapon 赋 null 不引发额外 ATK 减算，或初始武器本就未装备）。

### H.3 重置边界（规格确认）

| 属性/资源 | 重置？ | 细节 |
|-----------|--------|------|
| HP | **是** → 400 | setValue 直接赋值 |
| ATK | **是** → 10 | setValue 直接赋值 |
| DEF | **是** → 10 | setValue 直接赋值 |
| 武器/盾牌 flag | **是** → null | 脚本显式卸装；sword5/shield5 **永久失去**（见下） |
| flag:魔法免疫 | **是** → false | 脚本显式移除 |
| 背包道具 | **否** | 脚本无 items 操作 |
| 钥匙 | **否** | 脚本无 keys 操作 |
| 金币 | **否** | 脚本无 money 操作 |
| 已拾取宝石/药水的累计加成 | 已被清零 | 宝石加成已计入 status:atk/def，被 setValue=10 覆盖 |

**sword5/shield5 永久失去（重要）**：`core.firstData.hero.items = {fly:1}` — sword5 和 shield5 从未放入 items 字典，只以 `flag:nowWeapon/nowShield` 形式存在。伏击将这两个 flag 设为 null 后，两把装备从游戏状态中**彻底消失**，无法重装。伏击后 ATK=10/DEF=10 是永久基底，需靠宝石和商店累积重建。

### H.4 route 起始状态裁定（存档实际数据）

**外层 JSON 字段**：`name / version / hard / seed / route` 仅此五项，**无任何英雄状态**。  
→ route 重放初始化完全依赖 `core.firstData`。

**`core.firstData.hero`（hero_init.json 来源）**：
```
floor=MT1, loc=(6,11),  HP=1000, ATK=100, DEF=100, mdef=0
flags: {nowWeapon:"sword5", nowShield:"shield5", 魔法免疫:true}
items: {fly:1}      ← sword5/shield5 仅在 flag，不在 items
```

**MT1 `firstArrive`（MT1.json 直接证据）**：
- `choices "开启flash特性？"` + `choices "开启疯狂加血？"` ← 两个 `choices` 类型二选一对话
- route global[0-1] = CHOICE:1,CHOICE:1 = 两项均选"不开启"
- → route **从 MT1 游戏开始时刻启动**，firstArrive 立即触发

**route 走位模拟（前55步）**：
- global[2]=L → MT1(5,11) ✓；global[4]=U → MT1(5,10) = yellowKey 拾取 ✓  
- global[55]=L → **MT1(1,1) = upFloor → changeFloor to MT2**（第一次跨层）  
- global[56-64]=D×9 = MT2 上的跨层后废输入

→ **裁定 (b)：route 从 MT1 (6,11) 初始状态出发，包含伏击前全部 MT1-3 段落。**

### H.5 伏击触发状态与 CHOICE 缺失的解释

**伏击强制必经（MT3 地图验证）**：  
MT3 row 10 可通行格仅 (5,10)；从 (5,10) 向上唯一路径 = **(5,9) 伏击格**。无任何绕行路径。  
→ 首次遍历 MT3 必定触发伏击。

**CHOICE token 为何缺失（两类指令对比）**：

| 指令类型 | 示例 | route 是否录入 |
|----------|------|----------------|
| `choices` 类型（多选一） | MT1 firstArrive，祭坛 | **是** → CHOICE:n |
| `\t[name]text`（纯文本，非拦截） | MT3 伏击全部 5 条对话 | **否** → 无 token |
| `\t[name]text` + intercepting 机制 | MT10 小偷 | **是** → CHOICE:1（恢复冻结事件流，非对话本身） |

MT3 伏击 5 条对话均为 `\t[name]text` 格式，无 `choices` 索引，无 intercepting 机制。  
→ **伏击在初始 MT3 遍历中触发，但对话不产生 CHOICE token。route 中看不到痕迹不等于没触发。**

**CHOICE:0 at global[116] 的身份**：  
模拟显示英雄在跨层后（MT2 或 MT3 上），与某 NPC 进行 `choices` 类型互动（CHOICE:0 = 第一选项）。仅 1 个 CHOICE，与伏击（需 5 个 `\t-text` 对话，均无 CHOICE）无关。

**伏击后续**：changeFloor 将英雄传送至 MT2(3,8)，HP=400/ATK=10/DEF=10，route 从此继续，最终 FLOOR:MT4@g=186。

### H.6 优化含义（修正版）

- **伏击是强制必经，非可绕开陷阱**：(5,9) 是 MT3 唯一上行路径，初次遍历必触发。求解器基线 = 伏击后的 400/10/10。
- **sword5/shield5 永久失去**：两者不在 items 中，伏击 unequip 后无法重装。ATK=10/DEF=10 是不可逆的初始重置值，之后靠宝石和祭坛重建。
- **伏击前的 ATK/DEF 宝石加成全部清零**：setValue=10 覆盖所有前期 ATK/DEF 积累。**伏击前 ATK/DEF 宝石拾取无价值**；但 **钥匙和金币不被重置，伏击前积累的钥匙可在重回 MT1-2 时解锁资源**。
- **模拟器须建模此事件**：必须实现 (5,9) 触发的 setValue + changeFloor，否则伏击后所有战斗伤害计算错误。

---

## I. 飞行系统

**来源**：h5mota 引擎 `core.flyTo`、`core.plugin.floorTofloor`、`core.hasVisitedFloor`、各道具 `useItemEffect`（均通过浏览器 `toString()` 从运行中引擎取得）。

### I.1 三种飞行道具概览

| 道具 ID | 名称 | 触发方式 | 效果 | 路由 token |
|---------|------|----------|------|-----------|
| `fly` | 魔杖 | 物品栏使用 | 全塔楼层选择界面，调用 `core.flyTo(toId)` | `fly:MTn` |
| `centerFly` | 瞬移 | 物品栏使用（或快捷键 K51/键'3'） | 当前层对称格传送 | 无（不切层） |
| `upFly` | 上飞翼 | 物品栏使用（或快捷键 K52/键'4'） | 切至当前层 +1 层 | 无（含于 changeFloor 流程） |
| `downFly` | 下飞翼 | 同上 | 切至当前层 -1 层 | 无（含于 changeFloor 流程） |

**关键结论**：路由中所有 `fly:MTn` token 均由 fly魔杖调用 `core.flyTo` 产生。centerFly/upFly/downFly 不产生 `fly:MTn`，无法与 fly魔杖切层事件区分（route 重放时 fly: replay handler 必须持有 fly魔杖才能执行）。

---

### I.2 fly魔杖（item:fly）

`useItemEffect`（源码）：
```javascript
core.ui.drawFly(core.floorIds.indexOf(core.status.floorId));
```
打开楼层选择 UI。用户选定目标楼层后，UI 内部调用 `core.flyTo(toId)` 并将结果 `fly:toId` 压入路由。

**重放入口**（route replay handler）：
```javascript
if (action.indexOf("fly:") != 0) return false;
var floorId = action.substring(4);
if (!core.canUseItem("fly")) return false;  // 重放时必须持有 fly 道具
core.ui.drawFly(toIndex);
// → 内部调用 core.flyTo(floorId, core.replay)
```
结论：重放 `fly:MTn` token 时，模拟器须确认英雄持有 fly 道具，否则无效。

---

### I.3 核心函数：core.flyTo

#### I.3.1 条件检查顺序

```
gate 1 (仅当 flag:fly = false):
    floorTofloor(toId) 必须为 true
    → 楼梯路径连通性检查（见 §I.4.2）

gate 2 (始终):
    canFlyFrom[fromId] == true
    canFlyTo[toId]     == true
    hasVisitedFloor(toId) == true
    → 三者均满足才允许飞行
```

若任一 gate 失败，播放失败音效并显示提示，返回 `false`，路由不记录 token。

**flag:fly**：初始值为 `false`（需通过 gate1 的楼梯连通检查），特定事件可设为 `true`（解除连通要求）。具体触发条件见 §J（未确认项 J8）。

**gate1 玩家视角**（与玩家实测吻合）：fly魔杖**不要求站在楼梯旁**，只要当前楼层存在一条能到达楼梯格的无阻碍路径即可使用。精确判定（来源：`core.plugin.floorTofloor` + `core.plugin.canConnect`）：
- 对相邻±1层：`canConnect(英雄当前坐标, 本层楼梯格坐标, 当前层)`= BFS/DFS 可达性（受当前地图状态影响：门/活怪/墙）
- 对跨多层：递归检查每个中间层的上/下楼梯格之间是否连通
- 隐藏层（isHide=true）跳过连通检查，直接放行

#### I.3.2 落点规则（flyRecordPosition=false）

`flyRecordPosition=false`（此塔设置），英雄不记忆出发格，而是降落在目标层的楼梯坐标：

```
fromIndex = floorIds.indexOf(fromId)
toIndex   = floorIds.indexOf(toId)

if fromIndex ≤ toIndex:   # 向上飞（或同层）
    stair = "downFloor"   # 降落在目标层的"下楼梯"坐标
else:                      # 向下飞
    stair = "upFloor"     # 降落在目标层的"上楼梯"坐标
```

特殊：若目标层设有 `flyPoint` 字段，则降落在 `flyPoint` 坐标（优先于上述规则）。

#### I.3.3 路由 token

`core.status.route.push("fly:" + toId)`，toId 为 `"MT1"`–`"MT50"` 等楼层 ID。
编码进 .h5route 时显示为 `FMTn:`（见 §E）。

---

### I.4 可飞性条件

#### I.4.1 hasVisitedFloor 算法

```javascript
// 引擎实现（h5mota engine core.hasVisitedFloor）
function(floorId) {
  if (!core.hasFlag("__visited__")) core.setFlag("__visited__", {});
  if (core.status.maps[floorId].isHide) {
    return core.getFlag("__visited__")[floorId];  // 隐藏层：必须显式访问
  }
  // 非隐藏层：若 floorIds 数组中任意更高索引的楼层已访问，则视为"已访问"
  for (var i = core.floorIds.length - 1; i >= 0; i--) {
    if (floorId === core.floorIds[i]) return core.getFlag("__visited__")[floorId];
    if (core.getFlag("__visited__")[core.floorIds[i]]) return true;
  }
}
```

**推论**：
- 非隐藏楼层（isHide=false）：只要访问过任何比目标楼层编号更高的楼层，目标楼层自动视为"已访问"。即到达 MT30 后，MT1–MT29 均可作为 fly 目标。
- 隐藏楼层（isHide=true，本塔仅 MT44）：必须实际进入过才视为"已访问"。

**模拟器实现要点**：状态须维护 `visited_floors: set[str]`，每次 changeFloor 进入新楼层时加入该集合。

#### I.4.2 floorTofloor 楼梯连通性检查（gate 1）

当 `flag:fly=false` 时，飞行前检查从当前层到目标层的楼梯路径是否连通：

```
function floorTofloor(toId):
    fromIndex = indexOf(fromId)
    toIndex   = indexOf(toId)

    # 隐藏层直接放行
    if main.floors[toId].isHide: return true

    # 同层：检查 downFloor 格是否可直接移动到达
    if toId == fromId:
        return canMoveDirectly(downFloor[0], downFloor[1]) != -1

    # 相邻一层（差 1）：
    if abs(toIndex - fromIndex) == 1:
        if fromIndex in {0, 44}: return true   # 边界特例
        if toIndex > fromIndex:
            return canConnect(hero.x, hero.y, upFloor[0], upFloor[1], fromId)
        else:
            return canConnect(hero.x, hero.y, downFloor[0], downFloor[1], fromId)

    # 跨多层：递归检查中间层的上下楼梯是否连通
    if toIndex > fromIndex:
        prevFloorId = floorIds[toIndex - 1]
        if isHide[prevFloorId]: return floorTofloor(prevFloorId)  # 隐藏层跳过
        return canConnect(upFloor_prev[0], upFloor_prev[1],
                          downFloor_prev[0], downFloor_prev[1], prevFloorId) \
               and floorTofloor(prevFloorId)
    else:  # toIndex < fromIndex
        nextFloorId = floorIds[toIndex + 1]
        if isHide[nextFloorId]: return floorTofloor(nextFloorId)
        return canConnect(upFloor_next[0], upFloor_next[1],
                          downFloor_next[0], downFloor_next[1], nextFloorId) \
               and floorTofloor(nextFloorId)
```

`canConnect(x1,y1, x2,y2, floorId)` = BFS/DFS 同层可达性（考虑当前地图状态的门/怪/墙）。

**实现警告**：此检查依赖当前地图状态（机关门开闭），因此是动态的。若地图状态改变，结果可能变化。

---

### I.5 各楼层飞行属性

#### I.5.1 canFlyTo / canFlyFrom / isHide（来源：浏览器引擎，全塔枚举）

| 楼层 | canFlyTo | canFlyFrom | isHide | 备注 |
|------|---------|-----------|--------|------|
| MT0  | **false** | true | false | 不可作为飞行目的地（地下） |
| MT1–MT43 | true | true | false | 普通楼层，正常可飞 |
| MT44 | **false** | true | **true** | 隐藏层；楼梯到不了（:next/:before 跳过本层），只能用 upFly/downFly 进入；可飞出但不可飞入 |
| MT45–MT49 | true | true | false | 普通楼层，正常可飞 |
| MT50 | **false** | **false** | false | 顶层；既不可飞入也不可飞出 |

**特殊楼层小结**：
- **MT0**：不可飞入；若需进入，只能从 MT1 走楼梯。
- **MT44**（隐藏层）：不可飞入；**楼梯也到不了**——引擎 `:next`/`:before` 楼梯解析对 isHide 层透明（跳过），故 **MT43 的 (1,11) 上楼梯与 MT45 的 (1,1) 下楼梯直接相连**，中间的 MT44 被跳过（玩家实测 2026-06-04 确认，落盘 sim `_resolve_floor_id` isHide-skip）。MT44 **只能用 upFly/downFly 道具进入**（从 MT43 用 upFly 上、从 MT45 用 downFly 下）；进入后记录 `__visited__[MT44]`，之后可用 fly魔杖飞出（canFlyFrom=true）。
- **MT50**：顶层；完全不可飞，须走楼梯 MT49→MT50。

#### I.5.2 upFloor / downFloor 落点坐标（来源：浏览器引擎，部分已确认）

落点坐标含义：飞行时的降落格（见 §I.3.2）。格式 `[x, y]`（同 `map[y][x]` 坐标系）。

| 楼层 | downFloor（向上飞时降落） | upFloor（向下飞时降落） |
|------|--------------------------|------------------------|
| MT10 | [1, 10] | [6, 10] |
| MT44 | null | null |
| MT45 | [2, 1] | [10, 1] |
| MT46 | [11, 2] | [11, 10] |
| MT47 | [11, 10] | [2, 1] |
| MT48 | [11, 10] | [1, 10] |
| MT49 | [2, 11] | **null**（无上楼梯；MT49→MT50 只能用 upFly） |

注：MT49 的 upFloor = null 已由引擎取值确认（`core.floors['MT49'].upFloor` = undefined）。MT49 的 changeFloor 字典仅有 `"1,11"` 一条（→ `:before` = MT48），无指向 MT50 的楼梯格。
MT1–MT9、MT11–MT43 的 upFloor/downFloor 待完整楼层提取后补充（须运行 gen_floors.py 扩展范围）。

---

### I.6 centerFly（瞬移，item:centerFly）

`useItemEffect`（源码）：
```javascript
core.clearMap('hero');
core.setHeroLoc('x', core.bigmap.width  - 1 - core.getHeroLoc('x'));
core.setHeroLoc('y', core.bigmap.height - 1 - core.getHeroLoc('y'));
core.drawHero();
core.setFlag('talking', 0);
core.drawTip(core.material.items[itemId].name + '使用成功');
```

**传送公式**（此塔地图 13×13，bigmap.width = bigmap.height = 13）：
```
新x = 12 - 旧x
新y = 12 - 旧y
```
即关于地图中心 (6,6) 的点对称。

#### 使用前校验（canUseItemEffect）

centerFly **在传送前执行碰撞检测**。完整源码：

```javascript
// core.material.items['centerFly'].canUseItemEffect（从运行中引擎取得）
(function () {
    var toX = core.bigmap.width  - 1 - core.getHeroLoc('x'),
        toY = core.bigmap.height - 1 - core.getHeroLoc('y');
    var id = core.getBlockId(toX, toY);
    return id === null || id === 'none' || id === 'airwall';
})();
```

调用链：
```
canUseItemEffect
  → core.getBlockId(toX, toY)
      → core.maps.getBlock(x, y, floorId, false)
          → blockObjs[x+","+y]  （false = 不含 disabled block）
      → block == null ? null : block.event.id
```

`_mapIntoBlocks` 将所有 `block.id ≠ 0` 的 tile 装入 blockObjs。各 event.id 对应规则：

| 目标格情况 | event.id | canUseItemEffect 返回 | 结果 |
|-----------|---------|----------------------|------|
| 空地板（tile 0，无 trigger）| 不入 blockObjs → null | `null === null` → **true** | **可传送** |
| 装饰地板（tile 18/19/66-80等）| "none" | `id === 'none'` → **true** | **可传送** |
| 透明墙 airwall（tile 17）| "airwall" | `id === 'airwall'` → **true** | **可传送** |
| 普通墙（tile 1）| "yellowWall" | false | **被拦截** |
| fakeWall（tile 2/3）| "fakeWall"/"fakeWall2" | false | **被拦截** |
| 怪物 | 怪物 ID | false | **被拦截** |
| 门 | 门 ID | false | **被拦截** |
| 地面道具 | 道具 ID | false | **被拦截** |
| 已击败怪物（disabled）| `getBlock` 返回 null → null | **true** | **可传送** |

**来源**：`core.items.canUseItem.toString()`（通过浏览器引擎取得）：
```javascript
function(itemId) {
    if (!core.hasItem(itemId)) return false;
    var canUseItemEffect = core.material.items[itemId].canUseItemEffect;
    if (canUseItemEffect) {
        try { return eval(canUseItemEffect) } catch(e) { main.log(e); return false }
    }
}
```
若 `canUseItemEffect` 返回 false，`useItem` 立即 return，不执行 `useItemEffect`（即不传送、不播放音效）。

**与玩家实测一致**：对称格有墙/怪/门/道具 → 必定被拦截，无法传送。

**其他特性**：
- 不切换楼层，不产生任何 FLOOR token。
- 路由 token：`useItem` 记录 `"item:centerFly"` → 编码为 `I{num}:` → 解码为 `ITEM:{num}`。
- 不消耗道具（`useItemEffect` 无 `removeItem` 调用；本塔中可反复使用——待确认次数上限）。

---

### I.7 upFly / downFly（±1层飞翼）

#### 使用前校验（canUseItemEffect，来源：浏览器引擎 toString，2026-05-31）

```javascript
// upFly canUseItemEffect
(function () {
    var floorId = core.status.floorId,
        index = core.floorIds.indexOf(floorId);
    if (index >= 49) {               // ← 硬编码封顶：从 index≥49 的层起飞 → 拒绝
        core.drawTip('你已在最高层');
        return false;
    }
    if (index < core.floorIds.length - 1) {
        var toId = core.floorIds[index + 1],
            toX = core.getHeroLoc('x'),
            toY = core.getHeroLoc('y');
        var mw = core.floors[toId].width, mh = core.floors[toId].height;
        if (toX >= 0 && toX < mw && toY >= 0 && toY < mh
            && core.getBlockId(toX, toY, toId) == null) {
            return true;             // ← 目标层该坐标为空 → 允许
        }
    }
    core.drawTip('上一层此位置有东西');
    return false;
})();

// downFly canUseItemEffect
(function () {
    var floorId = core.status.floorId,
        index = core.floorIds.indexOf(floorId);
    if (index < 1) {                 // ← 硬编码地板：已在最低层 → 拒绝
        core.drawTip('你已在地下室');
        return false;
    }
    var toId = core.floorIds[index - 1],
        toX = core.getHeroLoc('x'),
        toY = core.getHeroLoc('y');
    var mw = core.floors[toId].width, mh = core.floors[toId].height;
    if (toX >= 0 && toX < mw && toY >= 0 && toY < mh
        && core.getBlock(toX, toY, toId) == null) {
        return true;                 // ← 目标层该坐标为空 → 允许
    }
    core.drawTip('下一层此位置有东西');
    return false;
})();
```

`upFly useItemEffect`（源码）：
```javascript
var floorId = core.floorIds[core.floorIds.indexOf(core.status.floorId) + 1];
if (core.status.event.id == 'action') {
    core.insertAction([
        {"type": "changeFloor", "loc": [x, y], "floorId": floorId},
        {"type": "tip", "text": "上飞翼使用成功"}
    ]);
} else {
    core.changeFloor(floorId, null, core.status.hero.loc, null, function() {
        core.drawTip('上飞翼使用成功');
        core.replay();
    });
}
```
`downFly` 同理，改为 `currentIndex - 1`。

#### upFly / downFly 与 fly魔杖 的检查项对比

| 检查项 | fly魔杖（core.flyTo） | upFly | downFly |
|-------|----------------------|-------|---------|
| `canFlyFrom[fromId]` | ✅ 检查 | ❌ **不检查** | ❌ **不检查** |
| `canFlyTo[toId]` | ✅ 检查 | ❌ **不检查** | ❌ **不检查** |
| `hasVisitedFloor` | ✅ 检查 | ❌ 不检查 | ❌ 不检查 |
| floorTofloor gate1 | ✅ 检查 | ❌ 不检查 | ❌ 不检查 |
| 层索引封顶 | — | ✅ `index >= 49` → 拒绝 | — |
| 层索引地板 | — | — | ✅ `index < 1` → 拒绝 |
| 目标格为空 | — | ✅ getBlockId==null | ✅ getBlock==null |

**关键结论**：
- `canFlyTo` / `canFlyFrom` **只对 fly魔杖生效**，对 upFly/downFly 无效。
- upFly 的封顶是**硬编码 `index >= 49`**，不是 canFlyTo：从 MT49（index=49）起飞时 49≥49 → 拒绝，因此 **MT49→MT50 通过 upFly 不可行**（不是因为 canFlyTo=false，而是因为硬编码封顶）。
- downFly **不检查 canFlyFrom**，只检查目标层该坐标是否有障碍物。

**传送规则**：
- 目标层 = 当前层 floorIds 下标 ±1 的楼层 ID。
- 降落坐标 = **当前英雄坐标**，不使用 upFloor/downFloor 字段。
- 不产生 `fly:MTn` token；记录 `"item:upFly"` / `"item:downFly"` token（编码为 `I{n}:`）。

#### 实现状态（sim，2026-06-04）✅ 已实现

- `sim/simulator.py::_use_floor_fly_item(state, item_id, step_dir)` 复刻 upFly(+1)/downFly(-1)：
  目标层 = floorIds[idx±1]；落点 = 当前英雄坐标；硬顶 idx≥49 / 硬底 idx<1；
  目标格须为空(terrain==0 且 entities==0)否则整体 no-op；不查 canFlyTo/canFlyFrom/hasVisitedFloor；成功消耗 1。
  派发：`_use_item_by_id` 中 `upFly→+1`、`downFly→-1`；tile 51=upFly、52=downFly。
- **隐藏层进入根因修复**：MT44 `isHide=true`（canFlyTo=false、canFlyFrom=true）。
  `_resolve_floor_id` 早已正确跳过 isHide 层（MT43↔MT45 楼梯双向直连、跳过 MT44；MT44 自身楼梯仅单向出口）。
  真正的 bug 在 `_copy_state` 重建 FloorState 时**漏传 `is_hide=f.is_hide`** → 每步把 is_hide 重置为 False，跳过逻辑失效，
  导致 tok4473 在 MT45(2,1) 按 L 误走楼梯进 MT44。修复 = `_copy_state` 补一行 `is_hide=f.is_hide`。
  进 MT44 的唯一途径 = upFly/downFly（route 实测 tok4507 ITEM:51=upFly，MT43(9,4)→MT44(9,4)）。

#### 炸弹 bomb（tile49, cls=tools）✅ 已实现 — KEY:50='2' 已坐实绑定

**来源**：浏览器引擎 `core.material.items.bomb.useItemEffect` toString（2026-06-04 实测）。`canUseItemEffect` 恒 `true`。

```javascript
(function () {
  var bombList = [], todo = [], money = 0;
  var heroX = core.getHeroLoc('x'), heroY = core.getHeroLoc('y');
  var targets = {};
  var canBomb = function (x, y) {
    var block = core.getBlock(x, y);
    if (block && !block.disable && block.event.trigger === 'battle'
        && block.event.cls.indexOf('enemy') === 0) {
      var enemy = core.material.enemys[block.event.id];
      var hp = core.getEnemyValue(enemy, 'hp', x, y);
      return hp < 500;                         // ← 严格 hp<500 才炸得死
    }
  };
  var prepareBomb = function (x, y) {
    if (!canBomb(x, y)) return;                // ← 不可炸格逐个跳过
    bombList.push([x, y]); targets[x + "," + y] = true;
    var enemy = core.material.enemys[core.getBlockId(x, y)];
    money += core.getEnemyInfo(enemy, null, x, y).money || 0;   // ← 只给金币
    core.push(todo, core.floors[core.status.floorId].afterBattle[x + "," + y]);  // ← floor afterBattle
    core.push(todo, enemy.afterBattle);                                          // ← enemy afterBattle
  };
  var scan = core.utils.scan;                  // {up,left,down,right} 四方向相邻(非8格)
  for (var d in scan) prepareBomb(heroX + scan[d].x, heroY + scan[d].y);
  if (bombList.length > 0) {
    var indexes = [];
    for (var i in core.status.thisMap.blocks) {
      var b = core.status.thisMap.blocks[i];
      if (targets[b.x + "," + b.y]) indexes.push(i);
    }
    core.removeBlockByIndexes(indexes); core.redrawMap();   // ← 批量移除
  }
  core.playSound('炸弹');
  core.status.hero.money += money;
  if (todo.length > 0) core.insertAction(todo);  // ← 统一触发收集到的 afterBattle
})();
```

**逐条结论**：
- **范围**：`core.utils.scan` = `{up:(0,-1), left:(-1,0), down:(0,1), right:(1,0)}` → **上/左/下/右四个相邻格，非 8 格**。
- **可炸条件**：该格 block 存在且 `!disable`、`event.trigger==='battle'`、`event.cls` 以 `'enemy'` 开头、且 `getEnemyValue(hp,x,y) < 500`（**严格小于 500**）。hp≥500（boss级）→ 跳过该格。
- **不可炸处理**：`if(!canBomb) return` 逐格跳过；炸弹**仍可用、仍消耗**（canUseItemEffect 恒 true，无目标也消耗）。
- **奖励**：累加 `money`（`hero.money += money`）→ **给金币，不给经验**；引擎无"击杀计数"概念（sim 的 kill_count 不随炸弹增加）。
- **afterBattle（命门，已坐实）**：bomb **触发 afterBattle**——对每个被炸怪显式 `core.push(todo, floors[floorId].afterBattle[x,y])` + `enemy.afterBattle`，移除后 `core.insertAction(todo)` 执行。
  即 **bomb 杀怪走与正常战死【同一 floor.afterBattle 路径】**（不是只 removeBlock）。
  ⇒ MT44 在 (6,9) 用 bomb 一发炸掉 (5,9)(7,9) 两只 redGuard(hp180<500)：
  afterBattle["5,9"] 设 flag:44=1 → afterBattle["7,9"] 见 flag:44 真 → `openDoor([6,8])` 开 specialDoor →
  上行取 redPotion(×2,+250×2=+500)/shield5(+100 DEF) → tok4528 落 MT44(6,5) HP=623 DEF=304 ✅。
- **消耗**：cls=tools → 框架 `_afterUseItem` 用后 `items.tools.bomb--`（≤0 删除）。

**sim 实现**：`sim/simulator.py::_use_bomb(state)`——四方向相邻、`_build_monster(state,id).hp < 500` 判可炸、
先批量清格+给 gold、再对每个被炸怪跑 `floor.after_battle[x,y]`（沿用 `_fight_monster` 同一 `_execute_event_list` + `_done_after_battle` 守卫）、用后 bomb -1。
KEY:50='2' 绑定落 `data/games51/replay_keybindings.json`（`"50":"bomb"`），sim 查表派发不硬编码。

---

### I.8 路由编码与切层分析修正

#### 路由编码规则（来源：`core.utils._encodeRoute_encodeOne`，引擎 toString）

```javascript
// 关键分支（节选）
if (t.indexOf("fly:") == 0)  return "F" + t.substring(4) + ":";  // "fly:MT37" → "FMT37:"
if (t.indexOf("key:") == 0)  return "K" + t.substring(4);         // "key:49" → "K49"
if (t.indexOf("item:") == 0) return "I" + _id2number(t.sub(5)) + ":"; // "item:centerFly" → "I{n}:"
// 无 "changeFloor:" 专用分支 → 楼梯切层不记录到路由
```

Python 解码器对应：`"FMT37:"` → `FLOOR:MT37`；`"K49"` → `UNK:K49`；`"K50"` → `UNK:K50`。

#### 决定性实验：走楼梯不产生 FMTn: token

**实验 1 — FMTn: 精确计数（直接统计 h5route raw string）：**

```
route_raw 总长度：5188 字符
FMTn: 出现次数：220   ← 与 floor_transitions 分析的 220 条 FLOOR:MTn 完全吻合
```

出现在 FMTn: 中的楼层：MT1–MT20, MT24–MT26, MT31–MT43, MT45–MT49（共 39 个楼层，各 1–11 次）。

**从未出现为 FMTn: 的楼层**：MT0, MT21–MT23, MT27–MT30, **MT44**, **MT50**。

**实验 2 — MT50 铁证（FMT50:=0 的真实含义）：**

- MT50：`canFlyTo=false`，`canFlyFrom=false` → 不可用 fly魔杖 进出
- 此存档为通关存档，玩家必然到达 MT50
- **FMT50: 出现次数 = 0**
- ~~初始推断：只能走楼梯从 MT49 上楼梯进入~~ ← **已推翻**

**实测更正（玩家行为级事实 + 引擎源码双重验证）**：

MT49 **根本没有通往 MT50 的楼梯**（引擎确认：`core.floors['MT49'].changeFloor` 只有 `"1,11":before` 一条，指向 MT48，无指向 MT50 的条目；`upFloor=null`）。MT49→MT50 唯一路径是 **upFly 道具**（绕过 canFlyTo=false，产生 `ITEM:{n}` token 而非 FMTn:）。

MT50 的真实入场方式有两种，均不产生 FMT token：
1. **upFly（ITEM token）**：从 MT49 使用 upFly 道具，绕过 canFlyTo 限制，落点 = 当前英雄坐标（§I.7）
2. **MT24 特殊事件传送（无 token）**：踩 MT24(6,2) 触发条件事件（见 §I.9）

因此 FMT50:=0 的正确结论是：**MT50 的入场路径均不产生 FMT token**，不是"走楼梯"的证据。

**实验 3 — 开局段（UDLR 纯序列）：**

路由前 93 个字符（第一个 FMT token 出现前）：
```
C1 C1 L2 U2 R2 U6 L1 U5 R2 U4 R1 U4 R1 U6 R1 U7 L10 D9 R3 U3 L4 U1 L2 D5
R3 U10 L1 D3 R2 U2 L1 D4 R6 U1 C0 L3 D6 R5 U6 L10 D5 R4 U5 R5 D3 L3 D5 R4 L5
→ FMT4:   （第一次 fly魔杖：直接飞到 MT4）
```
完整 token 列表为纯 CHOICE + UDLR，无任何 FMT token。玩家在初始楼层（MT1）探索后直接用 fly魔杖 飞到 MT4，中间无楼梯 token。

#### 最终结论

> ~~"217次为changeFloor（走楼梯），3次为fly魔杖"~~ ← **已废除，来源于错误假设。**

| 类型 | 路由表现 | 本存档计数 |
|------|---------|-----------|
| **fly魔杖** | `fly:MTn` → 编码为 `FMTn:` → 解码为 `FLOOR:MTn` | **220 次** |
| **走楼梯** | 不记录 token，隐含于 UDLR 序列，changeFloor 在回放时自动触发 | 未知（需模拟器统计） |
| **upFly/downFly** | `item:upFly` / `item:downFly` → 编码为 `I{n}:` → 解码为 `ITEM:{n}` | 若有则在 ITEM token 中 |
| **特殊事件传送** | 事件脚本内 changeFloor 指令触发，不记录任何 token | 已确认至少 2 次（MT3伏击→MT2；MT24事件→MT50）|

floor_transitions.json 的 `type` 字段（"changeFloor"/"centerFly"/"keyboard_fly"）**全部错误**：220 条 FLOOR:MTn token 均来自 fly魔杖；"changeFloor" 标签是因为前驱 token 窗口全为 UDLR/CHOICE（无特殊 token），不是楼梯的证据。

#### "无 FMT token 楼层"的正确推断方法（修订）

**推断原则**：某楼层从未出现为 FMTn: 目的地，只能说明"该楼层未被 fly魔杖 以其为目的地飞入"。可能原因：
1. 该楼层从未被访问过（skip）
2. 该楼层经由 **走楼梯** 进入（UDLR 到楼梯格，无 token）
3. 该楼层经由 **upFly/downFly** 进入（产生 ITEM token，非 FMT token）
4. 该楼层经由 **事件脚本 changeFloor** 传送进入（无任何 token）

MT50 是第 4 类被误判为第 2 类的反例。**禁止用"不是 fly 就是走楼梯"的排除法推断**。

| 无 FMT 楼层 | canFlyTo | 入场方式 | 确定性 |
|-----------|---------|---------|--------|
| MT0 | false | 若访问过：从 MT1 走楼梯（changeFloor 字典有 `"1,1":next=MT1`，出口可 fly） | **未知**（可能未访问） |
| MT21–MT23 | **true（普通楼层）** | canFlyTo=true 与其余可飞层相同；若本存档未出现 FMTxx:，可能从未被访问或走楼梯进入 | 普通情形，无特殊机制；是否访问留给全程模拟器统计（J10） |
| MT27–MT30 | **true（普通楼层）** | 同上 | 同上 |
| MT44 | false（isHide=true） | **楼梯到不了**（:next/:before 跳过 isHide 层→MT43↔MT45 直连，upFloor=downFloor=null）；**只能 upFly/downFly 进入**；可 fly出 | **已确认**（玩家实测 2026-06-04） |
| MT50 | false | **唯一入场：MT24(6,2) 事件 changeFloor**（见 §I.9）；fly魔杖/upFly/downFly 均无法到达 | **已确认**（见 §I.9）|

#### 3 条具体误标记录（用前驱 token 核实）

| seq | global_idx | 路由 | 原分类（错误） | 正确分类 | 前驱 token 真实含义 |
|-----|-----------|------|---------------|---------|-------------------|
| 148 | 4368 | MT46→MT37 | centerFly | **fly魔杖** | ITEM:50 = 地面拾取 centerFly 道具，与飞行无关 |
| 151 | 4534 | MT45→MT37 | keyboard_fly | **fly魔杖** | UNK:K50 = 炸弹（键'2'），与飞行无关 |
| 177 | 5399 | MT48→MT47 | keyboard_fly | **fly魔杖** | UNK:K49 = 锄头（键'1'），与飞行无关 |

#### 键盘快捷键映射（⚠️ 2026-06-04 重大订正）

**确定部分**（编码层，`_encodeRoute_encodeOne`："key:n" → "Kn"，keyCode 为 ASCII）：
keyCode 49='1', 50='2', 51='3', 52='4'。解析器忠实产出 `KEY:<n>` token。

**键→道具绑定**是该**存档自定义快捷键配置**，无法从 route 反推，原表（下）系**推测**。
玩家 2026-06-04 在真实引擎实测 **键'4'(K52)=地震卷轴 earthquake**，**推翻了原推测的"upFly/downFly"**。
据此，K49/K50/K51 的旧推测**同属未经实测的猜测，一律降级为「待裁定」**，绝不在 sim 据旧表绑定。

| 路由 token | 键 | route 内出现 | 旧推测（已不可信） | 现状态 |
|-----------|-----|------------|-----------------|--------|
| `KEY:49` | '1' | tok5391 | 锄头 pickaxe | ✅ **pickaxe 破墙镐**（源码派发表 case 49 无条件 useItem('pickaxe')，见下方权威表；旧推测被证实） |
| `KEY:50` | '2' | tok4524 | 炸弹 bomb/hammer | ✅ **bomb 炸弹**（玩家实测坐实，hp<500 才炸死、触发 afterBattle，见 §I.7） |
| `KEY:51` | '3' | （本 route 未出现） | centerFly 瞬移 | 源码 case 51 = 打开 centerFly 瞬移面板（route 无此 token，暂不影响） |
| `KEY:52` | '4' | tok4369 | ~~upFly/downFly 列表~~ | ✅ **earthquake 地震卷轴**（玩家实测坐实，见 §L.6） |

> 实测落盘于 `data/games51/replay_keybindings.json`（已坐实：52→earthquake、50→bomb、49→pickaxe）。
> route 全程仅 3 个 KEY token：tok4369 KEY:52、tok4524 KEY:50、tok5391 KEY:49（另有 tok5315-5326 = 字面 "help" 字符，与快捷键无关）。
> 注：本节早前"误标记录"表中的 K50@4534 / K49@5399 为**旧解析器下标**，当前解析器为 K50@4524 / K49@5391（口径已变，以现解析器为准）。

#### keyCode→道具 的权威派发表（来源：`core.actions.actionsdata.onKeyUp(keyCode)` 引擎 toString，2026-06-04）

这是**引擎硬编码**的数字键派发（非存档/玩家配置），是 KEY token 绑定的唯一事实来源。`core.status.route.push("key:n")` **仅在对应道具实际使用成功时**写入 → route 出现 `KEY:n` ⇒ 该道具确被使用。

| keyCode | 键 | 派发逻辑（源码原文） |
|---------|-----|--------------------|
| 49 | '1' | `if hasItem('pickaxe') && canUseItem(...)` → `useItem('pickaxe')`。**无 else 备选** → 键'1' 恒为破墙镐 |
| 50 | '2' | `if hasItem('bomb')` → bomb；`else if hasItem('hammer')` → hammer（圣锤）。本塔有 bomb → bomb |
| 51 | '3' | `if hasItem('centerFly')` → 打开 centerFly 瞬移面板 |
| 52 | '4' | 列表 `[icePickaxe, freezeBadge, earthquake, upFly, downFly, jumpShoes, lifeWand, poisonWine, weakWine, curseWine, superWine]` 按序取**首个 canUseItem 者**使用 |

**交叉验证**：case 50→bomb、case 52→earthquake 两行与玩家独立实测**完全吻合** → 该表权威 → case 49→pickaxe **一并坐实**（非 route 反推猜测，旧 §I.8 推测被源码证实）。

---

### I.9 特殊事件传送：MT24(6,2) → MT50(6,7)

**来源**：`core.floors['MT24'].events["6,2"]`（浏览器引擎 toString，2026-05-31）

#### I.9.1 触发条件与脚本

踩上 MT24 坐标 **(6,2)** 时触发，脚本如下：

```json
{
  "6,2": [
    {
      "type": "if",
      "condition": "flag:营救公主",
      "true": [
        { "type": "setCurtain", "color": [0,0,0], "time": 200, "keep": true },
        {
          "type": "for", "name": "temp:A", "from": "24", "to": "50", "step": "1",
          "data": [
            { "type": "function",
              "function": "function(){core.ui.statusBar._update_props(core.floors[\"MT\" + core.calValue(\"temp:A\")].title)}" },
            { "type": "sleep", "time": 80 }
          ]
        },
        { "type": "changeFloor", "floorId": "MT50", "loc": [6,7], "direction": "down", "time": 200 },
        { "type": "setCurtain", "time": 200 }
      ],
      "false": []
    }
  ]
}
```

**关键字段说明**：

| 字段 | 值 | 含义 |
|------|-----|------|
| 触发位置 | MT24(6,2) | 踩格触发，**无条件检查 enable**（首次踩就运行 if） |
| 触发条件 | `flag:营救公主` | 必须事先设置此 flag（取值 true）才会传送；否则 false 分支为空，什么都不发生 |
| 视觉效果 | `for 24→50` + `sleep 80ms/层` | 纯演出：状态栏依次显示 MT24–MT50 标题，约 2.1 秒动画，无实际属性变化 |
| 目标楼层 | `MT50` | 直接跳过 MT25–MT49 |
| 落点 | `loc=[6,7]` | MT50 坐标 (6,7)，即 `map[7][6]` |
| 指令类型 | `changeFloor`（事件脚本内） | 不产生任何路由 token（既非 FMTn: 也非 ITEMn:） |

#### I.9.2 MT49 / MT50 顶层区域连通结构（已勘误）

| 连通关系 | 方式 | token | 是否产生 FMT | 备注 |
|---------|------|-------|------------|------|
| MT48 → MT49（入） | fly魔杖（canFlyTo=true）或 走楼梯（MT48 upFloor） | FMT49: 或 无 | fly时产生 | 正常 |
| MT49 → MT48（出） | 走楼梯 (1,11)→:before 或 fly魔杖 | 无 或 FMTx: | fly时产生 | 正常 |
| ~~MT49 → MT50（upFly）~~ | ~~upFly 道具~~ | — | — | **❌ 错误已删除**：upFly 从 MT49（index=49）起飞时被 `index>=49` 硬编码封顶，无法到达 MT50 |
| **MT24(6,2) → MT50(6,7)** | **事件 changeFloor**（`flag:营救公主=true`）| **无 token** | ❌ 无 FMT | MT50 **唯一入场路径** |
| MT50 → MT49（downFly） | downFly 道具（**不检查 canFlyFrom**，只检查目标格） | ITEM:{n} | ❌ 无 FMT | **位置限制**：目标格 MT49(x,y) 须为空；MT49(6,7) 初始为 specialDoor（需清除后才可用） |
| MT50 → 其他 fly魔杖 | ❌ canFlyFrom=false → 被 core.flyTo 拒绝 | — | — | fly魔杖 检查 canFlyFrom |
| MT50 → MT51（upFly） | ❌ MT50 index=50，`50>=49` → 硬编码封顶 | — | — | MT51 不存在且被封顶 |

**MT50 进入：唯一路径是 MT24 事件 changeFloor**

fly魔杖、upFly、downFly 三者均无法到达 MT50，原因各不相同：

| 道具 | 失败原因 | 检查字段 |
|------|---------|---------|
| fly魔杖 | `canFlyTo[MT50]=false` | `core.flyTo` 检查 canFlyTo |
| upFly（从 MT49） | `index >= 49` → 硬编码封顶 | **不检查 canFlyTo**，由 index 封顶 |
| downFly | MT51 不存在，目标层 = floorIds[51] = undefined | — |

**MT50 离开：downFly 理论上可行（位置相关）**

downFly 不检查 canFlyFrom。从 MT50 的某坐标 (x,y) 向下飞，目标为 MT49(x,y)。MT49 多数位置初始有墙或特殊门，需具体检查目标格。本存档具体离场方式待模拟器跑通后统计（J12）。

**原引擎取值确认**：
- `core.floors['MT49'].upFloor` = `undefined`（null）—— MT49 无上楼梯
- `core.floors['MT49'].changeFloor` 仅有 `"1,11":before`，无 `:next` 条目 —— 无走楼梯到 MT50
- `core.floors['MT50'].changeFloor` = `{}`（空）—— MT50 无楼梯格
- `upFly_checks_canFlyTo` = false、`downFly_checks_canFlyFrom` = false（引擎取值直接确认）

#### I.9.3 `flag:营救公主` 的设置时机（J9 已确认）

**已确认（J9，来源：`MT26.json` events["6,6"]，源码核对 2026-06-04）**：`flag:营救公主` 由 **MT26(6,6) 公主（princess 132）事件**设置。

事件结构 `if flag:营救公主`：
- **true 分支**（已营救，重复踩）：仅两句对话（`\t[洋娃娃,princess]…` / `\t[hero]…`），无状态变化、无 CHOICE。
- **false 分支**（首次踩，flag 未设）：两句对话后，**跨层 setBlock 改写 MT24 地图**，末尾 `setValue flag:营救公主=true` + playBgm。

false 分支对 MT24 的改写（全部 `floorId:"MT24"`）：

| 指令 | MT24 坐标 | 落子 | 作用 |
|------|----------|------|------|
| setBlock whiteWall2 | (6,1) | 321 | 演出装饰 |
| setBlock 1 | (5,1) | 墙 | 封边 |
| setBlock 1 | (7,1) | 墙 | 封边 |
| setBlock 0 | (6,2) | 地板 | **打通传送触发格** |
| setBlock 0 | (6,3) | 地板 | 打通通路 |
| setBlock 0 | (6,4) | 地板 | 打通通路 |
| show | (6,2) | — | 显示该格 |

→ **跨层动态建图点**（一层事件改写另一层地图，呼应建图铁律「地图连通性是动态的」）。改写后回 MT24 踩 (6,2)、flag 成立 → `changeFloor MT50(6,7)`（§I.9.1）。

**一次性保证**：事件无 `hide/remove`，但首访即 `flag=true`，此后重踩走 true 分支（仅对话），map 改写不重复。

模拟器须在触发 MT24(6,2) 前确保 flag 已写入 `hero.flags`，且已应用上述 MT24 col-6 跨层改写（字符串 id setBlock，见 §M.5）。

#### I.9.4 模拟器实现要点

1. `_execute_instruction()` 需支持 `changeFloor` 指令类型（当前未实现，同 MT3 伏击）。
2. `for` 循环指令（type="for"）：纯视觉演出，模拟器可作为 **no-op** 处理（不改变任何属性）。
3. 切层目标 `MT50, loc=[6,7]` 须写入 `pending_floor_change`，外层循环完成跨层。
4. 此事件**无 `hide/remove=true`**：可重复触发（每次踩 MT24(6,2) 且 flag:营救公主=true 都会传送）。
   → 模拟器不需要用 `_suppressed_events` 抑制此事件（除非引擎另有逻辑，待确认）。

---

## M. 剧情 Boss 强制战斗（MT32 / MT40 骑士队长）—— canBattle 拦截的唯一例外

> ⚠️ **全塔铁律例外，务必记清，禁止当作 bug "修掉"。**
> 普通战斗遵守 canBattle 拦截：`damage >= hp` 时**不允许战斗、英雄原地不动**（见 `sim/combat` + `_fight_monster`，对应 `core.enemys.canBattle` = `damage != null && damage < hp`）。
> **MT32 与 MT40 的骑士队长 boss 是全塔仅有的两处「强制战斗（force）」**：勇者走到触发格被剧情拉去打，**即使 `damage >= hp` 也必须打，打不过就当场死亡**——与普通拦截规则**相反**。

### M.1 引擎依据（force 语义）

`core.events.battle(id, x, y, force, ...)` 的拦截判断为 `if (n > 0 && !force ...)`（n = 预计损血）：
- `force = false`（普通战斗）：`damage > 0 且 damage >= hp` → 拦截，不打。
- `force = true`（剧情 boss）：跳过拦截，无条件开打，扣 `damage`（可致 `hp <= 0` = 死亡）。

事件脚本里以 `{"type":"battle","id":"..."}` 触发的战斗即走 `force=true` 路径（剧情强制）。

### M.2 MT32 骑士队长完整时序（来源：`MT32.json` events["6,10"]）

prologue 演出 + 强制战斗，逐条：
1. `setEnemy id=yellowKnight name=special value=1` —— **临时把骑士队长的 special 置为 `[1]`（先攻）**。
2. `hide (6,2) (6,9) remove` —— 清掉两块 `whiteWall2(321)` 装饰。
3. `setBlock number="yellowKnight" loc=[[10,1]]` —— 在 (10,1) **动态生成**骑士队长（字符串 id，tile 226）。
4. `move/keep` 演出：把队长移到 (6,1) 一带，对话。
5. `if core.canBattle('yellowKnight')`：
   - **true → `battle yellowKnight`（强制战斗）**。本存档 route 走这支（勇者打赢、不死）。
   - false → 退化分支（`!flag:addhp && flag:开启特性` 等），最终仍是 `battle`（强制）或直接 `hp=0`，即**打不过则死**。
6. 战后对话「有本事到 40 楼再打一次」+ 移动演出。
7. `setEnemy id=yellowKnight name=special value=0` —— **还原 special 为 `[]`**（解除先攻）。
8. `hide remove` —— 清掉演出残留。
> 另有 `afterBattle["1,10"]["3,10"]`（与 boss 无关）：杀 2 只 blueGuard 计数 `flag:32`，满则 `openDoor(2,9)`。

### M.3 骑士队长的先攻来自哪里（源码坐实）

- `monsters.json.yellowKnight`：hp=120 / atk=150 / def=50 / gold=100，**`special=[]`（基础无特技）**。
- 先攻**不是怪物常驻**，而是上面第 1 步 `setEnemy special=1` **临时赋予**，第 7 步还原。
- special 1 = 先攻，伤害公式已实现（§A.4 第 84 行 `if hasSpecial(1): init_damage += per_damage`，即英雄多挨一刀；§A.1「玩家先手，除非怪物有先攻」）。
- ∴ boss 这一刀的多挨损血 = `per_damage`，必须在 setEnemy 生效后用同一套 getDamageInfo 算，**不得手写**。

### M.4 模拟器实现要点（force 仅限这两场，普通战斗拦截不变）

1. `setEnemy`：维护 `GameState._enemy_overrides = {id: {attr: val}}`；`special` 的 `value` 解析为 `[int]`（0 → `[]`）。建怪时用覆盖值（`_build_monster`），普通战斗与 boss 共用同一建怪逻辑。
2. `battle` 指令 = **强制战斗**：用 `_build_monster` + `compute_combat` 算 `damage`，**跳过 `damage >= hp` 拦截**，直接 `hp -= damage`（可致死），给金币/升级/后置效果；**不操作网格**（生成/移除由 boss 演出的 setBlock/hide 自理）。
3. `core.canBattle('id')` 条件：建怪→算损血→`damage is not None and damage < hp`。
4. **隔离**：force 路径只存在于 `battle` 指令；`_process_move → _fight_monster` 的普通战斗保留 `damage >= hp → return` 拦截，零改动。

### M.5 setBlock 接受字符串 tile id（扩展）

`setBlock number` 可为字符串（如 `"yellowKnight"` / `"yellowWall"` / `"specialDoor"`），引擎按 id 反查 tile 编号。原实现只查实体表（怪/道具/NPC），**门/墙/地形 id 查不到会误置 0**。修正：建**全量 id→tile 映射**（覆盖 tiles.json 全部分段：walls/terrains/animates/items/enemys/npcs）供 setBlock 字符串与 searchBlock 反查。
- `yellowKnight`→226（enemy）、`yellowWall`→1（墙）、`specialDoor`→85（机关门）、`whiteWall2`→321（地形）。

### M.6 searchBlock 语义（MT29 小偷暗道，支线）

- `core.searchBlock('whiteWall2', 'MT23').length` = MT23 上 `whiteWall2(321)` 的当前数量。
- MT29 events["6,2"]（踩小偷格）：`if (searchBlock('whiteWall2','MT23').length > 0)` → 再判 `flag:额外功能开关`（**默认关**）→ 默认只出对话、**不开** (6,3) 暗道；MT23 的 whiteWall 全被「还原」后（length==0）才直接开暗道（move + 传送 MT2）。
- **原版**：碰过 MT23 所有 whiteWall 才能走 MT29 暗道；**当前版本无需完成**，暗道是通往 MT2 的**支线捷径，主线不依赖**。模拟器实现 searchBlock 基本语义即可（默认 length>0 → 暗道不开 → 主线走正常楼梯）。

### M.7 MT40 骑士队长 boss = **「红门以上存活怪才打」**（区别于 MT32 的无条件强制战斗）

> ⚠️ **MT32 与 MT40 都是 force 强制战斗，但触发条件不同，不可混为一谈。**
> - **MT32**：单场 boss，无条件触发（§M.2）。
> - **MT40**：踩 (6,7) 触发对**红门以上所有「还活着」的怪**逐个先攻强制战斗；**已死/已清的怪不参与、零伤**。

**源码依据**（`MT40.json` events["6,7"] 内 `{"type":"function"}` 的原始 JS，已从 live engine 提取核对）：

```js
var a = [[5,4],[4,4],[3,4], [7,4],[8,4],[9,4], [4,2],[3,2],[2,2], [8,2],[9,2],[10,2], [6,1]];
for (var i = 0; i <= 12; i++) {
    var x = a[i][0], y = a[i][1];
    if (core.getBlockId(x, y) !== null) {            // ← 逐场存活判断：该格还有怪才打
        // sleep + move(把 a[i] 的怪移到 (6,7)) + battle(loc:[6,7])
    }
    // i===2/5/8/11 队长台词；i===12 收尾(setBlock upFloor[6,1] 等纯演出)
}
core.insertAction(todo);
```

- `a` 的 13 格 = 红门(83,在(6,8))以上全部怪：ghostSkeleton×3 / soldier×3 / swordsman×3 / redKnight×3 / yellowKnight×1。
- `if (core.getBlockId(x,y) !== null)`：该格仍有实体（怪没被提前清掉）才生成「移动+战斗」；**已清格 `getBlockId===null` 直接跳过**。
- 怪先 move 到 (6,7) 再 `battle`，是演出；对状态的唯一影响 = 与该怪打一场（force + special=1 先攻）。
- 全程 setEnemy special=1 先攻、打完 special=0 还原（同 §M.3）。战后 setBlock 把 12 格覆为掉落、setBlock 87 在 (6,1) 开上楼梯、setValue flag:402=true（events[6,1] 凭此放行下一层）。
- **本存档 route**：用 centerFly 瞬移到 (2,1) 后，先用普通走格清光红门以上全部 13 个怪，再踩 (6,7) → 13 格全 `getBlockId===null` → **一场都不打、HP 零损**（真值 tok4103 后 HP 恒为 262）。

**模拟器实现**（`data` 展开为带 `loc` 的 battle 指令 + 引擎按存活判断派发）：
1. `MT40.json` events["6,7"] 的 13 场 battle 各带 `loc:[x,y]`（怪原格，顺序即源码 `a`）。
2. `_execute_instruction` 的 `battle` 分支：**带 `loc`** → 读 `entities[ly][lx]`，为 0（已清，`getBlockId===null`）则**跳过零伤**；非 0 则取该格怪 `_forced_battle` 后清格。**无 `loc`**（MT32）→ 保持无条件强制战斗，语义零改动。
3. ∴ MT32 不可达性铁律不受波及（`test_force_battle_mt32.py` 全套看守）。

### M.8 勇者死亡（HP≤0）= 硬终止（game over），之后一切不执行

> 引擎机制：`hp <= 0` 立即 `core.events.lose()`，游戏结束。重放路线不会死，但 **solver 启发式搜索会探索大量会死的路线**，死亡必须是硬终止，否则搜索会在「负血英雄」上继续推演出虚假路径。

- **`GameState.dead`**（默认 `False`）：任何 HP 结算后若 `hp <= 0` 即置 `True`。死亡来源 = **绕过 canBattle 拦截的扣血**：强制战斗（§M.1/§M.7）、事件扣血（setValue status:hp）、poison/地形伤等。
- **`step()` 入口检查**：`dead` 为真 → 对一切 token **no-op**（原样返回，不战斗/拾取/切层/触发事件），状态冻结在死亡点。
- **冻结在死亡点**：强制战斗序列中某一场致死 → `_forced_battle` 当场置 `dead`，`_execute_event_list` 检测到 `dead` **立即停止**执行事件列剩余指令（不再打后续怪、不 setBlock）。
- **与「打不过原地不动」(§M.4.4) 的关系**：普通走格战斗的 `damage >= hp` 拦截**不变**——普通战斗永远不会致死（打不过就原地不动）；**能致死的只有 force/事件/地形**这些绕过拦截的来源，故仅在这些结算点查 `dead`。

---

## N. 终局 boss 链：MT49 中间魔王竞技场 + MT50 终局魔王 + 通关判定

> 入场前置见 §I.9（营救公主传送）。本节为 MT50「boss 死即通关」的源码依据，及与之耦合的 MT49 魔王竞技场。来源：`MT49.json` / `MT50.json` events·autoEvent·afterBattle（live engine 提取，逐格 0 处校验）+ `monsters.json`。
> **两处 redKing 是同一敌人模板**（`monsters.json redKing` hp8000/atk5000/def1000/gold500/**special[]=普通战斗**），靠 setEnemy 改写同一模板。

### N.1 两个 redKing 战斗（勿混淆）

| 位置 | redKing 属性 | 来源 | 性质 |
|---|---|---|---|
| **MT49 (6,3)** | `setEnemy` 三维 **/= 10**（对触发时的当前模板；若此前未被改写 = base 8000/5000/1000 → 800/500/100） | `MT49.json` events["6,6"] + autoEvent["1,1"] | 中间魔王，杀后掉落（redKey/knife/redGem…），**非通关** |
| **MT50 (6,5)** | `setEnemy` 绝对设 **5000/1580/190**（无 operator = 覆盖任何先前 /10；special 仍 []） | `MT50.json` events["6,5"] | **终局魔王，杀即通关** |

### N.2 MT49 中间魔王竞技场

**入场门控（两道 specialDoor，镜像 MT45：杀守卫对→首杀 set flag、次杀 openDoor）：**
- specialDoor **(6,9)** ← 清 (5,10)+(7,10)：afterBattle 首杀 `flag:491+=1`，次杀 `flag:491` 真 → `openDoor(6,9)`。
- specialDoor **(6,7)** ← 清 (5,8)+(7,8)：同理 `flag:492` → `openDoor(6,7)`。

**踩 (6,6) → events["6,6"]（开战演出）：**
1. `setBlock specialDoor @(6,7)` — 把刚开的 (6,7) **重新关上**（封入竞技场）。
2. `setBlock redKing @(6,3)` time500 — 中央生成魔王。
3. 对话「你终于来了…但我的部下不同意」+ playBgm Zeno.mp3。
4. `setBlock 0 @(5,3)(6,2)(7,3)(6,4)` — 清四边 airwall(17) 占位。
5. `setBlock whiteKing @(5,2)(5,3)(5,4)(6,4)(7,4)(7,3)(7,2)(6,2)` — 魔王外围 **8 格 whiteKing 环**（魔法警卫 hp230/atk450/def100，**special[16] 夹击**，见 §C.4）。
6. hide。

**autoEvent["1,1"]（削弱魔王，currentFloor=true / multiExecute=false 仅一次）：**
- 触发条件：`getBlockId` 四角 (5,2)(7,2)(5,4)(7,4)=whiteKing **且** 四边 (6,2)(5,3)(7,3)(6,4)=null —— 即**玩家已清掉 4 个边 whiteKing、四角仍在**。
- 动作：`if flag:与50层小偷对话 → flag:TE=true`（否则空）；`setEnemy redKing hp/atk/def 各 /= 10`；update；对话「我只剩一成功力」。

**afterBattle["6,3"]（杀中央魔王）：** 对话「合格的战士」→ `hide` 整个 3×3 (5,2)-(7,4)（清魔王+残余 whiteKing）→ setBlock 掉落 redKey(5,2)/knife(7,2)/redGem(2,4)… 等。

### N.3 MT50 终局魔王 + 通关判定（"boss 死即通关" 源码依据）

**入场：** 仅 §I.9 营救公主传送 MT24(6,2)→MT50(6,7)（MT50 唯一入场路径；顶层不可飞，见 §I.5.2）。

**events["6,5"]（thief 123 所在格，到达即触发）：**
1. playBgm LastFight + 勇者/小偷对话 + hide（小偷消失）。
2. `setEnemy redKing hp=5000 / atk=1580 / def=190`（**绝对设**，覆盖 MT49 的 /10）。
3. `setBlock redKing` @(6,5) — 原小偷格生成终局魔王。
4. show + 长篇魔王对话（神圣剑/智慧权杖/作者结语）。
5. 末尾 `setValue flag:与50层小偷对话=true`。

**afterBattle["6,5"]（杀终局魔王）= 通关：**
- 结构：[0]「祝贺你顺利过关…」→ [1] 多重 if（按 flag:versionType/endingType 选 reason）各分支均 `{"type":"win", reason:"…特性版/纯净版-…-TE/NE…"}`；[2][3] setValue versionType/endingType；[4] while；[5] 兜底 `{"type":"win"}`。
- **结论：杀 MT50(6,5) redKing → afterBattle 无条件抵达 `type:win`。** TE/NE、特性版/纯净版仅结局措辞（flag:TE 取决于 §N.2 削弱魔王时是否已 flag:与50层小偷对话），**不影响"是否通关"**。

**∴ 重放/搜索的两个终止条件：** (a) §M.8 HP≤0 → game over；(b) 本节 杀 MT50(6,5) redKing → `type:win` 通关（此刻剩余 HP = 最优化目标值）。

### N.4 玩家裁定（2026-06-04 结案）

- **N-a【已定】**：MT49(6,3) 与 MT50(6,5) 两个 redKing **各打各的、互不影响**。MT49 杀的是 autoEvent /10 削弱后的魔王（作用于当前模板；若 base 8000/5000/1000 → 800/500/100）；MT50 杀的是 events["6,5"] **绝对设 5000/1580/190** 的终局魔王（绝对设独立于 MT49 的 /10，不叠加）。本 route **两个都杀**，但按各自属性结算——**MT49 只需杀 /10 后的魔王即可**，MT50 那只是另一场。
- **N-b【已定】**：本 route 对齐 **假结局（NE）**，**非真结局（TE）**。通关判定 = 杀 MT50(6,5) redKing → `type:win`（§N.3），与 flag:TE / flag:与50层小偷对话 顺序**无关**。真结局 TE 另需全程保留 **破墙镐 + 下楼器**——先不实现，待真结局对齐时再处理。
- **N-c【已定】**：whiteKing **确系本塔真实怪物**——`monsters.json` 坐实 `whiteKing`（tile **246**，name **"魔法警卫"**，hp230/atk450/def100/gold100，**special[16] 夹击**），出现于 MT42/43/45/48 地图 + MT49 竞技场。§N.2 第 5 步 `setBlock whiteKing ×8` **源码无误**。措辞订正：非"夹击环"整体结算，而是 **8 个独立魔法警卫**；夹击按 §C.4 标准逐格触发——玩家须站在**两个同 id whiteKing 之间**的格才扣 floor(hp/2)，单个 whiteKing 不触发。

---

## K. 冰魔法（snow）与岩浆通行机制

### K.1 道具定义（来源：`core.material.items['snow']`）

| 字段 | 值 |
|------|-----|
| id | `snow` |
| name | `冰魔法` |
| cls | `constants` |
| text | `可冻结熔岩` |
| canUseItemEffect | `"true"`（始终可使用） |
| hideInToolbox | `true` |
| hideInReplay | `true` |

### K.2 道具类型：constants = 永久持有，不消耗

`_afterUseItem`（来源：`core.items._afterUseItem`）：

```js
function(itemId) {
  var itemCls = core.material.items[itemId].cls;
  if (itemCls == "tools") core.status.hero.items[itemCls][itemId]--;  // 只扣 tools
  if (core.status.hero.items[itemCls][itemId] <= 0)
    delete core.status.hero.items[itemCls][itemId];
  core.updateStatusBar();
}
```

**结论：`constants` 类道具使用后不被扣数量，snow 可反复使用。**  
（注意边缘情况：无相邻岩浆时 `useItemEffect` 调用 `core.addItem(itemId, 1)` 会多给 1 个；正常游玩不触发。）

**持有守卫（玩家裁定 2026-06-05，已实现+单测）**：`_use_snow` 入口加 `if items['snow']<=0: return`——**背包无 snow 则使用=no-op、不清 lava**（与 centerFly 同款守卫，solver 正确性必须；否则 solver 可能在 MT35 屠龙获取前就"用 snow"）。验证：route snow 首次进背包 = token5907（MT35 屠龙后），全部 5 次 ITEM:54（tok5992/5994/5998/6001 MT13、tok6309 MT26）使用时 `items['snow']==1`，故守卫不破坏回放（46 检查点零回归）。单测 `tests/test_snow.py::test_snow_not_held_is_noop` 看守。snow 只清**四正方向**相邻 lava（不清对角，玩家 2026-06-05 实测确认）。

### K.3 获取途径（来源：`core.floors['MT35'].afterBattle['6,7']`）

MT35 位置 (6,7) 有 `magicDragon`，击败后触发：
```json
[
  { "type": "openDoor", "loc": [6, 3] },
  { "type": "hide",    "loc": [[5,7],[7,7]], "remove": true },
  { "type": "if", "condition": "flag:开启特性",
    "true":  [],
    "false": [
      { "type": "setBlock", "number": "bluePotion", "loc": [[5,5],[6,5],[7,5]] },
      { "type": "setBlock", "number": "snow",       "loc": [[6,6]] }
    ]
  }
]
```

- 条件：`flag:开启特性 = false`（普通模式）时，将 `snow` 道具放置于 MT35(6,6)
- 英雄踩上 MT35(6,6) 即拾取
- **全塔唯一来源**（`snowFloors = ["MT35"]`）

### K.4 使用效果（来源：`core.material.items['snow'].useItemEffect`）

```js
// snowFourDirections = true（四方向模式）
for (direction of ['up','down','left','right']) {
  var nx = hero_x + scan[direction].x,
      ny = hero_y + scan[direction].y;
  if (core.getBlockId(nx, ny) == 'lava') {
    core.removeBlock(nx, ny);   // 永久移除该岩浆格，变为空地(tile 0)
    success = true;
  }
}
```

- 每次使用：移除英雄当前位置四方向所有相邻 `lava`（tile 5）格，最多 4 格
- 移除后该格变 tile 0（空地），**永久**（不会恢复）
- 可在任意楼层使用，效果作用于当前楼层

### K.5 岩浆的通行性判断

`core.maps.noPass(x, y)` → `block.event.noPass`：
- 岩浆（tile 5）：`event.noPass = true` → 英雄无法踏入（`moveAction` 走 noPass 分支，不前进）
- 被 snow 移除后：`getBlock(x,y) = null` → `noPass = false` → 可通行

**岩浆通行性 = 取决于"该格是否已被 snow 移除"，不是全局 flag。**  
未移除 → 永远不可通行；已移除 → 永远可通行（空地）。

### K.6 跨层案例：MT13 sword5(6,5)

MT13 地图结构：sword5(43) 在 (6,5)，四周全为墙（tile 1）或岩浆（tile 5）。

拿到 snow 后的到达路径（最短）：

| 步骤 | 英雄位置 | 操作 | 效果 |
|------|---------|------|------|
| 0 | (6,11) 走廊 | 开黄门(6,10) | (6,10)变空地 |
| 1 | (6,10) | 用 snow | 移除(6,9)=岩浆 |
| 2 | (6,9) | 用 snow | 移除(6,8)(5,9)(7,9)=岩浆 |
| 3 | (6,8) | 用 snow | 移除(6,7)(5,8)(7,8)=岩浆 |
| 4 | (6,7) | 用 snow | 移除(6,6)(5,7)=岩浆 |
| 5 | (6,6) | 北走 | 踩 sword5(6,5)，拾取 |

最少需用 snow 4 次（snow 为 constants，可复用，无问题）。

**结论：sword5 不是纯装饰，拿到 snow 后可达，是后期回来拾取的高价值装备。**

### K.7 对模拟器的影响（待实现，暂不改代码）

1. **岩浆通行判断**：当前模拟器将 tile 5（lava）视为不可通行是正确的（MT1–MT14 期间英雄尚未到 MT35，无 snow）。
2. **snow 道具行为**：须实现为一种"地图变异动作"——使用时将当前楼层相邻 lava 格从地图移除（tile 5 → tile 0），并更新可达性缓存。
3. **snow 为 constants 类**：模拟器中不需要消耗该道具的库存（使用后 item count 不减）。
4. **跨层 sword5**：MT13(6,5) 在玩家拥有 snow 且已清路时可达，须纳入全局路径搜索（但在 MT1–MT14 重放验证中可忽略）。
5. **架构要求**：岩浆的"不可通行"判断须从 `floors[floorId].map[y][x] == 5`（或对应块的存在性）实时计算，禁止硬编码为永久不可通行。

---

## L. 矿镐（pickaxe）道具机制

### L.1 道具定义（来源：`core.material.items['pickaxe'].useItemEffect`，2026-06-02 源码坐实）

| 字段 | 值 |
|------|----|
| id | `pickaxe` |
| name | 镐 |
| cls | `tools` |
| 消耗性 | **是**（tools 类，每次使用扣 1 个） |

### L.2 使用效果（源码逐行分析）

```javascript
// canBreak 判断函数
var canBreak = function (x, y) {
    var block = core.getBlock(x, y);
    if (block == null || block.disable) return false;
    return block.event.canBreak;   // 只有 canBreak=true 的 tile 才能被砸
};
// 遍历英雄四方向（scan = U/D/L/R，不含斜角）
for (var direction in core.utils.scan) {
    var nx = heroX + delta.x, ny = heroY + delta.y;
    if (canBreak(nx, ny)) {
        insertAction({ "type": "openDoor", "loc": [nx, ny] });
    }
}
core.playSound('破墙镐');
```

### L.3 可被砸破的 tile（来源：`core.maps.blocksInfo[id].canBreak`）

| tile ID | id | 说明 |
|---------|----|------|
| 1 | yellowWall | 普通黄墙，**可砸** |
| 2 | fakeWall | 假墙，**可砸** |

**不可砸**：tile 330（unbreakableWall）、tile 4（airwall）、tile 5（lava）、tile 81–86（各色门）等——这些 block 的 `canBreak` 字段不为 true。

### L.4 效果总结

- 使用后：英雄四方向（上下左右）中**所有** canBreak=true 的格子执行 openDoor（tile→0），同时砸 **≥0 格**
- 扇区：4 方向，不含斜角
- 消耗：每次使用扣 1 个矿镐（tools 类）
- 声效：播放"破墙镐"

### L.5 对模拟器的影响 ✅ 已实现（2026-06-04）

`sim/simulator.py::_use_pickaxe(state)`：遍历英雄四方向相邻格，凡 `terrain[y][x] in floor._can_break_tiles`
（与 §L.6 earthquake 同一 canBreak 集合，数据驱动不硬编码 tile 号）→ `terrain[y][x] = 0`（openDoor 破墙）；用后 `pickaxe -= 1`。
派发：`_use_item_by_id` 中 `pickaxe → _use_pickaxe`，由 **KEY:49**（键'1'，tok5391）经 `replay_keybindings.json` 查表触发（亦兼容 `ITEM:<pickaxe-tile>`）。
与 earthquake 唯一区别 = 范围（镐=相邻 4 格、震=整层全图）。

---

### L.6 地震卷轴（earthquake）道具机制 ✅ 已实现（2026-06-04）

矿镐（§L.1–L.5）是**四方向**破墙；地震卷轴是**整层全图**破墙——两者共用同一套
`block.event.canBreak` 过滤（§L.3 的 tile 集合），只是作用范围不同。

#### L.6.1 道具定义（来源：`https://h5mota.com/games/51/project/items.js` 的 `items.earthquake`，2026-06-04 WebFetch 源码坐实）

| 字段 | 值 |
|------|----|
| id | `earthquake` |
| name | 地震卷轴 |
| cls | `tools` |
| text | 可破坏一层楼的墙 |
| 消耗性 | **是**（tools 类，使用成功后 `_afterUseItem` 扣 1，见 §K.2 同类规则） |
| canUseItemEffect | `"true"`（无前置条件，随时可用） |
| hideInToolbox / hideInReplay | true（道具栏/回放中隐藏图标，不影响逻辑） |

#### L.6.2 使用效果（`useItemEffect` 源码逐行，verbatim）

```javascript
(function () {
    var actions = core.searchBlockWithFilter(
        block => !block.disable && block.event.canBreak
    ).map(function (block) {
        return { "type": "openDoor", "loc": [block.x, block.y], "async": true };
    });
    actions.push({ "type": "waitAsync" });
    actions.push({ "type": "tip", "text": core.material.items[itemId].name + "使用成功" });
    core.insertAction(actions);
})();
```

- `searchBlockWithFilter` 默认搜**当前层全图**（不传 floorId 即 `core.status.floorId`），
  对每个 `!disable && canBreak` 的块插入一个 `openDoor`。即**清当前层所有 canBreak 墙**。
- 范围：**当前层全图**，非某半径。**不跨层**（与玩家预告"破 MT37 墙"一致——
  earthquake 在 MT37 当层使用，破的是 MT37 自己的墙，并非从别层遥控破 MT37）。
- canBreak tile（§L.3，maps.js verbatim）：**tile 1 yellowWall=true、tile 2 fakeWall=true、
  tile 3 fakeWall2=false**。门(81–86)/不可破墙(330)/装饰/楼梯**无 canBreak 字段 → 不破**。

#### L.6.3 模拟器实现（已落地）

- 数据：`tiles.json` tile 1/2 加 `"canBreak":true`、tile 3 加 `"canBreak":false`；
  `load_floor` 数据驱动收集 `FloorState._can_break_tiles`（镜像 `_no_pass_tiles`，不硬编码 tile 号）。
- 逻辑：`sim/simulator.py:_use_earthquake` —— 遍历当前层 terrain，命中 `_can_break_tiles` 的格 `=0`
  （openDoor 语义），消耗 1 个 earthquake。可达性实时重算自动生效，无需手动失效缓存。
- 触发：本存档经**键盘快捷键** `KEY:52`（键'4'）触发，不是 `ITEM:57`。见 §I.8 修正 + `data/games51/replay_keybindings.json`。
- 验证：token4369 使用后 MT37 内部连通，token4370–4417 逐格拾取 11黄/2蓝/1红/ATK+16/DEF+16，
  与玩家实测 token4417 真值**属性全部吻合**（HP/ATK/DEF/钥匙）；仅终点坐标 sim(2,3) vs 真值(2,4)
  差一步，待玩家裁定 token 边界口径（非 earthquake 问题）。

#### L.6.4 购买地点（订正）

地震卷轴在 **MT47(5,2)** 商人处购买（price 4000，give earthquake×1），**非 MT48**。
来源：`MT47.json` trader(122)@(5,2) 已提取坐实 + ledger token4360 在 MT47(4,2) 撞商人成交。
`shops.json` 原本即正确记 MT47；handoff.md / 本文档 J15 旧记"MT48"系笔误，已订正。

---

## G7. MT41 隐藏怪 (10,2) 揭示链 + afterBattle 地形重塑（"道具出现+地形变化"机关真身）

> 来源：`MT41.json` events["10,2"] / afterBattle["2,2"] / afterBattle["10,2"]（live engine 提取，逐字段核对）。
> 这是 handoff 里 **G7 机关** 的真身：玩家实测「打败隐藏怪 → 降临之翼(downFly)出现 + 地形同时变化」。
> **downFly 全塔唯一来源**：本 afterBattle 的 `setBlock downFly@(6,5)`（grep `data/games51/floors/*.json` 全塔仅此一处占位 + 玩家 2026-06-05 确认）。

### G7.1 揭示链（reveal）三段前置

1. **flag:41=1** ← 杀 (2,2) redWizard220。`afterBattle["2,2"]: setValue flag:41=1`。
2. **hasVisitedFloor('MT42')=true** ← 首次到过 MT42（本 route tok4153 经 (6,10)→MT42）。
3. **英雄站到 (9,2)** 并触发 (10,2) 假墙格（(10,2)=330 noPass，英雄站其左 (9,2) 朝右撞墙触发其 events）。

`events["10,2"]` 的 if 条件（源码原文）：
`((flag:41==1)&&((status:x===9)&&((status:y===2)&&core.hasVisitedFloor('MT42'))))`
- `status:x/status:y` = 英雄当前坐标；条件即「英雄在 (9,2)」。
- 三者全真 → true 分支：`playSound 开关门` → `sleep` → **`setBlock 220 destruct`**（无 loc = 本事件格 (10,2)，把假墙就地变成 redWizard220 现身）→ `setValue flag:41=2` → `sleep`。
- ∴ (10,2) 隐藏怪 = **第二只 redWizard220**，站 (9,2) 触发假墙后现身，再按一次右键打它 → afterBattle["10,2"]。

### G7.2 afterBattle["10,2"]：杀隐藏怪后的 13 条指令逐条翻译

| # | 指令 | 作用 | 改哪格 |
|---|------|------|--------|
| 1 | `sleep 200` | 演出节奏 | 无（sim no-op） |
| 2 | `playSound 开关门` | 音效 | 无 |
| 3 | `setBlock 0, loc:[[5,6],[7,6]]` | 先把 (5,6)(7,6) 清空（为下一步关门铺位） | (5,6)→0, (7,6)→0 |
| 4 | `closeDoor yellowWall, loc:[5,6]` | 在 (5,6) 落一道黄墙 | (5,6)→yellowWall(1) |
| 5 | `closeDoor yellowWall, loc:[6,6]` | 在 (6,6) 落黄墙（封脊柱） | (6,6)→yellowWall(1) |
| 6 | `closeDoor yellowWall, loc:[7,6]` | 在 (7,6) 落黄墙 | (7,6)→yellowWall(1) |
| 7 | `openDoor loc:[5,7]` | 打开 (5,7) 使可通行 ⚠️见下注 | (5,7)→0（待核对） |
| 8 | `openDoor loc:[7,7]` | 打开 (7,7) 使可通行 ⚠️见下注 | (7,7)→0（待核对） |
| 9 | `waitAsync` | 等 3–8 的 async 动画 | 无 |
| 10 | `setBlock downFly, loc:[[6,5]]` | **放降临之翼道具** | (6,5)→downFly(52) |
| 11 | `setBlock yellowWall, loc:[[7,1]]` | (7,1) 原 330 假墙 → 黄墙 | (7,1)→yellowWall(1) |
| 12 | `tip "降临之翼出现了"` | 提示文字 | 无 |
| 13 | `hide remove:true` | 事件自毁（防重复触发） | (10,2) 事件块移除 |

> ⚠️ **第 7/8 条待坐实（看不懂的单条，已问玩家）**：map 初始 (5,7)=(7,7)=1（墙），对墙格 `openDoor` 的确切结果（变 0？变某门？）需回引擎源码确认。功能意图清楚（让 row-7 变通路），但精确 tile 值标待核对，不在 sim 写死。

**净效果（= 玩家说的"地形也会变化"）**：
- **封死 row-6 旧横向通道**：(5,6)(6,6)(7,6) 三格 → yellowWall。原来左右互通的**唯一** row-6 通道 (7,6) 被堵死。
- **打开 row-7 新横向通道**：(5,7)(7,7) → 通，配 (6,7)=81 黄门（早开过）→ 形成 (5,7)-(6,7)-(7,7) 新左右通路。
- **放 downFly@(6,5)** 供拾取；(7,1)→黄墙。
- 一句话：**杀隐藏怪 → 降临之翼出现在脊柱 (6,5) + 横向通道从 row-6 下移到 row-7**。

### G7.3 sim 实现状态：✅ 整条链**已实现**（玩家确认 2026-06-05，commit 1377688，tok4723/4925 PASS）

- **已实现的语义**（仅 MT41 用到，通用分支+数据声明、不绑楼层）：① `status:x/status:y` 求值（`simulator.py:1915-1936` 条件求值器）；② `core.hasVisitedFloor`（同上）；③ **撞 noPass(330) 假墙先按条件求值其 events、成立则触发**（英雄当步不移入，见 `simulator.py:980-982`）；④ `setBlock 220 destruct`（无 loc=就地现身怪，`simulator.py:1564`；放实体时清底层地形 330→0 怪才可被战斗走入，`simulator.py:1572`）；⑤ afterBattle 的 `closeDoor yellowWall`/`openDoor`/`setBlock downFly` 地形重塑。
- **旧"route 够不到触发点"分析已推翻**：先前认为"英雄全 6 次 MT41 访问 maxx 恒=6、从不跨 (7,6)"——**该分析有误**。实际英雄确实到右侧 (9,2) 撞 (10,2) 假墙、杀隐藏怪、拾 downFly（tok4916）→ 下飞 MT0（tok4921）→ 拾 coin → 回 MT1，全链 tok4723/4925 两检查点 PASS 为铁证。原 §J-G7c"右半区跨越口径矛盾"随之**消解**。
- **G7.2 第 7/8 条（对墙格 `openDoor`）**：实现后检查点全 PASS，按"使 row-7 变通路"的意图落地，无需再标待坐实。

---

## J. 未确认项

以下条目标记为**待确认**，禁止在模拟器中假设：

| 编号 | 问题 | 优先级 |
|------|------|--------|
| ~~G1~~ | ~~祭坛费用/收益~~ | **已确认**（见 §D.2–D.3） |
| I2 | ~~Key token K49/K50/K52 的绑定道具~~ | ✅ **全部坐实**（2026-06-04，源码 `actionsdata.onKeyUp` 派发表 + 玩家实测交叉验证，见 §I.8 权威表）：K49='1'=**pickaxe**、K50='2'=**bomb**、K52='4'=**earthquake**。三者均已绑定 `replay_keybindings.json` 并在 sim 实现 |
| ~~I3~~ | ~~Special 14/19 battle 后处理~~ | **已确认**（见 §F） |
| ~~I4~~ | ~~Tile ID 51 对应的道具 ID~~ | **已确认**：upFly（见 §B.4） |
| ~~J5~~ | ~~护身符（amulet）的获取楼层和条件~~ | **已解决**（2026-06-05，§C.8）：本塔**无 amulet、全图无 lavaNet 地形**（updateCheckBlock 源码坐实），护身符/血网机制**空置**，无获取楼层 |
| ~~J6~~ | ~~魔法免疫 flag 的设置条件~~ | **已解决**（2026-06-05，§C.8）：设置路径 = 拾**神圣盾 shield5**（MT44(6,6)）itemEffect `setFlag('魔法免疫',true)`；移除路径 = MT3 伏击事件（§H） |
| ~~I7~~ | ~~MT10 (6,3) 机关门开放机制~~ | **已确认**（见 §G） |
| J8 | flag:fly 设置条件（fly魔杖飞行连通性检查的开关，见 §I.3.1） | 高 |
| ~~J9~~ | ~~`flag:营救公主` 的设置时机和位置（MT24(6,2)→MT50 传送的触发条件，见 §I.9.3）~~ | **已确认**：MT26(6,6) 公主事件 false 分支 setValue + 跨层改写 MT24 col-6（见 §I.9.3） |
| J10 | MT21–MT23、MT27–MT30 在本存档中是否实际访问（canFlyTo=true 普通层，走楼梯或未访问均可能），跑全程模拟器统计即可 | 低 |
| J11 | MT24(6,2) 事件在 `flag:营救公主=true` 时是否可重复触发（无 `hide/remove=true`，引擎行为待确认） | 中 |
| J12 | MT50 的实际离场方式：downFly 不检查 canFlyFrom，但需目标格 MT49(x,y) 为空；本存档具体离场坐标和 token 待模拟器统计 | 低 |
| ~~N-a~~ | ~~MT49 redKing /10 与 MT50 绝对设的交互；两魔王是否都杀~~ | **已裁定**（§N.4：各打各的，MT49 杀 /10 后魔王、MT50 杀绝对设 5000/1580/190） |
| ~~N-b~~ | ~~flag:TE 真结局顺序 + MT49↔MT50 入场口径~~ | **已裁定**（§N.4：本 route=假结局 NE，杀 MT50 即通关；TE 另需破墙镐+下楼器，暂不实现） |
| ~~N-c~~ | ~~whiteKing 8 格环逐格配对结算~~ | **已裁定**（§N.4：whiteKing=魔法警卫 tile246 special[16] 真实存在，8 个独立怪按 §C.4 夹击触发） |
| ~~J13~~ | ~~神圣盾免疫地形伤害~~ | ✅ **已解决**（2026-06-05，§C.8）：神圣盾=shield5@MT44(6,6)，itemEffect `setFlag('魔法免疫',true)` + def+100；`flag:魔法免疫` 免疫**领域15/夹击16/阻击18/激光24/伏击27** 全部区域伤（updateCheckBlock 源码）。sim 已就绪（:930/:1242），单测 `test_holy_shield.py` 6 测全过 |
| J14 | **MT43 移动的魔法警卫**（玩家预告）：MT43 whiteKing(246)@... 是否每回合/每步移动？移动规则（朝勇者?巡逻?）？sim 当前按静态怪处理——若实为移动怪，夹击触发格随之变，需建模移动 | 中 |
| ~~J15~~ | ~~MT48 地震卷轴破 MT37 墙~~ | ✅ **已实现**（§L.6）：商人在 **MT47(5,2)**（非 MT48，原笔误已订正）price4000 give earthquake；经 **KEY:52**（键'4'）使用，效果=清**当前层全图**所有 canBreak 墙（tile 1/2），**不跨层**（在 MT37 当层用，破 MT37 自身墙）。token4417 属性全吻合 |
| ~~J-G7c~~ | ~~MT41 右半区跨越口径矛盾~~ | ✅ **已解决**（2026-06-05，commit 1377688，见 §G7.3）：旧"全程不跨 (7,6)"分析有误，英雄确实到右侧 (9,2) 撞 (10,2)、杀隐藏怪、拾 downFly，揭示链已实现，tok4723/4925 PASS |
| **J16** | **bomb × coin（幸运金币）交互待源码坐实**：拾 coin(53) 后「击杀金币×2」是否覆盖 **bomb 炸怪** 的掉金？普通战斗/battle 指令已纳入×2，bomb 暂**不×2、记此待确认**。回 `core.useBomb`/炸弹结算源码坐实后接入 | 中 |
